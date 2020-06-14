import ipaddress
import json
import logging

import pytest
import sdk_cmd
import sdk_install
import sdk_networks
import sdk_tasks
import shakedown
import spark_utils as utils
import docker_utils

log = logging.getLogger(__name__)

SHUFFLE_JOB_FW_NAME = "Shuffle Test"
SHUFFLE_JOB_EXPECTED_GROUPS_COUNT = 12000
SHUFFLE_JOB_NUM_EXECUTORS = 4

CNI_DISPATCHER_SERVICE_NAME = "spark-cni-dispatcher"
CNI_DISPATCHER_ZK = "spark_mesos_dispatcher" + CNI_DISPATCHER_SERVICE_NAME

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
        "UCR_containerizer": False
    }
}


@pytest.fixture()
def setup_spark(configure_security_spark, configure_universe):
    try:
        utils.upload_dcos_test_jar()
        utils.require_spark()
        yield
    finally:
        utils.teardown_spark()


# The following dispatcher fixtures rely on sdk_install.install because for the time being
# spark_utils.require_spark can't be effectively used with virtual network due to
# https://jira.mesosphere.com/browse/DCOS-45468 (Add supporting endpoints for services
# running in CNI (e.g. Calico) to AdminRouter)
@pytest.fixture()
def spark_dispatcher(configure_security_spark, configure_universe, use_ucr_containerizer):
    utils.teardown_spark(service_name=CNI_DISPATCHER_SERVICE_NAME, zk=CNI_DISPATCHER_ZK)

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
        utils.teardown_spark(service_name=CNI_DISPATCHER_SERVICE_NAME, zk=CNI_DISPATCHER_ZK)


@pytest.mark.sanity
@pytest.mark.parametrize('use_ucr_containerizer', [
    True,
    False
])
def test_cni_dispatcher(spark_dispatcher, use_ucr_containerizer):
    task = utils.get_dispatcher_task(service_name=CNI_DISPATCHER_SERVICE_NAME)
    _check_task_network(task, is_ucr=use_ucr_containerizer)


@pytest.mark.sanity
@pytest.mark.smoke
def test_cni_labels(setup_spark):
    submit_args = [
        "--conf spark.mesos.network.name={}".format(NETWORK_NAME),
        "--conf spark.mesos.network.labels={}".format(SPARK_NETWORK_LABELS)
    ]

    test_shuffle_job(
        submit_args=submit_args,
        check_network_labels=True
    )


@pytest.mark.sanity
@pytest.mark.smoke
@pytest.mark.parametrize("use_ucr_for_spark_submit", [
    True,
    False
])
def test_cni_driver_and_executors(setup_spark, use_ucr_for_spark_submit):
    log.info("Running test with use_ucr_for_spark_submit={}".format(use_ucr_for_spark_submit))

    submit_args = [
        "--conf spark.mesos.network.name={}".format(NETWORK_NAME)
    ]

    # ATM, this is the only corner-case with using 'bootstrap' for IP resolution:
    # Spark jobs submitted with a network different from Dispatcher's network and using Docker containerizer
    if not use_ucr_for_spark_submit:
        submit_args = submit_args + [
            "--conf spark.mesos.driverEnv.VIRTUAL_NETWORK_ENABLED=true",
            "--conf spark.executorEnv.VIRTUAL_NETWORK_ENABLED=true"
        ]

    test_shuffle_job(
        submit_args=submit_args,
        use_ucr_for_spark_submit=use_ucr_for_spark_submit
    )


@pytest.mark.sanity
@pytest.mark.parametrize("use_ucr_containerizer,use_ucr_for_spark_submit", [
    (True, True),
    (True, False),
    (False, True),
    (False, False)
])
def test_dispatcher_default_network(spark_dispatcher, use_ucr_containerizer, use_ucr_for_spark_submit):
    log.info("Running test with use_ucr_containerizer={}, use_ucr_for_spark_submit={}"
             .format(use_ucr_containerizer, use_ucr_for_spark_submit))

    dispatcher_task = utils.get_dispatcher_task(service_name=CNI_DISPATCHER_SERVICE_NAME)
    _check_task_network(dispatcher_task, is_ucr=use_ucr_containerizer)
    dispatcher_ip = sdk_networks.get_task_ip(dispatcher_task)

    submit_args = [
        "--master mesos://{}:7077".format(dispatcher_ip),
        "--deploy-mode cluster",
        "--conf spark.mesos.executor.docker.image={}".format(utils.SPARK_DOCKER_IMAGE)
    ]

    test_shuffle_job(
        submit_args=submit_args,
        use_ucr_for_spark_submit=use_ucr_for_spark_submit,
        use_cli_for_spark_submit=False
    )


