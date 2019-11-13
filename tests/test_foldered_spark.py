import logging

import pytest
import retrying

import sdk_cmd
import sdk_hosts
import sdk_utils

import spark_utils as utils

log = logging.getLogger(__name__)

service_name = utils.FOLDERED_SPARK_SERVICE_NAME
driver_role = service_name.lstrip('/').split('/')[0]


@pytest.fixture(scope='module', autouse=True)
def upload_test_jars(configure_security_spark, configure_universe):
    utils.upload_dcos_test_jar()


@pytest.fixture(scope='module')
def configure_role_permissions(configure_security_spark):
    try:
        if sdk_utils.is_strict_mode():
            utils.grant_user_permissions("nobody", driver_role, utils.SPARK_SERVICE_ACCOUNT)
            utils.grant_launch_task_permission(service_name)
        yield
    finally:
        if sdk_utils.is_strict_mode():
            utils.revoke_user_permissions("nobody", driver_role, utils.SPARK_SERVICE_ACCOUNT)
            utils.revoke_launch_task_permission(service_name)


@pytest.fixture()
def setup_spark(configure_universe, configure_role_permissions):
    try:
        utils.require_spark()
        zk = 'spark_mesos_dispatcher__path_to_spark'
        utils.require_spark(service_name=service_name, zk=zk)
        yield
    finally:
        utils.teardown_spark(service_name=service_name, zk=zk)


@pytest.mark.dcos_min_version('1.10')
@pytest.mark.sanity
@pytest.mark.smoke
def test_foldered_spark(setup_spark):
    utils.run_tests(
        app_url=utils.SPARK_EXAMPLES,
        app_args="100",
        expected_output="Pi is roughly 3",
        service_name=service_name,
        driver_role=driver_role,
        args=["--class org.apache.spark.examples.SparkPi"])


@pytest.mark.sanity
def test_dispatcher_task_stdout(setup_spark):
    task_id = service_name.lstrip("/").replace("/", "_")
    task = sdk_cmd._get_task_info(task_id)
    if not task:
        raise Exception("Failed to get '{}' task".format(task_id))

    task_sandbox_path = sdk_cmd.get_task_sandbox_path(task_id)
    if not task_sandbox_path:
        raise Exception("Failed to get '{}' sandbox path".format(task_id))
    agent_id = task["slave_id"]

    task_sandbox = sdk_cmd.cluster_request(
        "GET", "/slave/{}/files/browse?path={}".format(agent_id, task_sandbox_path)
    ).json()
    stdout_file = [f for f in task_sandbox if f["path"].endswith("/stdout")][0]
    assert stdout_file["size"] > 0, "stdout file should have content"


@pytest.mark.sanity
def test_unique_vips():

    @retrying.retry(wait_exponential_multiplier=1000, stop_max_attempt_number=7) # ~2 minutes
    def verify_ip_is_reachable(ip):
        ok, _ = sdk_cmd.master_ssh("curl -v {}".format(ip))
        assert ok

    spark1_service_name = "test/groupa/spark"
    spark2_service_name = "test/groupb/spark"
    try:
        utils.require_spark(spark1_service_name)
        utils.require_spark(spark2_service_name)

        dispatcher1_ui_ip = sdk_hosts.vip_host("marathon", "dispatcher.{}".format(spark1_service_name), 4040)
        dispatcher2_ui_ip = sdk_hosts.vip_host("marathon", "dispatcher.{}".format(spark2_service_name), 4040)

        verify_ip_is_reachable(dispatcher1_ui_ip)
        verify_ip_is_reachable(dispatcher2_ui_ip)
    finally:
        utils.teardown_spark(service_name=spark1_service_name)
        utils.teardown_spark(service_name=spark2_service_name)
