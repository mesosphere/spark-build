import csv
import random
import sys
import time
import spark_utils as utils
from threading import Thread

MONTE_CARLO_APP_URL = "http://xhuynh-dev.s3.amazonaws.com/monte-carlo-portfolio.py"


# Inputs:
# - File containing a list of dispatcher service names, one per line
# - Launch rate per min.
#
# This job will submit jobs at the specified launch rate, alternating among the given
# set of dispatchers.
#
# Running:
# > dcos cluster setup <cluster url>
# > dcos package install spark ... # Install one or more dispatchers
# > export PYTHONPATH=../spark-testing:../testing
# > python scale_test.py /tmp/dispatchers.txt 6


def _get_duration():
    """
    Randomly choose among a set of job durations, according to a distribution.
    The average job duration is one hour.
    """
    rand = random.random()
    if rand < 0.239583:
        duration = 450 # 15 min
    elif rand < 0.479166:
        duration = 3150 # 105 min
    elif rand < 0.979166:
        duration = 900 # 30 min
    else:
        duration = 21600 # 12 hr
    return duration


def submit_job(dispatcher, duration):
    print("T dispatcher: {}".format(dispatcher))
    dispatcher_name, dispatcher_role, driver_role = dispatcher
    print("duration: {}".format(str(duration)))

    args = ["--conf", "spark.cores.max=4",
            "--conf", "spark.executor.cores=1",
            "--conf", "spark.mesos.containerizer=mesos",
            "--conf", "spark.mesos.executor.docker.image=mesosphere/spark-dev:fea8e635e369596fb521e3aa140faecdbb0cacd0-5879a4ecf7d9a3781c70f3cdec64acff4f770e73",
            # use Hector's image
            "--conf", "spark.port.maxRetries=64",  # setting to allow up to 32 drivers on same node
            #"--conf", "spark.mesos.driverEnv.SPARK_USER=root", # Run as root on centos
            "--supervise",
            #"--conf", "spark.mesos.rejectOfferDuration=1000s",
            "--conf", "spark.mesos.driver.failoverTimeout=30",
            "--conf", "spark.mesos.task.labels=jpmc_test_id:spark_batch_run001"
            ]

    app_args = "100000 {}".format(str(duration))

    utils.submit_job(
        app_name="/{}".format(dispatcher_name),
        app_url=MONTE_CARLO_APP_URL,
        app_args=app_args,
        verbose=False,
        args=args,
        driver_role=driver_role)


def submit_loop(launch_rate_per_min, dispatchers):
    print("dispatchers: {}".format(dispatchers))
    sec_between_submits = 60 / launch_rate_per_min
    print("sec_between_submits: {}".format(sec_between_submits))
    num_dispatchers = len(dispatchers)
    print("num_dispatchers: {}".format(num_dispatchers))

    dispatcher_index = 0
    while(True):
        print("dispatchers[index]: {}".format(dispatchers[dispatcher_index]))
        duration = _get_duration()
        t = Thread(target=submit_job, args=(dispatchers[dispatcher_index], duration))
        t.start()
        dispatcher_index = (dispatcher_index + 1) % num_dispatchers
        print("sleeping {} sec.".format(sec_between_submits))
        time.sleep(sec_between_submits)


if __name__ == "__main__":
    usage = """
        Setup: export PYTHONPATH=../spark-testing:../testing
        Usage: python scale_test.py [dispatchers_file] [launch_rate_per_min]
    """

    if len(sys.argv) < 3:
        print(usage)
        sys.exit(2)

    dispatchers = []

    dispatchers_file = sys.argv[1]
    print("dispatchers_file: {}".format(dispatchers_file))
    with open(dispatchers_file) as f:
        infile = csv.reader(f, delimiter=',')
        for row in infile: dispatchers.append(row)
    print("dispatchers: {}".format(dispatchers))

    launch_rate_per_min = int(sys.argv[2])
    print("launch_rate_per_min: {}".format(launch_rate_per_min))

    submit_loop(launch_rate_per_min, dispatchers)
