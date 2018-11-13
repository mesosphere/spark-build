# Env:
#   AWS_ACCESS_KEY_ID
#   AWS_SECRET_ACCESS_KEY
#   COMMONS_DIR
#   S3_BUCKET
#   S3_PREFIX
#   MESOS_SPARK_TEST_JAR_PATH // /path/to/mesos-spark-integration-tests.jar
#   DCOS_SPARK_TEST_JAR_PATH // /path/to/dcos-spark-scala-tests.jar

import json
import logging
import os
import pytest
import retrying
import shakedown
import time

import sdk_cmd
import sdk_hosts
import sdk_install
import sdk_security
import sdk_tasks
import sdk_utils
import requests
import spark_s3 as s3
import spark_utils as utils
import subprocess

LOGGER = logging.getLogger(__name__)
THIS_DIR = os.path.dirname(os.path.abspath(__file__))
SPARK_PI_FW_NAME = "Spark Pi"
CNI_TEST_NUM_EXECUTORS = 1


@pytest.fixture(scope='module')
def configure_security():
    yield from utils.spark_security_session()


@pytest.fixture(scope='module', autouse=True)
def setup_spark(configure_security, configure_universe):
    try:
        utils.upload_dcos_test_jar()
        utils.require_spark()
        sdk_cmd.run_cli('package install --cli dcos-enterprise-cli --yes')
        yield
    finally:
        utils.teardown_spark()


@pytest.mark.sanity
def test_task_not_lost():
    driver_task_id = utils.submit_job(app_url=utils.SPARK_EXAMPLES,
                                      app_args="1500",  # Long enough to examine the Executor's task info
                                      args=["--conf spark.cores.max=1",
                                            "--class org.apache.spark.examples.SparkPi"])

    # Wait until executor is running
    sdk_tasks.check_running(SPARK_PI_FW_NAME, 1, timeout_seconds=600)

    # Check Executor task ID - should end with 0, the first task.
    # If it's > 0, that means the first task was lost.
    assert sdk_tasks.get_task_ids(SPARK_PI_FW_NAME, '')[0].endswith('-0')

    # Check job output
    utils.check_job_output(driver_task_id, "Pi is roughly 3")


def retry_if_false(result):
    return not result


@retrying.retry(stop_max_attempt_number=30,
                wait_fixed=10000,
                retry_on_result=retry_if_false)
def wait_for_jobs_completion(driver_id_1, driver_id_2):
    out_1 = sdk_cmd.run_cli("spark status --skip-message {}".format(driver_id_1))
    out_2 = sdk_cmd.run_cli("spark status --skip-message {}".format(driver_id_2))
    data_1 = json.loads(out_1)
    data_2 = json.loads(out_2)

    LOGGER.info('Driver 1 state: %s, Driver 2 state: %s' % (data_1['driverState'], data_2['driverState']))
    return data_1['driverState'] == data_2["driverState"] == "FINISHED"


@pytest.mark.sanity
def test_unique_task_ids():
    sdk_cmd.run_cli("package install spark --cli --yes")

    LOGGER.info('Submitting two sample Spark Applications')
    driver_id_1 = utils.submit_job(app_url=utils.SPARK_EXAMPLES,
                                   app_args="100",
                                   args=["--class org.apache.spark.examples.SparkPi"])
    driver_id_2 = utils.submit_job(app_url=utils.SPARK_EXAMPLES,
                                   app_args="100",
                                   args=["--class org.apache.spark.examples.SparkPi"])

    LOGGER.info('Two Spark Applications submitted. Driver 1 ID: %s, Driver 2 ID: %s' % (driver_id_1, driver_id_2))
    LOGGER.info('Waiting for completion. Polling state')
    completed = wait_for_jobs_completion(driver_id_1, driver_id_2)

    assert completed == True, 'Sample Spark Applications failed to successfully complete within given time'
    out = sdk_cmd.run_cli("task --completed --json")
    data = json.loads(out)

    LOGGER.info('Collecting tasks that belong to the drivers created in this test')
    task_ids = []
    for d in data:
        if driver_id_1 in d['framework_id'] or driver_id_2 in d['framework_id']:
            task_ids.append(d['id'])

    LOGGER.info('Tasks found: %s' % (' '.join(task_ids)))
    assert len(task_ids) == len(set(task_ids)), 'Task ids for two independent Spark Applications contain duplicates'


