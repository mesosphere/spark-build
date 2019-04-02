import logging

import dcos_utils
import pytest
import retrying
import sdk_cmd
import sdk_networks
import sdk_tasks
import shakedown
import spark_utils as utils

log = logging.getLogger(__name__)

start_agent_cmd = "sudo systemctl start dcos-mesos-slave"
stop_agent_cmd = "sudo systemctl stop dcos-mesos-slave"
check_agent_cmd = "sudo systemctl is-active dcos-mesos-slave"

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
    (driver_task, executor_task) = next(_submit_job_and_get_tasks())

    driver_ip = sdk_networks.get_task_host(driver_task)
    executor_ip = sdk_networks.get_task_host(executor_task)

    # Dispatcher starts Driver Tasks with checkpointing enabled so Driver is expected to be in RUNNING state
    _restart_task_agent_and_verify_state(driver_ip, driver_task, "TASK_RUNNING")
    _restart_task_agent_and_verify_state(executor_ip, executor_task, "TASK_LOST")


@pytest.mark.sanity
def test_agent_restart_with_checkpointing_enabled():
    (driver_task, executor_task) = next(_submit_job_and_get_tasks(extra_args=["--conf spark.mesos.checkpoint=true"]))

    driver_ip = sdk_networks.get_task_host(driver_task)
    executor_ip = sdk_networks.get_task_host(executor_task)

    _restart_task_agent_and_verify_state(executor_ip, executor_task, "TASK_RUNNING")
    _restart_task_agent_and_verify_state(driver_ip, driver_task, "TASK_RUNNING")


def _restart_task_agent_and_verify_state(host_ip, task, expected_state):
    dcos_utils.agent_ssh(host_ip, stop_agent_cmd)
    _check_agent_status(host_ip, "inactive")
    dcos_utils.agent_ssh(host_ip, start_agent_cmd)
    _check_agent_status(host_ip, "active")
    _wait_for_task_status(task["id"], expected_state)


@retrying.retry(
        wait_fixed=5000,
        stop_max_delay=120 * 1000,
        retry_on_result=lambda res: not res)
def _check_agent_status(host_ip, expected_status):
    status = dcos_utils.agent_ssh(host_ip, check_agent_cmd)
    log.info(f"Checking status of agent at host {host_ip}, expected: {expected_status}, actual: {status}")
    return expected_status == status


@retrying.retry(
        wait_fixed=5000,
        stop_max_delay=120 * 1000,
        retry_on_result=lambda res: not res)
def _wait_for_task_status(task_id, expected_state):
    completed = expected_state != "TASK_RUNNING"
    task = shakedown.get_task(task_id, completed=completed)
    assert task is not None
    log.info(f"Checking task state for '{task_id}', expected: {expected_state}, actual: {task['state']}")
    return expected_state == task["state"]


def _submit_job_and_get_tasks(extra_args=[]):
    submit_args = ["--conf spark.driver.cores={}".format(driver_cpus),
                   "--conf spark.cores.max={}".format(executor_cpus),
                   "--conf spark.executor.cores={}".format(executor_cpus),
                   "--class {}".format(app_name)
                   ] + extra_args

    driver_task_id = utils.submit_job(app_url=utils.dcos_test_jar_url(),
                                      app_args="1 600",
                                      args=submit_args)
    try:
        sdk_tasks.check_running(app_name, 1, timeout_seconds=300)
        driver_task = shakedown.get_task(driver_task_id, completed=False)
        executor_task = shakedown.get_service_tasks(app_name)[0]

        yield (driver_task, executor_task)

    finally:
        log.info(f"Cleaning up. Attempting to kill driver: {driver_task_id}")
        utils.kill_driver(driver_task_id)
