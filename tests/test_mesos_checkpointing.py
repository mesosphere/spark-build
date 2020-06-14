import logging

import pytest
import sdk_cmd
import sdk_networks
import sdk_tasks
import shakedown
import spark_utils as utils

log = logging.getLogger(__name__)

app_name = "MockTaskRunner"
driver_cpus = None
executor_cpus = None


@pytest.fixture(scope='module', autouse=True)
def setup_spark(configure_security_spark, configure_universe):
    try:
        utils.upload_dcos_test_jar()
        utils.require_spark()

        # We need to pick two nodes with the maximum unused CPU to guarantee that Driver and Executor
        # are not running on the same host.
        available_cpus = []
        cluster_agents = sdk_cmd.cluster_request('GET', '/mesos/slaves').json()
        for agent in cluster_agents["slaves"]:
            available_cpus.append(int(float(agent["resources"]["cpus"])) - int(float(agent["used_resources"]["cpus"])))

        available_cpus.sort(reverse=True)
        assert len(available_cpus) >= 3, \
            "Expected 3 or more nodes in the cluster to accommodate Dispatcher, " \
            "Driver, and Executor each on a separate node"

        global driver_cpus
        driver_cpus = available_cpus[0]

        global executor_cpus
        executor_cpus = available_cpus[1]

        log.info(f"{driver_cpus} cores will be used for driver, {executor_cpus} cores will be used for executor")
        yield
    finally:
        utils.teardown_spark()


@pytest.mark.sanity
def test_agent_restart_with_checkpointing_disabled():
    (driver_task_id, driver_task, executor_task) = _submit_job_and_get_tasks()

    driver_ip = sdk_networks.get_task_host(driver_task)
    executor_ip = sdk_networks.get_task_host(executor_task)

    # Dispatcher starts Driver Tasks with checkpointing enabled so Driver is expected to be in RUNNING state
    utils.restart_task_agent_and_verify_state(driver_ip, driver_task, "TASK_RUNNING")
    utils.restart_task_agent_and_verify_state(executor_ip, executor_task, "TASK_LOST")

    _kill_driver_task(driver_task_id)


@pytest.mark.sanity
def test_agent_restart_with_checkpointing_enabled():
    (driver_task_id, driver_task, executor_task) = _submit_job_and_get_tasks(extra_args=["--conf spark.mesos.checkpoint=true"])

    driver_ip = sdk_networks.get_task_host(driver_task)
    executor_ip = sdk_networks.get_task_host(executor_task)

    utils.restart_task_agent_and_verify_state(executor_ip, executor_task, "TASK_RUNNING")
    utils.restart_task_agent_and_verify_state(driver_ip, driver_task, "TASK_RUNNING")

    _kill_driver_task(driver_task_id)


def _submit_job_and_get_tasks(extra_args=[]):
    submit_args = ["--conf spark.driver.cores={}".format(driver_cpus),
                   "--conf spark.cores.max={}".format(executor_cpus),
                   "--conf spark.executor.cores={}".format(executor_cpus),
                   "--class {}".format(app_name)
                   ] + extra_args

    driver_task_id = utils.submit_job(app_url=utils.dcos_test_jar_url(),
                                      app_args="1 600",
                                      args=submit_args)

    sdk_tasks.check_running(app_name, 1, timeout_seconds=300)
    driver_task = shakedown.get_task(driver_task_id, completed=False)
    executor_task = shakedown.get_service_tasks(app_name)[0]

    return (driver_task_id, driver_task, executor_task)


def _kill_driver_task(driver_task_id):
    log.info(f"Cleaning up. Attempting to kill driver: {driver_task_id}")
    utils.kill_driver(driver_task_id)
