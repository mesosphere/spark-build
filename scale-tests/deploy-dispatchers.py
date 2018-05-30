#!/usr/bin/env python3

"""deploy-dispatchers.py

Usage:
    deploy-dispatchers.py [options] <num_dispatchers> <service_name_base> <output_file>

Arguments:
    num_dispatchers    number of dispatchers to deploy
    service_name_base  DC/OS service name base
    output_file        output file

Options:
    --cpus <n>                   number of CPUs to use per dispatcher [default: 1]
    --enable-kerberos <bool>     enable Kerberos configuration [default: False]
    --hdfs-config <url>          URL of the HDFS configuration files
    --history-service <url>      URL of the Spark history service
    --kdc-hostname <hostname>    the name or address of a host running a KDC
    --kdc-port <port>            the port of the host running a KDC [default: 88]
    --kerberos-realm <realm>     the Kerberos realm used to render the principal
    --log-level <level>          log level [default: INFO]
    --mem <n>                    amount of memory (mb) to use per dispatcher [default: 1024.0]
    --options-json <file>        a file containing installation options in JSON format
    --package-name <name>        name of the Spark package name [default: spark]
    --package-repo <url>         URL of the Spark package repo to install from
    --create-quotas <bool>       create drivers and executors quotas [default: True]
    --quota-drivers-cpus <n>     number of CPUs to use for drivers quota [default: 1]
    --quota-drivers-gpus <n>     number of GPUs to use for drivers quota [default: 0]
    --quota-drivers-mem <n>      amount of memory (mb) to use per drivers quota [default: 2048.0]
    --quota-executors-cpus <n>   number of CPUs to use for executors quota [default: 1]
    --quota-executors-gpus <n>   number of GPUs to use for executors quota [default: 0]
    --quota-executors-mem <n>    amount of memory (mb) to use per executors quota [default: 1524.0]
    --role <role>                Mesos role registered by dispatcher [default: *]
    --ucr-containerizer <bool>   launch using the Universal Container Runtime [default: True]
    --user <user>                user to run dispatcher service as [default: root]

"""

from docopt import docopt

import ast
import contextlib
import json
import logging
import os
import shakedown
import sys
import typing
import urllib

import sdk_install
import sdk_repository
import sdk_security
import sdk_utils

import scale_tests_utils


logging.basicConfig(
    format='[%(asctime)s|%(name)s|%(levelname)s]: %(message)s',
    level=logging.INFO,
    stream=sys.stdout)

log = logging.getLogger(__name__)

# This script will deploy the specified number of dispatchers with an optional
# options json file. It will take the given base service name and
# append an index to generate a unique service name for each dispatcher.
#
# The service names of the deployed dispatchers will be written into an output
# file.


@contextlib.contextmanager
def no_stdout():
    save_stdout = sys.stdout
    with open("/dev/null", "w") as null:
        sys.stdout = null
        yield
        sys.stdout = save_stdout


def create_quota(
    role_name: str,
    quota: typing.Dict
):
    with no_stdout():
        stdout, _, _ = shakedown.run_dcos_command("spark quota list --json", raise_on_error=True)
        existing_quotas = json.loads(stdout)

    # remove existing quotas matching name
    if role_name in [x['role'] for x in existing_quotas.get('infos', [])]:
        shakedown.run_dcos_command("spark quota remove {}".format(role_name), raise_on_error=True)

    cmd_list = ["spark", "quota", "create"]
    for resource, value in quota.items():
        cmd_list.extend(["-{}".format(resource[0]), value,])

    cmd_list.append(role_name)

    cmd = " ".join(str(c) for c in cmd_list)

    # create quota
    log.info("Creating quota for %s: %s", role_name, quota)

    shakedown.run_dcos_command(cmd, raise_on_error=True)


def setup_role(service_name: str, role_base: str, quota: typing.Dict) -> str:

    quota_for_role = quota.get(role_base, {})

    role_name = "{}-{}-role".format(service_name, role_base).replace("/", "__")
    if quota_for_role:
        create_quota(role_name, quota_for_role)
    else:
        log.info("No quota to assing to %s", role_name)

    return role_name


def setup_spark_security(service_name: str, driver_role: str,
                         service_account_info: typing.Dict):
    if not sdk_utils.is_strict_mode():
        return

    log.info("Adding spark specific permissions")

    sdk_security.grant_permissions(
        linux_user=service_account_info["linux_user"],
        role_name="*",
        service_account_name=service_account_info["name"],
    )

    sdk_security.grant_permissions(
        linux_user=service_account_info["linux_user"],
        role_name=driver_role,
        service_account_name=service_account_info["name"],
    )

    app_id = urllib.parse.quote(service_name)
    sdk_security._grant(service_account_info["name"],
                        "dcos:mesos:master:task:app_id:{}".format(app_id),
                        description="Spark drivers may execute Mesos tasks",
                        action="create")

    if service_account_info.get("linux_user", "nobody") == "root":
        log.info("Marathon must be able to launch tasks as root")
        sdk_security._grant("dcos_marathon",
                            "dcos:mesos:master:task:user:root",
                            description="Root Marathon may launch tasks as root",
                            action="create")

    return


