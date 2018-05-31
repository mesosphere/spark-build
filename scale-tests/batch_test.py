#!/usr/bin/env python3

"""batch_test.py

Usage:
    batch_test.py <dispatcher_file> [options]

Arguments:
    dispatcher_file             file path to dispatchers list

Options:
    --docker-image <img>                              docker image to run on executors
    --max-num-dispatchers <n>                         maximum number of dispatchers to use from dispatchers file
    --submits-per-min <n>                             number of jobs to submit per minute [default: 1]
    --spark-cores-max <n>                             max executor cores per job [default: 1]
    --spark-executor-cores <n>                        number of cores per executor [default: 1]
    --spark-port-max-retries <n>                      num of retries to find a driver UI port [default: 64]
    --spark-mesos-driver-failover-timeout <seconds>   driver failover timeout in seconds [default: 30]
    --spark-mesos-containerizer <containerizer>       containerizer for each driver [default: mesos]
    --spark-mesos-driver-labels <labels>              task labels to attach to each driver
    --spark-mesos-executor-gpus <n>                   number of gpus per executor
    --spark-mesos-max-gpus <n>                        max gpus per job
    --no-supervise                                    disable supervise mode
"""


import json
import logging
import random
import sys
import time
from docopt import docopt
from threading import Thread
import typing

import sdk_utils
import spark_utils


# This script will submit jobs at a specified submit rate, alternating among the given
# set of dispatchers.
#
# Running:
# > dcos cluster setup <cluster url>
# > export PYTHONPATH=../spark-testing:../testing
# > python deploy-dispatchers.py 1 myspark dispatchers.txt
# > python batch_test.py dispatchers.txt


logging.basicConfig(
    format='[%(asctime)s|%(name)s|%(levelname)s]: %(message)s',
    level=logging.INFO,
    stream=sys.stdout)

log = logging.getLogger(__name__)
MONTE_CARLO_APP_URL = "http://xhuynh-dev.s3.amazonaws.com/monte-carlo-portfolio.py"
GPU_IMAGE_RECOGNITION_APP_URL = "https://svt-dev.s3.amazonaws.com/run_image_recognition-final.py"


def _get_duration() -> int:
    """
    Randomly choose among a set of job durations in minutes according to a distribution.
    The average job duration is one hour.
    """
    rand = random.random()
    if rand < 0.239583:
        duration = 15
    elif rand < 0.479166:
        duration = 105
    elif rand < 0.979166:
        duration = 30
    else:
        duration = 720
    return duration


def submit_job(app_url: str, dispatcher: typing.Dict, duration: int, config: typing.List[str]):
    dispatcher_name = dispatcher["service"]["name"]
    log.info("Submitting job to dispatcher: %s, with duration: %s min.", dispatcher_name, duration)

    app_args = "100000 {}".format(str(duration * 30))  # about 30 iterations per min.

    if dispatcher["service"].get("service_account") is not None:  # only defined in strict mode
        spark_utils.submit_job(
            service_name=dispatcher_name,
            app_url=app_url,
            app_args=app_args,
            verbose=False,
            args=config,
            driver_role=dispatcher["roles"]["executors"],
            spark_user=dispatcher["service"]["user"],
            principal=dispatcher["service"]["service_account"])
    else:
        spark_utils.submit_job(
            service_name=dispatcher_name,
            app_url=app_url,
            app_args=app_args,
            verbose=False,
            args=config,
            driver_role=dispatcher["roles"]["executors"])


def submit_loop(app_url: str, submits_per_min: int, dispatchers: typing.List[typing.Dict], user_conf: typing.List[str]):
    sec_between_submits = 60 / submits_per_min
    log.info("sec_between_submits: %s", sec_between_submits)
    num_dispatchers = len(dispatchers)
    log.info("num_dispatchers: %s", num_dispatchers)

    dispatcher_index = 0
    while(True):
        duration = _get_duration()
        t = Thread(target=submit_job, args=(app_url, dispatchers[dispatcher_index], duration, user_conf))
        t.start()
        dispatcher_index = (dispatcher_index + 1) % num_dispatchers
        log.info("sleeping %s sec.", sec_between_submits)
        time.sleep(sec_between_submits)


if __name__ == "__main__":
    args = docopt(__doc__)

    dispatchers = []
    with open(args["<dispatcher_file>"]) as f:
        data = json.load(f)
        dispatchers = data["spark"]

    user_conf = ["--conf", "spark.cores.max={}".format(args["--spark-cores-max"]),
                 "--conf", "spark.executor.cores={}".format(args["--spark-executor-cores"]),
                 "--conf", "spark.mesos.containerizer={}".format(args["--spark-mesos-containerizer"]),
                 "--conf", "spark.port.maxRetries={}".format(args["--spark-port-max-retries"]),
                 "--conf", "spark.mesos.driver.failoverTimeout={}".format(args["--spark-mesos-driver-failover-timeout"])
                ]

    if args["--spark-mesos-executor-gpus"]:
        MEMORY_MULTIPLIER = 20
        memory = int(args["--spark-mesos-executor-gpus"]) * MEMORY_MULTIPLIER
        user_conf += ["--conf", "spark.driver.memory={}g".format(str(memory)),
                      "--conf", "spark.executor.memory={}g".format(str(memory)),
                      "--conf", "spark.mesos.gpus.max={}".format(args["--spark-mesos-max-gpus"]),
                      "--conf", "spark.mesos.executor.gpus={}".format(args["--spark-mesos-executor-gpus"]),
                      "--conf", "spark.mesos.executor.docker.image={}".format(args["--docker-image"]),
                      "--conf", "spark.mesos.executor.docker.forcePullImage=false"
                      ]
        app_url = GPU_IMAGE_RECOGNITION_APP_URL
    else:
        app_url = MONTE_CARLO_APP_URL

    if args["--spark-mesos-driver-labels"] is not None:
        user_conf += ["--conf", "spark.mesos.driver.labels={}".format(args["--spark-mesos-driver-labels"])]

    if not args["--no-supervise"]:
        user_conf += ["--supervise"]

    if args["--max-num-dispatchers"]:
        end = int(args["--max-num-dispatchers"])
        dispatchers = dispatchers[0:end]

    submit_loop(app_url, int(args["--submits-per-min"]), dispatchers, user_conf)
