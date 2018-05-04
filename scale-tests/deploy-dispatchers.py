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
    --package-repo <url>         URL of the Spark package repo to install from
    --quota-dispatcher-cpus <n>  number of CPUs to use for dispatcher quota [default: 1]
    --quota-dispatcher-gpus <n>  number of GPUs to use for dispatcher quota [default: 0]
    --quota-dispatcher-mem <n>   amount of memory (mb) to use per dispatcher quota [default: 2048.0]
    --quota-driver-cpus <n>      number of CPUs to use for driver quota [default: 1]
    --quota-driver-gpus <n>      number of GPUs to use for driver quota [default: 0]
    --quota-driver-mem <n>       amount of memory (mb) to use per driver quota [default: 1524.0]
    --role <role>                Mesos role registered by dispatcher [default: *]
    --service-account <account>  Mesos principal registered by dispatcher
    --service-secret <secret>    Mesos secret registered by dispatcher
    --ucr-containerizer <bool>   launch using the Universal Container Runtime [default: True]
    --user <user>                user to run dispatcher service as [default: root]

"""

from docopt import docopt

import ast
import contextlib
import json
import shakedown
import sys


# This script will deploy the specified number of dispatchers with an optional
# options json file. It will take the given base service name and
# append an index to generate a unique service name for each dispatcher.
#
# The service names of the deployed dispatchers will be written into an output
# file.


class DummyFile(object):
    def write(self, x): pass


@contextlib.contextmanager
def no_stdout():
    save_stdout = sys.stdout
    sys.stdout = DummyFile()
    yield
    sys.stdout = save_stdout


def create_quota(
    name,
    cpus=1,
    gpus=0,
    mem=1024.0
):
    with no_stdout():
        stdout, stderr, return_code = shakedown.run_dcos_command("spark quota list --json")
        existing_quotas = json.loads(stdout)

    # remove existing quotas matching name
    if name in [x['role'] for x in existing_quotas['infos']]:
        shakedown.run_dcos_command("spark quota remove {}".format(name))

    # create quota
    stdout, stderr, return_code = shakedown.run_dcos_command(
        "spark quota create -c {} -g {} -m {} {}".format(cpus, gpus, mem, name))


def deploy_dispatchers(
    num_dispatchers,
    service_name_base,
    output_file,
    options,
    options_file=None,
    package_repo=None,
    quota_dispatcher_cpus=1,
    quota_dispatcher_gpus=0,
    quota_dispatcher_mem=2048.0,
    quota_driver_cpus=1,
    quota_driver_gpus=0,
    quota_driver_mem=1024.0
):
    with open(output_file, "w") as outfile:
        shakedown.run_dcos_command("package install spark --cli --yes")

        for i in range(0, num_dispatchers):
            service_name = "{}-{}".format(service_name_base, str(i))

            # set service name
            options["service"]["name"] = service_name

            if package_repo is not None:
                if package_repo not in [x['uri'] for x in shakedown.get_package_repos()['repositories']]:
                    shakedown.add_package_repo(
                        repo_name="{}-repo".format(service_name_base),
                        repo_url=package_repo)

            # create dispatcher & driver role quotas
            dispatcher_role = "{}-dispatcher-role".format(service_name)
            create_quota(name=dispatcher_role,
		cpus=quota_dispatcher_cpus, gpus=quota_dispatcher_gpus, mem=quota_dispatcher_mem)
            driver_role = "{}-driver-role".format(service_name)
            create_quota(name=driver_role,
		cpus=quota_driver_cpus, gpus=quota_driver_gpus, mem=quota_driver_mem)

            # install dispatcher with appropriate role
            options["service"]["role"] = dispatcher_role

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

            outfile.write("{},{},{}\n".format(service_name, dispatcher_role, driver_role))


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
        num_dispatchers=int(arguments['<num_dispatchers>']),
        service_name_base=arguments['<service_name_base>'],
        output_file=arguments['<output_file>'],
        options=options,
        options_file=arguments['--options-json'],
        package_repo=arguments['--package-repo'],
        quota_dispatcher_cpus=arguments['--quota-dispatcher-cpus'],
        quota_dispatcher_gpus=arguments['--quota-dispatcher-gpus'],
        quota_dispatcher_mem=arguments['--quota-dispatcher-mem'],
        quota_driver_cpus=arguments['--quota-driver-cpus'],
        quota_driver_gpus=arguments['--quota-driver-gpus'],
        quota_driver_mem=arguments['--quota-driver-mem'])
