import logging
import os
import pytest
import re
import shakedown
import time

import spark_utils as utils

import sdk_tasks

LOGGER = logging.getLogger(__name__)
THIS_DIR = os.path.dirname(os.path.abspath(__file__))
LONG_RUNNING_FW_NAME = "Long-Running Spark Job"
LONG_RUNNING_FW_NUM_TASKS = 1
MASTER_CONNECTION_TIMEOUT_SEC = 15 * 60
LONG_RUNNING_RUN_TIME_SEC = MASTER_CONNECTION_TIMEOUT_SEC + (15 * 60)


def setup_module(module):
    utils.require_spark()


def teardown_module(module):
    utils.teardown_spark()


@pytest.mark.recovery
def test_disconnect_from_master():
    python_script_path = os.path.join(THIS_DIR, 'jobs', 'python', 'long_running.py')
    python_script_url = utils.upload_file(python_script_path)
    task_id = utils.submit_job(python_script_url,
                    "{} {}".format(LONG_RUNNING_FW_NUM_TASKS, LONG_RUNNING_RUN_TIME_SEC),
                    ["--conf", "spark.mesos.driver.failoverTimeout=1800",
                     "--conf", "spark.cores.max=1"])

    # Wait until executor is running
    sdk_tasks.check_running(LONG_RUNNING_FW_NAME, LONG_RUNNING_FW_NUM_TASKS, timeout_seconds=600)

    # Block the driver's connection to Mesos master
    framework_info = shakedown.get_service(LONG_RUNNING_FW_NAME)
    (driver_host, port) = _parse_fw_pid_host_port(framework_info["pid"])
    _block_master_connection(driver_host, port)

    # The connection will timeout after 15 minutes of inactivity.
    # Add 5 minutes to make sure the master has detected the disconnection.
    # The framework will be considered disconnected => failover_timeout kicks in.
    LOGGER.info("Waiting {} seconds for connection with master to timeout...".format(MASTER_CONNECTION_TIMEOUT_SEC))
    time.sleep(MASTER_CONNECTION_TIMEOUT_SEC + 5 * 60)

    # Restore the connection. The driver should reconnect.
    _unblock_master_connection(driver_host)

    # The executor and driver should finish.
    utils.check_job_output(task_id, "Job completed successfully")

    # Due to https://issues.apache.org/jira/browse/MESOS-5180, the driver does not re-register, so
    # teardown won't occur until the failover_timeout period ends. The framework remains "Inactive".
    # Uncomment when the bug is fixed:
    #                           The framework is not Active or Inactive
    #shakedown.wait_for(lambda: shakedown.get_service(fw_name, True) is None,
    #                   ignore_exceptions=False,
    #                   timeout_seconds=timeout_seconds)


def _parse_fw_pid_host_port(pid):
    # Framework pid looks like: "scheduler-cd28f2eb-3aec-4060-a731-f5be1f5186c4@10.0.1.7:37085"
    regex = r"([^@]+)@([^:]+):(\d+)"
    match = re.search(regex, pid)
    return match.group(2), int(match.group(3))


def _block_master_connection(host, port):
    LOGGER.info("Blocking connection with master")
    shakedown.network.save_iptables(host)
    # Reject incoming packets from master
    shakedown.network.run_iptables(host, '-I INPUT -p tcp --dport {} -j REJECT'.format(port))


def _unblock_master_connection(host):
    LOGGER.info("Unblocking connection with master")
    shakedown.network.restore_iptables(host)
