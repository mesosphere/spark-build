import ipaddress
import json
import logging
import os

import pytest
import retrying
import sdk_cmd
import sdk_install
import sdk_tasks
import sdk_utils
import shakedown
import spark_utils as utils

log = logging.getLogger(__name__)
THIS_DIR = os.path.dirname(os.path.abspath(__file__))
SPARK_PI_FW_NAME = "Spark Pi"
CNI_TEST_NUM_EXECUTORS = 1

CNI_DISPATCHER_SERVICE_NAME = "spark-cni-dispatcher"
CNI_DISPATCHER_ZK = "spark_mesos__dispatcher_cni"

NETWORK_NAME = "dcos"
SPARK_NETWORK_LABELS = "key_1:value_1,key_2:value_2"
DISPATCHER_NETWORK_LABELS = [
    {"key": "key_1", "value": "value_1"},
    {"key": "key_2", "value": "value_2"}
]

CNI_SERVICE_OPTIONS = {
    "service": {
        "name": CNI_DISPATCHER_SERVICE_NAME,
        "virtual_network_enabled": True,
        "virtual_network_name": NETWORK_NAME,
        "virtual_network_plugin_labels": DISPATCHER_NETWORK_LABELS,
        "UCR_containerizer": False,
        "use_bootstrap_for_IP_detect": False
    }
}


@pytest.fixture(scope='module')
def configure_security():
    yield from utils.spark_security_session()


@pytest.fixture(scope='module')
def setup_spark(configure_security, configure_universe):
    try:
        utils.upload_dcos_test_jar()
        utils.require_spark()
        sdk_cmd.run_cli('package install --cli dcos-enterprise-cli --yes')
        yield
    finally:
        utils.teardown_spark()


@pytest.mark.sanity
def test_cni(setup_spark):
    utils.run_tests(app_url=utils.SPARK_EXAMPLES,
                    app_args="",
                    expected_output="Pi is roughly 3",
                    args=["--conf spark.mesos.network.name=dcos",
                          "--class org.apache.spark.examples.SparkPi"])


@pytest.mark.sanity
@pytest.mark.smoke
def test_cni_labels(setup_spark):
    driver_task_id = utils.submit_job(app_url=utils.SPARK_EXAMPLES,
                                      app_args="3000",   # Long enough to examine the Driver's & Executor's task infos
                                      args=["--conf spark.mesos.network.name=dcos",
                                            "--conf spark.mesos.network.labels={}".format(SPARK_NETWORK_LABELS),
                                            "--conf spark.cores.max={}".format(CNI_TEST_NUM_EXECUTORS),
                                            "--class org.apache.spark.examples.SparkPi"])

    # Wait until executors are running
    sdk_tasks.check_running(SPARK_PI_FW_NAME, CNI_TEST_NUM_EXECUTORS, timeout_seconds=600)

    # Check for network name / labels in Driver task info
    driver_task = shakedown.get_task(driver_task_id, completed=False)
    _check_task_network_info(driver_task)

    # Check for network name / labels in Executor task info
    executor_task = shakedown.get_service_tasks(SPARK_PI_FW_NAME)[0]
    _check_task_network_info(executor_task)

    # Check job output
    utils.check_job_output(driver_task_id, "Pi is roughly 3")


def _check_task_network_info(task):
    # Expected: "network_infos":[{
    #   "name":"dcos",
    #   "labels":{
    #       "labels":[
    #           {"key":"key_1","value":"value_1"},
    #           {"key":"key_2","value":"value_2"}]}}]
    network_info = task['container']['network_infos'][0]
    log.info("Network info:\n{}".format(network_info))
    assert network_info['name'] == NETWORK_NAME
    labels = network_info['labels']['labels']

    log.info("=> Labels network_info['labels']:\n{}".format(network_info['labels']))
    log.info("=> Labels network_info['labels']['labels']:\n{}".format(network_info['labels']['labels']))
    _check_label_present(labels, "key_1", "value_1")
    _check_label_present(labels, "key_2", "value_2")


def _check_label_present(labels, key, value):
    for label in labels:
        if label["key"] == key:
            assert label["value"] == value
            return

    raise AssertionError("Label with key {} wasn't found in task network labels".format(key))


# The following dispatcher fixtures rely on sdk_install.install because for the time being
# spark_utils.require_spark can't be effectively used with virtual network due to
# https://jira.mesosphere.com/browse/DCOS-45468 (Add supporting endpoints for services
# running in CNI (e.g. Calico) to AdminRouter)
@pytest.fixture()
def spark_dispatcher(configure_security, configure_universe, use_ucr_containerizer):
    sdk_install.uninstall(utils.SPARK_PACKAGE_NAME, CNI_DISPATCHER_SERVICE_NAME, zk=CNI_DISPATCHER_ZK)

    options = {
        "service": {
            "UCR_containerizer": use_ucr_containerizer
        }
    }

    try:
        merged_options = sdk_install.merge_dictionaries(CNI_SERVICE_OPTIONS, options)
        sdk_install.install(
            utils.SPARK_PACKAGE_NAME,
            CNI_DISPATCHER_SERVICE_NAME,
            0,
            additional_options=utils.get_spark_options(CNI_DISPATCHER_SERVICE_NAME, merged_options),
            wait_for_deployment=False)
        yield
    finally:
        sdk_install.uninstall(utils.SPARK_PACKAGE_NAME, CNI_DISPATCHER_SERVICE_NAME, zk=CNI_DISPATCHER_ZK)


