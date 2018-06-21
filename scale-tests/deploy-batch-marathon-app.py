#!/usr/bin/env python3

"""deploy-batch-marathon-app.py

Usage:
    deploy-batch-marathon-app.py [options]

Arguments:

Options:
    --app-id <id>                 marathon app id [default: spark-batch-workload]
    --dcos-username <user>        DC/OS username
    --dcos-password <pass>        DC/OS password
    --input-file-uri <uri>        URI of script input file
    --script-cpus <n>             number of CPUs to use to run the script [default: 2]
    --script-mem <n>              amount of memory (mb) to use to run the script [default: 4096]
    --script-args <args>          args to pass to the script
    --security <mode>             strict or permissive [default: permissive]
    --spark-build-branch <branch> branch of spark build to run [default: master]

"""


import logging
import sys
import typing

import sdk_marathon

from docopt import docopt


logging.basicConfig(
    format='[%(asctime)s|%(name)s|%(levelname)s]: %(message)s',
    level=logging.INFO,
    stream=sys.stdout)

log = logging.getLogger(__name__)


def main(app_id: str, dcos_username: str, dcos_password: str, input_file_uri: str, script_cpus: int, script_mem: int,
         script_args: str, security: str, spark_build_branch: str):

    def _get_app_defn(app_id: str, dcos_username: str, dcos_password: str, input_file_uri: str, script_cpus: int,
                      script_mem: int, script_args: str, security: str, spark_build_branch: str) -> typing.Dict:
        """
        Construct the marathon app definition.
        """
        app_defn = {
            "id": app_id,
            "cmd": "cd $MESOS_SANDBOX; git clone https://github.com/mesosphere/spark-build.git; cd spark-build/; pwd; git checkout $SPARK_BUILD_BRANCH; python3 -m venv test-env; pip3 install -r scale-tests/requirements.txt; dcos cluster setup https://master.mesos --username=$DCOS_UID --password=$DCOS_PASSWORD --no-check; dcos package install spark --cli --yes; cd scale-tests/; export PYTHONPATH=../spark-testing:../testing; python3 batch_test.py $MESOS_SANDBOX/$SCRIPT_ARGS",
            "container": {
                "type": "DOCKER",
                "docker": {
                    "image": "susanxhuynh/dcos-commons:spark",
                }
            },
            "cpus": script_cpus,
            "mem": script_mem,
            "disk": 1024,
            "env": {
                "DCOS_UID": dcos_username,
                "DCOS_PASSWORD": dcos_password,
                "SCRIPT_ARGS": script_args.strip(),
                "SPARK_BUILD_BRANCH": spark_build_branch,
                "SECURITY": security
            },
            "fetch": [
                {
                    "uri": input_file_uri,
                }
            ]
        }
        return app_defn

    (success, err_msg) = sdk_marathon.install_app(_get_app_defn(app_id, dcos_username, dcos_password, input_file_uri,
                                                                script_cpus, script_mem, script_args, security,
                                                                spark_build_branch))
    assert success, err_msg


if __name__ == "__main__":
    args = docopt(__doc__)

    main(app_id=args["--app-id"],
         dcos_username=args["--dcos-username"],
         dcos_password=args["--dcos-password"],
         input_file_uri=args["--input-file-uri"],
         script_cpus=int(args["--script-cpus"]),
         script_mem=int(args["--script-mem"]),
         script_args=args["--script-args"],
         security=args["--security"],
         spark_build_branch=args["--spark-build-branch"])
