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
    --docker-image <image>       custom Docker image to use
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
    --role <role>                Mesos role registered by dispatcher [default: *]
    --service-account <account>  Mesos principal registered by dispatcher
    --service-secret <secret>    Mesos secret registered by dispatcher
    --ucr-containerizer <bool>   launch using the Universal Container Runtime [default: True]
    --user <user>                user to run dispatcher service as [default: root]

"""

from docopt import docopt

import ast
import shakedown
import sys


# This script will deploy the specified number of dispatchers with an optional
# options json file. It will take the given base service name and
# append an index to generate a unique service name for each dispatcher.
#
# The service names of the deployed dispatchers will be written into an output
# file.


def deploy_dispatchers(
    num_dispatchers,
    service_name_base,
    output_file,
    options,
    options_file=None
):
    with open(output_file, "w") as outfile:
        for i in range(0, num_dispatchers):
            service_name = "{}-{}".format(service_name_base, str(i))

            if options_file is not None:
                shakedown.install_package(
                    package_name=arguments['--package-name'],
                    service_name=service_name,
                    options_file=options_file)
            else:
                shakedown.install_package(
                    package_name=arguments['--package-name'],
                    service_name=service_name,
                    options_json=options)

            outfile.write("{}\n".format(service_name))


if __name__ == "__main__":
    arguments = docopt(__doc__, version="deploy-dispatchers.py 0.0")

    options={
        "service": {
            "cpus": int(arguments["--cpus"]),
            "mem": float(arguments["--mem"]),
            "role": arguments["--role"],
            "service_account": arguments["--service-account"] or "",
            "service_account_secret": arguments["--service-secret"] or "",
            "user": arguments["--user"],
            "docker-image": arguments['--docker-image'] or "mesosphere/spark-dev:931ca56273af913d103718376e2fbc04be7cbde0",
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

    deploy_dispatchers(
        int(arguments['<num_dispatchers>']),
        arguments['<service_name_base>'],
        arguments['<output_file>'],
        options,
        arguments['--options-json'])