def install_package(package_name: str,
                    service_prefix: str,
                    index: int,
                    linux_user: str,
                    service_task_count: int,
                    config_path: str,
                    additional_options: typing.Dict = None,
                    quota_options: typing.Dict = None) -> typing.Dict:
    """
    Deploy a single dispatcher with the specified index.
    """

    if package_name.startswith("beta-"):
        basename = package_name[len("beta-"):]
    else:
        basename = package_name

    service_name = "{}{}-{:0>2}".format(service_prefix, basename, index)

    service_account_info = scale_tests_utils.setup_security(service_name, linux_user)

    # create drivers & executors role quotas
    drivers_role = setup_role(service_name, "drivers", quota_options)
    executors_role = setup_role(service_name, "executors", quota_options)

    setup_spark_security(service_name, drivers_role, service_account_info)

    service_options = scale_tests_utils.get_service_options(service_name, service_account_info, additional_options, config_path)

    # create drivers & executors role quotas
    drivers_role = setup_role(service_name, "drivers", quota_options)
    executors_role = setup_role(service_name, "executors", quota_options)

    # install dispatcher with appropriate role
    service_options["service"]["role"] = drivers_role

    expected_task_count = service_task_count(service_options)
    log.info("Expected task count: %s", expected_task_count)

    log.info("Installing %s index %s as %s", package_name, index, service_name)

    sdk_install.install(
        package_name,
        service_name,
        expected_task_count,
        additional_options=service_options,
        wait_for_deployment=False,
        insert_strict_options=False)

    return {"package_name": package_name,
            "roles": {"drivers": drivers_role, "executors": executors_role},
            "service_account_info": service_account_info,
            **service_options}


def deploy_dispatchers(
    num_dispatchers: int,
    service_name_base: str,
    output_file: str,
    linux_user: str,
    options: typing.Dict,
    quota_options: typing.Dict):

    shakedown.run_dcos_command("package install spark --cli --yes", raise_on_error=True)
    with open(output_file, "w") as outfile:

        dispatchers = []
        for i in range(num_dispatchers):
            dispatcher_settings = install_package("spark", service_name_base, i,
                                                linux_user,
                                                lambda x: 0,
                                                None,
                                                options,
                                                quota_options)
            dispatchers.append(dispatcher_settings)
            outfile.write("{},{},{}\n".format(dispatcher_settings["service"]["name"],
                                              dispatcher_settings["roles"]["drivers"],
                                              dispatcher_settings["roles"]["executors"]))
            outfile.flush()


def get_default_options(arguments: dict) -> dict:
    options = {
        "service": {
            "cpus": int(arguments["--cpus"]),
            "mem": float(arguments["--mem"]),
            "log-level": arguments["--log-level"],
            "spark-history-server-url": arguments["--history-service"] or "",
            "UCR_containerizer": ast.literal_eval(arguments.get("--ucr-containerizer", True)),
            "use_bootstrap_for_IP_detect": False
        },
        "security": {
            "kerberos": {
                "enabled": ast.literal_eval(arguments.get("--enable-kerberos", False)),
                "kdc": {
                    "hostname": arguments["--kdc-hostname"] or "",
                    "port": int(arguments["--kdc-port"])
                },
                "realm": arguments["--kerberos-realm"] or ""
            }
        },
        "hdfs": {
            "config-url": arguments["--hdfs-config"] or ""
        }
    }
    return options


def get_quota_options(arguments: typing.Dict) -> typing.Dict:
    """
    Move the quota options from the command line arguments to a dict.
    """
    create_quotas = ast.literal_eval(arguments.get("--create-quotas", True))
    if not create_quotas:
        return {}

    resources = ["cpus", "mem", "gpus", ]
    targets = ["drivers", "executors", ]

    quota_options = {}
    for t in targets:
        quota_options[t] = {}
        for r in resources:
            arg_key = "--quota-{}-{}".format(t, r)
            if arg_key in arguments:
                quota_options[t][r] = arguments[arg_key]

    return quota_options


if __name__ == "__main__":
    arguments = docopt(__doc__, version="deploy-dispatchers.py 0.0")

    options_file = arguments['--options-json']
    if options_file:
        if not os.path.isfile(options_file):
            # TODO: Replace with logging
            log.error("The specified file does not exist: %s", options_file)
            sys.exit(1)

        options = json.load(open(options_file, 'r'))
    else:
        options = get_default_options(arguments)


    if arguments['--package-repo']:
        sdk_repository.add_stub_universe_urls([arguments['--package-repo']])

    quota_options = get_quota_options(arguments)

    deploy_dispatchers(
        num_dispatchers=int(arguments['<num_dispatchers>']),
        service_name_base=arguments['<service_name_base>'],
        output_file=arguments['<output_file>'],
        linux_user=arguments["--user"],
        options=options,
        quota_options=quota_options)