@pytest.mark.xfail(sdk_utils.is_strict_mode(), reason="Currently fails in strict mode")
@pytest.mark.skip(reason="Currently fails due to CI misconfiguration")  # TODO: Fix CI/update mesos-integration-tests
# @pytest.mark.sanity
# @pytest.mark.smoke
def test_jar(service_name=utils.SPARK_SERVICE_NAME):
    master_url = ("https" if sdk_utils.is_strict_mode() else "http") + "://leader.mesos:5050"
    spark_job_runner_args = '{} dcos \\"*\\" spark:only 2 --auth-token={}'.format(
        master_url,
        shakedown.dcos_acs_token())
    utils.run_tests(app_url=utils.upload_mesos_test_jar(),
                    app_args=spark_job_runner_args,
                    expected_output="All tests passed",
                    service_name=service_name,
                    args=['--class com.typesafe.spark.test.mesos.framework.runners.SparkJobRunner'])


@sdk_utils.dcos_ee_only
@pytest.mark.sanity
@pytest.mark.smoke
def test_rpc_auth():
    secret_name = "sparkauth"

    sdk_security.delete_secret(secret_name)
    rc, _, _ = sdk_cmd.run_raw_cli("{} --verbose secret /{}".format(utils.SPARK_PACKAGE_NAME, secret_name))
    assert rc == 0, "Failed to generate Spark auth secret"

    utils.run_tests(
        app_url=utils.SPARK_EXAMPLES,
        app_args="100",
        expected_output="Pi is roughly 3",
        service_name=utils.SPARK_SERVICE_NAME,
        args=["--executor-auth-secret {}".format(secret_name),
              "--class org.apache.spark.examples.SparkPi"])


@pytest.mark.sanity
def test_sparkPi(service_name=utils.SPARK_SERVICE_NAME):
    utils.run_tests(
        app_url=utils.SPARK_EXAMPLES,
        app_args="100",
        expected_output="Pi is roughly 3",
        service_name=service_name,
        args=["--class org.apache.spark.examples.SparkPi"])


@pytest.mark.sanity
def test_multi_arg_confs(service_name=utils.SPARK_SERVICE_NAME):
    utils.run_tests(
        app_url=utils.dcos_test_jar_url(),
        app_args="",
        expected_output="spark.driver.extraJavaOptions,-XX:+PrintGCDetails -XX:+PrintGCTimeStamps -Dparam3=\"valA valB\"",
        service_name=service_name,
        args=[
            "--conf spark.driver.extraJavaOptions='-XX:+PrintGCDetails -XX:+PrintGCTimeStamps -Dparam3=\\\"valA valB\\\"'",
            "--class MultiConfs"])


@pytest.mark.sanity
@pytest.mark.smoke
def test_python():
    python_script_path = os.path.join(THIS_DIR, 'jobs', 'python', 'pi_with_include.py')
    python_script_url = utils.upload_file(python_script_path)
    py_file_path = os.path.join(THIS_DIR, 'jobs', 'python', 'PySparkTestInclude.py')
    py_file_url = utils.upload_file(py_file_path)
    utils.run_tests(app_url=python_script_url,
                    app_args="30",
                    expected_output="Pi is roughly 3",
                    args=["--py-files {}".format(py_file_url)])


@pytest.mark.sanity
@pytest.mark.smoke
def test_r():
    r_script_path = os.path.join(THIS_DIR, 'jobs', 'R', 'dataframe.R')
    r_script_url = utils.upload_file(r_script_path)
    utils.run_tests(app_url=r_script_url,
                    app_args='',
                    expected_output="Justin")


