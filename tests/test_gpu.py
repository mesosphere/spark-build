import logging
import os
import pytest
import uuid

import shakedown
from shakedown.dcos.spinner import TimeoutExpired

import spark_utils


# Prerequisites
#   * Cluster with two 1-GPU nodes, one CPU-only node.
#   * Docker image has CUDA 7.5 installed.


log = logging.getLogger(__name__)
GPU_PI_APP_NAME = "GpuPiApp"


@pytest.fixture(scope='module')
def configure_security_spark():
    yield from spark_utils.spark_security_session()


@pytest.fixture(scope='module', autouse=True)
def setup_spark(configure_security_spark, configure_universe):
    try:
        spark_utils.require_spark(user="root",             # Run as root on centos
                                  use_bootstrap_ip=True)   # Needed on GPU nodes
        spark_utils.upload_file(os.environ["SCALA_TEST_JAR_PATH"])
        yield
    finally:
        spark_utils.teardown_spark()


def _submit_gpu_app(num_executors, executor_gpus, gpus_max, app_name=None):
    """
    Helper function to submit a gpu app.
    """
    args = ["--conf", "spark.scheduler.maxRegisteredResourcesWaitingTime=240s",
            "--conf", "spark.scheduler.minRegisteredResourcesRatio=1.0",
            "--conf", "spark.executor.memory=2g",
            "--conf", "spark.mesos.gpus.max={}".format(gpus_max),
            "--conf", "spark.executor.cores=1",
            "--conf", "spark.mesos.containerizer=mesos",
            "--conf", "spark.mesos.driverEnv.SPARK_USER=root", # Run as root on centos
            "--class", "GpuPiApp"]
    if executor_gpus is not None:
        args += ["--conf", "spark.mesos.executor.gpus={}".format(executor_gpus)]

    app_args = "{} 1000000".format(num_executors) # Long enough to examine the Executor's task info
    if app_name is not None:
        app_args += " {}".format(app_name)

    driver_task_id = spark_utils.submit_job(
        app_url=spark_utils.scala_test_jar_url(),
        app_args=app_args,
        args=args)
    return driver_task_id


@pytest.mark.gpus
def test_executor_gpus_allocated():
    """
    Checks that the specified executor.gpus is allocated for each executor.
    """
    num_executors = 2
    executor_gpus = 1
    driver_task_id = _submit_gpu_app(num_executors=num_executors,
                                     executor_gpus=executor_gpus,
                                     gpus_max=num_executors*executor_gpus)

    # Wait until executors are running
    spark_utils.wait_for_executors_running(GPU_PI_APP_NAME, num_executors)

    # Check Executor gpus - should be 1.
    for i in range(0, num_executors):
        executor_task = shakedown.get_service_tasks(GPU_PI_APP_NAME)[i]
        assert executor_task['resources']['gpus'] == 1.0

    # Check job output
    spark_utils.check_job_output(driver_task_id, "Pi calculated with GPUs: 3.14")


@pytest.mark.gpus
def test_executor_gpus_exceeds_available_gpus():
    """
    Checks: if executor.gpus exceeds the available gpus, the job never runs.
    """
    num_executors = 2
    executor_gpus = 2
    driver_task_id = _submit_gpu_app(num_executors=num_executors,
                                     executor_gpus=executor_gpus,
                                     gpus_max=num_executors*executor_gpus)
    try:
        log.info("Waiting for job to complete.")
        shakedown.wait_for_task_completion(driver_task_id, timeout_sec=240)
    except TimeoutExpired:
        log.info("Job failed to complete, as expected.")
        spark_utils.kill_driver(driver_task_id, spark_utils.SPARK_APP_NAME)
        return

    pytest.fail("Did not expect this job to complete.")


@pytest.mark.gpus
def test_gpus_max():
    """
    Checks that gpus.max is respected.
    """
    gpus_max = 1
    app_name = "{}-{}".format(GPU_PI_APP_NAME, str(uuid.uuid4()))
    driver_task_id = _submit_gpu_app(num_executors=1,
                                     executor_gpus=None,
                                     gpus_max=gpus_max,
                                     app_name=app_name)

    log.info("Waiting for job to complete.")
    shakedown.wait_for_task_completion(driver_task_id)

    # Check total Executor gpus <= gpus.max
    service = shakedown.get_service(service_name=app_name, completed=True)
    executor_tasks = service['completed_tasks']
    gpus = [task['resources']['gpus'] for task in executor_tasks]
    log.info("Task gpus: {}".format(str(gpus)))
    total_gpus = sum(gpus)
    log.info("Total gpus allocated: {}".format(str(total_gpus)))
    # We expect total gpus == gpus.max because gpus are allocated greedily.
    assert total_gpus == gpus_max