@pytest.mark.sanity
@pytest.mark.parametrize('use_ucr_containerizer', [False])
def test_dispatcher_cni_support_for_docker(spark_dispatcher):
    host_ip, task_ip = _get_host_and_task_ips(CNI_DISPATCHER_SERVICE_NAME)
    subnet = _get_host_subnet(host_ip)
    _verify_task_ip(task_ip, host_ip, subnet)

    # Network labels are not propagated to Mesos Task NetworkInfo by Marathon
    # when Docker containerizer is used. Labels verification is skipped for Docker.

    # checking Docker container info
    task = _get_task()
    task_id = task["id"]
    container_id_cmd = "sudo docker ps --format='{{.ID}}' | " \
                       "xargs -I {} docker inspect --format='{{.ID}},{{.Config.Labels.MESOS_TASK_ID}}' {} | " \
                       "grep " + task_id + " | cut -d',' -f1"

    _, container_id = sdk_cmd.agent_ssh(host_ip, container_id_cmd)
    assert container_id is not None and container_id.rstrip() != ""

    inspect_cmd = "sudo docker inspect " \
                  "--format='{{.NetworkSettings.Networks." + NETWORK_NAME + ".IPAddress}}' " + container_id.rstrip()

    _, container_ip = sdk_cmd.agent_ssh(host_ip, inspect_cmd)
    assert ipaddress.ip_address(container_ip.rstrip()) in ipaddress.ip_network(subnet), \
        "Docker container Network Info IP is not in the specified subnet"

    # checking Docker container inet address
    exec_cmd = "sudo docker exec {} hostname -i".format(container_id.rstrip())

    _, inet_addr = sdk_cmd.agent_ssh(host_ip, exec_cmd)
    assert ipaddress.ip_address(inet_addr.rstrip()) in ipaddress.ip_network(subnet), \
        "Docker Inet address is not in the specified subnet"


@pytest.mark.sanity
@pytest.mark.parametrize('use_ucr_containerizer', [True])
def test_dispatcher_cni_support_for_ucr(spark_dispatcher):
    host_ip, task_ip = _get_host_and_task_ips(CNI_DISPATCHER_SERVICE_NAME)
    subnet = _get_host_subnet(host_ip)
    _verify_task_ip(task_ip, host_ip, subnet)
    task = _get_task()

    log.info("Checking task network info")
    _check_task_network_info(task)

    # checking UCR container inet address
    task_id = task["id"]
    inet_addr = sdk_cmd.run_cli(f"task exec {task_id} hostname -i")
    assert ipaddress.ip_address(inet_addr.rstrip()) in ipaddress.ip_network(subnet), \
        "UCR container Inet address is not in the specified subnet"


def _get_task(task_name=CNI_DISPATCHER_SERVICE_NAME):
    tasks_json = json.loads(sdk_cmd.run_cli("task --json"))

    tasks = []
    for task in tasks_json:
        if task["name"] == task_name:
            tasks.append(task)

    assert len(tasks) == 1, "More than one task with name {} is running".format(task_name)
    return tasks[0]


def _get_host_subnet(host_ip, network_name=NETWORK_NAME):
    network_info_endpoint = "leader.mesos:5050/overlay-master/state"
    network_info_curl_cmd = "curl http://{}".format(network_info_endpoint)

    if sdk_utils.is_strict_mode():
        network_info_curl_cmd = "curl -k https://{}".format(network_info_endpoint)

    @retrying.retry(stop_max_attempt_number=10, wait_fixed=1000)
    def get_network_info_with_retry():
        ok, networks = sdk_cmd.master_ssh(network_info_curl_cmd)
        assert ok
        return json.loads(networks)

    network_info = get_network_info_with_retry()

    # finding an agent with the same IP as tasks's from the list of agents in networks info
    task_agent = None
    for agent in network_info["agents"]:
        if agent["ip"] == host_ip:
            task_agent = agent
            break

    assert task_agent is not None, \
        "Agent with task IP is not present in networks info output"

    # finding subnet info from agent's networks
    subnet = None
    for network in task_agent["overlays"]:
        if network["info"]["name"] == network_name:
            subnet = network["info"]["subnet"]
            break

    assert subnet is not None, \
        "Subnet wasn't found in agent networks info output"

    return subnet


def _get_host_and_task_ips(service_name):
    app_json = sdk_cmd.get_json_output("marathon app show {}".format(service_name))

    host_ip = app_json["tasks"][0]["host"]
    task_ip = app_json["tasks"][0]["ipAddresses"][0]["ipAddress"]
    return host_ip, task_ip


def _verify_task_ip(task_ip, host_ip, subnet):
    assert host_ip != task_ip, \
        "Task has the same IP as the host it's running on"
    assert ipaddress.ip_address(task_ip) in ipaddress.ip_network(subnet), \
        "Task IP is not in the specified subnet"