def test_shuffle_job(
        submit_args=[],
        use_ucr_for_spark_submit=True,
        use_cli_for_spark_submit=True,
        check_network_labels=False):

    if not use_ucr_for_spark_submit:
        submit_args = submit_args + [
            "--conf spark.mesos.containerizer=docker",
            "--conf spark.mesos.executor.docker.parameters=user=99",
        ]

    driver_task_id = _submit_shuffle_job(use_cli=use_cli_for_spark_submit,
                                         sleep=300,
                                         extra_args=submit_args)

    sdk_tasks.check_running(SHUFFLE_JOB_FW_NAME, SHUFFLE_JOB_NUM_EXECUTORS, timeout_seconds=600)
    driver_task = shakedown.get_task(driver_task_id, completed=False)
    _check_task_network(driver_task, is_ucr=use_ucr_for_spark_submit)

    if check_network_labels and use_ucr_for_spark_submit:
        _check_task_network_labels(driver_task)

    executor_tasks = shakedown.get_service_tasks(SHUFFLE_JOB_FW_NAME)
    for task in executor_tasks:
        _check_task_network(task, is_ucr=use_ucr_for_spark_submit)
        if check_network_labels and use_ucr_for_spark_submit:
            _check_task_network_labels(task)

    try:
        utils.wait_for_running_job_output(driver_task_id, "Groups count: {}".format(SHUFFLE_JOB_EXPECTED_GROUPS_COUNT))
    finally:
        log.info("Cleaning up. Attempting to kill driver: {}".format(driver_task_id))
        utils.kill_driver(driver_task_id, service_name=CNI_DISPATCHER_SERVICE_NAME)


def _submit_shuffle_job(sleep=0, extra_args=[], use_cli=True):
    num_unique_keys = SHUFFLE_JOB_EXPECTED_GROUPS_COUNT
    num_mappers = 4
    value_size_bytes = 100
    num_reducers = 4
    # Usage: ShuffleApp [numMappers] [numPairs] [valueSize] [numReducers] [sleepBeforeShutdown]
    return utils.submit_job(app_url=utils.dcos_test_jar_url(),
                            use_cli=use_cli,
                            app_args="{} {} {} {} {}".format(num_mappers, num_unique_keys, value_size_bytes, num_reducers, sleep),
                            args=["--conf spark.executor.cores=1",
                                  "--conf spark.cores.max={}".format(SHUFFLE_JOB_NUM_EXECUTORS),
                                  "--conf spark.scheduler.minRegisteredResourcesRatio=1",
                                  "--conf spark.scheduler.maxRegisteredResourcesWaitingTime=3m",
                                  "--class ShuffleApp"] + extra_args)


def _check_task_network(task, is_ucr=True):
    host_ip = sdk_networks.get_task_host(task)
    task_ip = sdk_networks.get_task_ip(task)
    subnet = sdk_networks.get_overlay_subnet()

    _verify_task_ip(task_ip, host_ip, subnet)
    _verify_task_network_name(task)

    if is_ucr:
        _verify_ucr_task_inet_address(task, subnet)
    else:
        _check_docker_network(task, host_ip, subnet)


def _verify_task_ip(task_ip, host_ip, subnet):
    assert host_ip != task_ip, \
        "Task has the same IP as the host it's running on"
    assert ipaddress.ip_address(task_ip) in ipaddress.ip_network(subnet), \
        "Task IP is not in the specified subnet"


def _verify_task_network_name(task):
    network_info = task['container']['network_infos'][0]
    log.info("Network info:\n{}".format(network_info))
    assert network_info['name'] == NETWORK_NAME


def _check_task_network_labels(task):
    labels = task['container']['network_infos'][0]['labels']['labels']

    _check_label_present(labels, "key_1", "value_1")
    _check_label_present(labels, "key_2", "value_2")


def _check_label_present(labels, key, value):
    for label in labels:
        if label["key"] == key:
            assert label["value"] == value
            return

    raise AssertionError("Label with key {} wasn't found in task network labels".format(key))


def _check_docker_network(task, host_ip, subnet):
    container_ip = docker_utils.docker_inspect(
        task,
        format_options="--format='{{.NetworkSettings.Networks." + NETWORK_NAME + ".IPAddress}}'"
    )
    assert ipaddress.ip_address(container_ip.rstrip()) in ipaddress.ip_network(subnet), \
        "Docker container Network Info IP is not in the specified subnet"

    # checking Docker container inet address
    inet_addr = docker_utils.docker_exec(task, "hostname -i")
    assert ipaddress.ip_address(inet_addr.rstrip()) in ipaddress.ip_network(subnet), \
        "Docker Inet address is not in the specified subnet"


def _verify_ucr_task_inet_address(task, subnet):
    task_id = task["id"]
    # older versions of Mesos produce additional output while running 'tasks exec', therefore 'tail -1'
    inet_addr = sdk_cmd.run_cli(f"task exec {task_id} hostname -i | tail -1")
    assert ipaddress.ip_address(inet_addr.rstrip()) in ipaddress.ip_network(subnet), \
        "UCR container Inet address is not in the specified subnet"
