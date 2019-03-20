import logging

import pytest
import retrying
import sdk_cmd
import sdk_tasks
import shakedown
import spark_utils as utils

log = logging.getLogger(__name__)


@pytest.fixture(scope='module', autouse=True)
def setup_spark(configure_security_spark, configure_universe):
    try:
        utils.upload_dcos_test_jar()
        utils.require_spark()
        yield
    finally:
        utils.teardown_spark()


# StatsD metrics require Mesos UCR, so no tests for Docker
@pytest.mark.sanity
@pytest.mark.parametrize('use_overlay', [
    False,
    True
])
def test_driver_metrics(use_overlay):
    @retrying.retry(
        wait_fixed=5000,
        stop_max_delay=600 * 1000,
        retry_on_result=lambda res: not res)
    def wait_for_metric(task_id, expected_metric_name):
        stdout = sdk_cmd.run_cli("task metrics details {}".format(task_id))
        result = expected_metric_name in stdout
        log.info('Checking for {} in STDOUT:\n{}\nResult: {}'.format(expected_metric_name, stdout, result))
        return result

    app_name = "MockTaskRunner"

    submit_args = ["--conf spark.cores.max=1",
                   "--conf spark.mesos.containerizer=mesos",
                   "--class {}".format(app_name)]

    if use_overlay:
        submit_args = submit_args + [
            "--conf spark.mesos.network.name=dcos",
            "--conf spark.mesos.driverEnv.VIRTUAL_NETWORK_ENABLED=true",
            "--conf spark.executorEnv.VIRTUAL_NETWORK_ENABLED=true"
        ]

    expected_metric = "jvm.heap.used"

    driver_id = utils.submit_job(app_url=utils.dcos_test_jar_url(),
                                 app_args="1 300",
                                 args=submit_args)
    wait_for_metric(driver_id, expected_metric)

    sdk_tasks.check_running(app_name, 1, timeout_seconds=600)
    executor_id = shakedown.get_service_task_ids(app_name)[0]
    wait_for_metric(executor_id, expected_metric)
