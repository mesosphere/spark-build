import os
import pytest

import shakedown

from tests import utils


# Prerequisites
#   * Cluster with two 1-GPU nodes, one CPU-only node.
#   * Docker image has CUDA 7.5 installed.


GPU_PI_APP_NAME = "GpuPiApp"


@pytest.fixture(scope='module')
def configure_security_spark():
    yield from utils.spark_security_session()


@pytest.fixture(scope='module', autouse=True)
def setup_spark(configure_security_spark, configure_universe):
    try:
        utils.require_spark(user="root",             # Run as root on centos
                            use_bootstrap_ip=True)   # Needed on GPU nodes
        utils.upload_file(os.environ["SCALA_TEST_JAR_PATH"])
        yield
    finally:
        utils.teardown_spark()


@pytest.mark.sanity
def test_executor_gpus_allocated():
    """
    Checks that the specified executor.gpus is allocated for each executor.
    """
    num_executors = 2
    driver_task_id = utils.submit_job(
        app_url=utils._scala_test_jar_url(),
        app_args="{} 1000000".format(num_executors), # Long enough to examine the Executor's task info
        args=["--conf", "spark.scheduler.maxRegisteredResourcesWaitingTime=240s",
            "--conf", "spark.scheduler.minRegisteredResourcesRatio=1.0",
            "--conf", "spark.executor.memory=2g",
            "--conf", "spark.mesos.gpus.max={}".format(num_executors),
            "--conf", "spark.mesos.executor.gpus=1",
            "--conf", "spark.executor.cores=1",
            "--conf", "spark.mesos.containerizer=mesos",
            "--conf", "spark.mesos.driverEnv.SPARK_USER=root", # Run as root on centos
            "--class", "GpuPiApp"])

    # Wait until executors are running
    utils.wait_for_executors_running(GPU_PI_APP_NAME, num_executors)

    # Check Executor gpus - should be 1.
    for i in range(0, num_executors):
        executor_task = shakedown.get_service_tasks(GPU_PI_APP_NAME)[i]
        assert executor_task['resources']['gpus'] == 1.0

    # Check job output
    utils.check_job_output(driver_task_id, "Pi calculated with GPUs: 3.14")
