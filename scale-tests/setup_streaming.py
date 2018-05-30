#!/usr/bin/env python3

"""
setup_streaming.py sets up the infrastructure for streaming spark scale tests. This includes the
Kafka -> Spark -> Cassandra tests.

The following steps are performed:
* Kafka ZooKeeper is installed
* Kafka is installed
* Cassandra is installed

Usage:
    setup_streaming.py <output_file> [options]

Arguments:
    <output_file>                          The file to use to store the information for the installed services

Options:
    --cleanup                              Don't install the services, but clean them up as defined in in the <output_file>

    --service-names-prefix <prefix>        The service prefix to use for all services. Defaults to their package names. [default: ]
    --kafka-cluster-count <n>              The number of Kafka clusters to install.
                                           This is used for both Kafka and ZooKeeper [default: 0]

    --kafka-package-name <name>            The package name to use for Kafka [default: confluent-kafka]
    --kafka-config <file>                  path to the config.json for the Kafka installation

    --kafka-zookeeper-package-name <name>  The package name to use for Kafka ZooKeeper [default: confluent-zookeeper]
    --kafka-zookeeper-config <file>        path to the config.json for the Kafka ZooKeeper installation

    --cassandra-cluster-count <n>          The number of Cassandra clusters to install [default: 0]
    --cassandra-package-name <name>        The package name to use for Cassandra [default: cassandra]
    --cassandra-config <file>              path to the config.json for the Cassandra installation
"""
import json
import logging
import os
import sys
import typing

from docopt import docopt

import sdk_cmd
import sdk_install
import sdk_security
import sdk_utils

import scale_tests_utils

logging.basicConfig(
    format='[%(asctime)s|%(name)s|%(levelname)s]: %(message)s',
    level=logging.INFO,
    stream=sys.stdout)

log = logging.getLogger(__name__)


SUPPORTED_MULTIPLE_CLUSTER_SERVICES = ['kafka', 'confluent-kafka', 'beta-kafka']


def install_package(package_name: str,
                    service_prefix: str,
                    index: int,
                    service_task_count: int,
                    config_path: str,
                    additional_options: dict = None) -> dict:
    if package_name.startswith("beta-"):
        basename = package_name[len("beta-"):]
    else:
        basename = package_name

    service_name = "{}{}-{:0>2}".format(service_prefix, basename, index)

    service_account_info = scale_tests_utils.setup_security(service_name, "nobody")

    service_options = scale_tests_utils.get_service_options(service_name, service_account_info, additional_options, config_path)

    expected_task_count = service_task_count(service_options)
    log.info("Expected task count: %s", expected_task_count)

    log.info("Installing %s index %s as %s", package_name, index, service_name)
    sdk_install.install(
        package_name,
        service_name,
        expected_task_count,
        additional_options=service_options,
        insert_strict_options=False)

    return {"package_name": package_name, "service_account_info": service_account_info,  **service_options}


def _supports_multiple_clusters(service_name: str) -> bool:
    return service_name in SUPPORTED_MULTIPLE_CLUSTER_SERVICES


def _get_cluster_count(args: dict, service: str) -> int:
    cluster_count = int(args["--{}-cluster-count".format(service)])

    if cluster_count > 1 and not _supports_multiple_clusters(service):
        log.error("This script currently only supports a single %s cluster", service)
        cluster_count = 1

    return cluster_count


def _get_pod_count(service_options: dict, pod_name: str, default: int) -> int:
    """
    Return the count of the specified pod name if present in the service config.
    Return the default value otherwise.
    """
    return int(sdk_utils.get_in([pod_name, 'count'], service_options, default))


def install_zookeeper(args: dict) -> list:
    """
    Install the ZooKeeper service(s) as defined by the arguments
    """
    def get_expected_task_count(service_options: dict) -> int:
        return 2 * _get_pod_count(service_options, "node", 3)

    kafka_cluster_count = _get_cluster_count(args, "kafka")

    if not kafka_cluster_count:
        return []

    kafka_zookeeper_package_name = args["--kafka-zookeeper-package-name"]
    kafka_zookeeper_service_prefix = args["--service-names-prefix"]
    kafka_zookeeper_config = args.get("--kafka-zookeeper-config", "")

    services = []
    for i in range(kafka_cluster_count):
        services.append(install_package(kafka_zookeeper_package_name,
                                        kafka_zookeeper_service_prefix, i, get_expected_task_count,
                                        kafka_zookeeper_config))

    return services


def install_kafka(args: dict, zookeeper_services: list) -> list:
    """
    Install the Kafka service(s) as defined by the arguments
    """
    def get_expected_task_count(service_options: dict) -> int:
        return _get_pod_count(service_options, "brokers", 3)

    kafka_cluster_count = _get_cluster_count(args, "kafka")

    if not kafka_cluster_count:
        return []

    kafka_package_name = args["--kafka-package-name"]
    kafka_service_prefix = args["--service-names-prefix"]
    kafka_config = args.get("--kafka-config", "")

    services = []
    for i in range(kafka_cluster_count):
        # Get the zookeeper DNS values
        zookeeper_service = zookeeper_services[i]
        zookeeper_dns = sdk_cmd.svc_cli(zookeeper_service["package_name"],
                                        zookeeper_service["service"]["name"],
                                        "endpoint clientport", json=True)["dns"]

        service_options = {
            "kafka": {
                "kafka_zookeeper_uri": ",".join(zookeeper_dns)
            }
        }

        services.append(install_package(kafka_package_name, kafka_service_prefix, i,
                                        get_expected_task_count, kafka_config,
                                        additional_options=service_options))

    return services


def install_cassandra(args: dict) -> list:
    """
    Install the Cassandra service(s) as defined by the arguments
    """
    def get_expected_task_count(service_options: dict) -> int:
        return _get_pod_count(service_options, "nodes", 3)

    cassandra_cluster_count = _get_cluster_count(args, "cassandra")

    if not cassandra_cluster_count:
        return []

    cassandra_package_name = args["--cassandra-package-name"]
    cassandra_service_prefix = args["--service-names-prefix"]
    cassandra_config = args.get("--cassandra-config", "")

    services = []
    for i in range(cassandra_cluster_count):
        services.append(install_package(cassandra_package_name, cassandra_service_prefix, i,
                                        get_expected_task_count, cassandra_config))

    return services


def install(args):
    services = {}
    services["zookeeper"] = install_zookeeper(args)
    services["kafka"] = install_kafka(args, services["zookeeper"])
    services["cassandra"] = install_cassandra(args)

    for k, v in services.items():
        log.info("%s service(s): %s", k, v)

    output_filename = args["<output_file>"]
    with open(output_filename, "w") as fp:
        log.info("Saving service info to: %s", output_filename)
        json.dump(services, fp, indent=2)


def cleanup(args):
    input_filename = args["<output_file>"]

    log.info("Reading service definition from %s", input_filename)
    with open(input_filename) as fp:
        services = json.load(fp)

    for k, services in services.items():
        log.info("Processing cleanup of %s", k)

        for s in services:

            service_name = s["service"]["name"]

            log.info("Uninstalling %s with name %s", s["package_name"], service_name)
            sdk_install.uninstall(s["package_name"], service_name)

            service_account = sdk_utils.get_in(["service", "service_account"], s)

            if service_account:
                log.info("Removing service accounts and secrets")
                sdk_security.cleanup_security(service_name, s["service_account_info"])


def main(args):
    if "--cleanup" in args and args["--cleanup"]:
        cleanup(args)
    else:
        install(args)


if __name__ == "__main__":
    args = docopt(__doc__)
    main(args)