@pytest.mark.sanity
def test_cni():
    utils.run_tests(app_url=utils.SPARK_EXAMPLES,
                    app_args="",
                    expected_output="Pi is roughly 3",
                    args=["--conf spark.mesos.network.name=dcos",
                          "--class org.apache.spark.examples.SparkPi"])


@pytest.mark.sanity
@pytest.mark.smoke
def test_cni_labels():
    driver_task_id = utils.submit_job(app_url=utils.SPARK_EXAMPLES,
                                      app_args="3000",  # Long enough to examine the Driver's & Executor's task infos
                                      args=["--conf spark.mesos.network.name=dcos",
                                            "--conf spark.mesos.network.labels=key1:val1,key2:val2",
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
    #           {"key":"key1","value":"val1"},
    #           {"key":"key2","value":"val2"}]}}]
    network_info = task['container']['network_infos'][0]
    assert network_info['name'] == "dcos"
    labels = network_info['labels']['labels']
    assert len(labels) == 2
    assert labels[0]['key'] == "key1"
    assert labels[0]['value'] == "val1"
    assert labels[1]['key'] == "key2"
    assert labels[1]['value'] == "val2"


# Your session credentials are tied to your IP. They work locally, but will not work from the spark job.
@pytest.mark.skipif(s3.get_credentials().token is not None, reason="Session credentials won't work")
@sdk_utils.dcos_ee_only
@pytest.mark.sanity
@pytest.mark.smoke
def test_s3_secrets():
    linecount_path = os.path.join(THIS_DIR, 'resources', 'linecount.txt')
    s3.upload_file(linecount_path)

    creds = s3.get_credentials()

    def make_credential_secret(path, val):
        sdk_security.delete_secret(path)
        rc, stdout, stderr = sdk_cmd.run_raw_cli("security secrets create /{} -v {}".format(path, val))
        assert rc == 0, "Failed to create secret {}, stderr: {}, stdout: {}".format(path, stderr, stdout)

    aws_access_key_path = "aws_access_key_id"
    make_credential_secret(aws_access_key_path, creds.access_key)
    aws_secret_key_path = "aws_secret_access_key"
    make_credential_secret(aws_secret_key_path, creds.secret_key)

    args = ["--conf spark.mesos.containerizer=mesos",
            "--conf spark.mesos.driver.secret.names=/{key},/{secret}".format(
                key=aws_access_key_path, secret=aws_secret_key_path),
            "--conf spark.mesos.driver.secret.envkeys=AWS_ACCESS_KEY_ID,AWS_SECRET_ACCESS_KEY",
            "--class S3Job"]

    try:
        # download/read linecount.txt only
        utils.run_tests(app_url=utils.dcos_test_jar_url(),
                        app_args="--readUrl {} --countOnly".format(s3.s3n_url('linecount.txt')),
                        expected_output="Read 3 lines",
                        args=args)
        # download/read linecount.txt, reupload as linecount-secret.txt:
        utils.run_tests(app_url=utils.dcos_test_jar_url(),
                        app_args="--readUrl {} --writeUrl {}".format(
                            s3.s3n_url('linecount.txt'), s3.s3n_url('linecount-secret.txt')),
                        expected_output="Read 3 lines",
                        args=args)
        assert len(list(s3.list("linecount-secret.txt"))) > 0
    finally:
        sdk_security.delete_secret(aws_access_key_path)
        sdk_security.delete_secret(aws_secret_key_path)


# Your session credentials are tied to your IP. They work locally, but will not work from the spark job.
@pytest.mark.skipif(s3.get_credentials().token is not None, reason="Session credentials won't work")
@pytest.mark.sanity
@pytest.mark.smoke
def test_s3_env():
    creds = s3.get_credentials()
    args = ["--conf spark.mesos.driverEnv.AWS_ACCESS_KEY_ID={}".format(creds.access_key),
            "--conf spark.mesos.driverEnv.AWS_SECRET_ACCESS_KEY={}".format(creds.secret_key)]
    args.append("--class S3Job")

    linecount_path = os.path.join(THIS_DIR, 'resources', 'linecount.txt')
    s3.upload_file(linecount_path)

    # download/read linecount.txt only
    utils.run_tests(app_url=utils.dcos_test_jar_url(),
                    app_args="--readUrl {} --countOnly".format(s3.s3n_url('linecount.txt')),
                    expected_output="Read 3 lines",
                    args=args)

    # download/read linecount.txt, reupload as linecount-env.txt
    utils.run_tests(app_url=utils.dcos_test_jar_url(),
                    app_args="--readUrl {} --writeUrl {}".format(
                        s3.s3n_url('linecount.txt'), s3.s3n_url('linecount-env.txt')),
                    expected_output="Read 3 lines",
                    args=args)

    assert len(list(s3.list("linecount-env.txt"))) > 0


@pytest.mark.dcos_min_version('1.10')
@pytest.mark.sanity
@pytest.mark.smoke
def test_foldered_spark():
    service_name = utils.FOLDERED_SPARK_SERVICE_NAME
    zk = 'spark_mesos_dispatcher__path_to_spark'
    utils.teardown_spark(service_name=service_name, zk=zk)
    utils.require_spark(service_name=service_name, zk=zk)
    test_sparkPi(service_name=service_name)
    utils.teardown_spark(service_name=service_name, zk=zk)
    # reinstall CLI so that it's available for the following tests:
    sdk_cmd.run_cli('package install --cli {} --yes'.format(utils.SPARK_PACKAGE_NAME))


@pytest.mark.sanity
def test_cli_multiple_spaces():
    utils.run_tests(app_url=utils.SPARK_EXAMPLES,
                    app_args="30",
                    expected_output="Pi is roughly 3",
                    args=["--conf spark.cores.max=2",
                          "--class org.apache.spark.examples.SparkPi"])


# Skip DC/OS < 1.10, because it doesn't have support for file-based secrets.
@pytest.mark.dcos_min_version('1.10')
@sdk_utils.dcos_ee_only
@pytest.mark.sanity
@pytest.mark.smoke
def test_driver_executor_tls():
    '''
    Put keystore and truststore as secrets in DC/OS secret store.
    Run SparkPi job with TLS enabled, referencing those secrets.
    Make sure other secrets still show up.
    '''
    python_script_path = os.path.join(THIS_DIR, 'jobs', 'python', 'pi_with_secret.py')
    python_script_url = utils.upload_file(python_script_path)
    resources_folder = os.path.join(
        os.path.dirname(os.path.realpath(__file__)), 'resources'
    )
    keystore_file = 'server.jks'
    truststore_file = 'trust.jks'
    keystore_path = os.path.join(resources_folder, '{}.base64'.format(keystore_file))
    truststore_path = os.path.join(resources_folder, '{}.base64'.format(truststore_file))
    keystore_secret = '__dcos_base64__keystore'
    truststore_secret = '__dcos_base64__truststore'
    my_secret = 'mysecret'
    my_secret_content = 'secretcontent'
    sdk_cmd.run_cli('security secrets create /{} --value-file {}'.format(keystore_secret, keystore_path))
    sdk_cmd.run_cli('security secrets create /{} --value-file {}'.format(truststore_secret, truststore_path))
    sdk_cmd.run_cli('security secrets create /{} --value {}'.format(my_secret, my_secret_content))
    password = 'changeit'
    try:
        utils.run_tests(app_url=python_script_url,
                        app_args="30 {} {}".format(my_secret, my_secret_content),
                        expected_output="Pi is roughly 3",
                        args=["--keystore-secret-path", keystore_secret,
                              "--truststore-secret-path", truststore_secret,
                              "--private-key-password", format(password),
                              "--keystore-password", format(password),
                              "--truststore-password", format(password),
                              "--conf", "spark.mesos.driver.secret.names={}".format(my_secret),
                              "--conf", "spark.mesos.driver.secret.filenames={}".format(my_secret),
                              "--conf", "spark.mesos.driver.secret.envkeys={}".format(my_secret),
                              ])
    finally:
        sdk_cmd.run_cli('security secrets delete /{}'.format(keystore_secret))
        sdk_cmd.run_cli('security secrets delete /{}'.format(truststore_secret))
        sdk_cmd.run_cli('security secrets delete /{}'.format(my_secret))


@pytest.mark.sanity
def test_unique_vips():
    spark1_service_name = "test/groupa/spark"
    spark2_service_name = "test/groupb/spark"
    try:
        utils.require_spark(spark1_service_name)
        utils.require_spark(spark2_service_name)

        dispatcher1_ui = sdk_hosts.vip_host("marathon", "dispatcher.{}".format(spark1_service_name), 4040)
        dispatcher2_ui = sdk_hosts.vip_host("marathon", "dispatcher.{}".format(spark2_service_name), 4040)

        # verify dispatcher-ui is reachable at VIP
        ok, _ = sdk_cmd.master_ssh("curl {}".format(dispatcher1_ui))
        assert ok

        ok, _ = sdk_cmd.master_ssh("curl {}".format(dispatcher2_ui))
        assert ok
    finally:
        sdk_install.uninstall(utils.SPARK_PACKAGE_NAME, spark1_service_name)
        sdk_install.uninstall(utils.SPARK_PACKAGE_NAME, spark2_service_name)


@pytest.mark.sanity
def test_task_stdout():
    try:
        service_name = utils.FOLDERED_SPARK_SERVICE_NAME
        task_id = service_name.lstrip("/").replace("/", "_")
        utils.require_spark(service_name=service_name)

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
    finally:
        sdk_install.uninstall(utils.SPARK_PACKAGE_NAME, service_name)


@pytest.mark.sanity
def test_handling_wrong_request_to_spark_dispatcher():
    service_name = utils.FOLDERED_SPARK_SERVICE_NAME
    utils.require_spark(service_name=service_name)

    json_data = sdk_cmd.run_cli("dcos task --json")
    dispatcher_ip = json_data['statuses'][0]['container_status']['network_infos'][0]['ip_addresses'][0]['ip_address']
    port = json_data['discovery']['ports'][0]['number']

    headers = {
        'Content-Type': 'application/json;charset=UTF-8',
    }
    data = {"action": "CreateSubmissionRequest",
            "clientSparkVersion": "2.3.2",
            "appResource": "noopTest.jar",
            "mainClass": "noop.Test",
            "appArgs": ["arg1", "arg2"],
            "environmentVariables": {
                "PATH": "/dev/null"
            },

            "sparkProperties": {
                "spark.app.name": "TestDispatcher",

            },

            }
    response = requests.post('http://{0}:{1}/submissions/create'.format(dispatcher_ip, port), headers=headers, data=data)

    headers = {
        'Content-Type': 'application/json;charset=UTF-8',
    }
    data = {"action": "CreateSubmissionRequest",
            "clientSparkVersion": "2.3.2",
            "appResource": "noopTest.jar",
            "mainClass": "noop.Test",
            "environmentVariables": {
                "PATH": "/dev/null"
            },

            "sparkProperties": {
                "spark.app.name": "TestDispatcher",
            },

            }
    response = requests.post('http://{0}:{1}/submissions/create'.format(dispatcher_ip, port), headers=headers,
                             data=data)

    headers = {
        'Content-Type': 'application/json;charset=UTF-8',
    }
    data = {"action": "CreateSubmissionRequest",
            "clientSparkVersion": "2.3.2",
            "appResource": "noopTest.jar",
            "mainClass": "noop.Test",
            "appArgs": ["arg1", "arg2"],
            "environmentVariables": {
                "PATH": "/dev/null"
            },

            "sparkProperties": {
                "spark.app.name": "TestDispatcher",

            },

            }
    response = requests.post('http://{0}:{1}/submissions/create'.format(dispatcher_ip, port), headers=headers,
                             data=data)
    assert (response.status_code < 200 or response.status_code >= 300)

