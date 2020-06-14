import logging

import pytest

import sdk_tasks
import shakedown
import sdk_networks
import spark_utils as utils

log = logging.getLogger(__name__)

# The debug messages we will be looking for in driver stderr
OFFER_SUPPRESS_LOG_MSG = "Suppressing further offers\."
OFFER_RECEIVED_LOG_MSG = "Received \d resource offers\."
OFFER_REVIVIED_LOG_MSG = "Reviving offers due to a failed executor task."


def setup_module(module):
    utils.upload_dcos_test_jar()
    utils.require_spark()


def teardown_module(module):
    utils.teardown_spark()


@pytest.mark.sanity
@pytest.mark.smoke
def test_offers_suppressed():
    driver_task_id = _launch_test_task("MockTaskRunner")
    shakedown.wait_for_task_completion(driver_task_id, timeout_sec=utils.JOB_WAIT_TIMEOUT_SECONDS)
    _check_logged_offers(driver_task_id, 0)


@pytest.mark.sanity
@pytest.mark.smoke
def test_offers_suppressed_with_lost_task():
    app_name = "MockTaskRunner"
    driver_task_id = _launch_test_task(app_name)
    executor_task = shakedown.get_service_tasks(app_name)[0]
    executor_ip = sdk_networks.get_task_host(executor_task)

    utils.restart_task_agent_and_verify_state(executor_ip, executor_task, "TASK_LOST")

    shakedown.wait_for_task_completion(driver_task_id, timeout_sec=utils.JOB_WAIT_TIMEOUT_SECONDS)
    _check_logged_offers(driver_task_id, 1)


def _launch_test_task(app_name):
    log.info('Submitting a Spark Applications with 1 executor')

    driver_task_id = utils.submit_job(app_url=utils.dcos_test_jar_url(),
                                      app_args="1 5",
                                      args=["--conf spark.cores.max=1",
                                            "--conf spark.executor.cores=1",
                                            "--conf spark.mesos.containerizer=mesos",
                                            "--conf spark.mesos.rejectOfferDuration=1s",
                                            f"--conf spark.mesos.executor.docker.image={utils.SPARK_DOCKER_IMAGE}",
                                            f"--class {app_name}"
                                            ])
    sdk_tasks.check_running(app_name, 1, timeout_seconds=300)
    return driver_task_id


# Looks through the driver log and checks that no resource offers were logged between a pair of suppress and revive calls
def _check_logged_offers(task_id, expected_revive_count):
    log_matches = utils.log_matches(task_id, "stderr", [OFFER_SUPPRESS_LOG_MSG, OFFER_RECEIVED_LOG_MSG, OFFER_REVIVIED_LOG_MSG])

    suppress_line_numbers = log_matches[OFFER_SUPPRESS_LOG_MSG]
    revive_line_numbers = log_matches[OFFER_REVIVIED_LOG_MSG]
    received_line_numbers = log_matches[OFFER_RECEIVED_LOG_MSG]
    log.info(f"suppresses = {suppress_line_numbers}")
    log.info(f"revives = {revive_line_numbers}")
    log.info(f"offers = {received_line_numbers}")

    assert suppress_line_numbers
    assert len(revive_line_numbers) == expected_revive_count

    for suppressed_line in suppress_line_numbers:
        # find if there are revive point after this line
        next_revive_points = [l for l in revive_line_numbers if l > suppressed_line]

        # if there were no revives later make sure there are no offers as well
        if len(next_revive_points) <= 0:
            assert len([l for l in received_line_numbers if l > suppressed_line]) == 0
        else: # else check that there are no offers in between
            assert len([l for l in received_line_numbers if suppressed_line < l < next_revive_points[0]]) == 0
