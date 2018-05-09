# Env:
#   AWS_ACCESS_KEY_ID
#   AWS_SECRET_ACCESS_KEY
#   COMMONS_DIR
#   S3_BUCKET
#   S3_PREFIX
#   TEST_JAR_PATH // /path/to/mesos-spark-integration-tests.jar
#   SCALA_TEST_JAR_PATH // /path/to/dcos-spark-scala-tests.jar

import logging
import os
import pytest
import json
import shakedown

import sdk_utils
import sdk_cmd

import spark_s3 as s3
import spark_utils as utils


LOGGER = logging.getLogger(__name__)
THIS_DIR = os.path.dirname(os.path.abspath(__file__))
SPARK_PI_FW_NAME = "Spark Pi"
CNI_TEST_NUM_EXECUTORS = 1
SECRET_NAME = "secret"
SECRET_CONTENTS = "mgummelt"


@pytest.fixture(scope='module')
def configure_security():
    yield from utils.spark_security_session()


@pytest.fixture(scope='module', autouse=True)
def setup_spark(configure_security, configure_universe):
    try:
        utils.require_spark()
        utils.upload_file(os.environ["SCALA_TEST_JAR_PATH"])
        shakedown.run_dcos_command('package install --cli dcos-enterprise-cli --yes')
        yield
    finally:
        utils.teardown_spark()


@pytest.mark.sanity
def test_task_not_lost():
    driver_task_id = utils.submit_job(app_url=utils.SPARK_EXAMPLES,
                                      app_args="1500",   # Long enough to examine the Executor's task info
                                      args=["--conf", "spark.cores.max=1",
                                            "--class", "org.apache.spark.examples.SparkPi"])

    # Wait until executor is running
    utils.wait_for_executors_running(SPARK_PI_FW_NAME, 1)

    # Check Executor task ID - should be 0, the first task.
    # If it's > 0, that means the first task was lost.
    executor_task = shakedown.get_service_tasks(SPARK_PI_FW_NAME)[0]
    assert executor_task['id'] == "0"

    # Check job output
    utils.check_job_output(driver_task_id, "Pi is roughly 3")


@pytest.mark.xfail(utils.is_strict(), reason="Currently fails in strict mode")
@pytest.mark.sanity
@pytest.mark.smoke
def test_jar(app_name=utils.SPARK_APP_NAME):
    master_url = ("https" if utils.is_strict() else "http") + "://leader.mesos:5050"
    spark_job_runner_args = '{} dcos \\"*\\" spark:only 2 --auth-token={}'.format(
        master_url,
        shakedown.dcos_acs_token())
    jar_url = utils.upload_file(os.getenv('TEST_JAR_PATH'))
    utils.run_tests(app_url=jar_url,
                    app_args=spark_job_runner_args,
                    expected_output="All tests passed",
                    app_name=app_name,
                    args=["--class", 'com.typesafe.spark.test.mesos.framework.runners.SparkJobRunner'])


@pytest.mark.sanity
@pytest.mark.smoke
def test_rpc_auth():
    secret_name = "sparkauth"

    rc, stdout, stderr = sdk_cmd.run_raw_cli("{pkg} secret /{secret}".format(
        pkg=utils.SPARK_PACKAGE_NAME, secret=secret_name))
    assert rc == 0, "Failed to generate Spark auth secret, stderr {err} stdout {out}".format(err=stderr, out=stdout)

    args = ["--executor-auth-secret", secret_name,
            "--class", "org.apache.spark.examples.SparkPi"]

    utils.run_tests(app_url=utils.SPARK_EXAMPLES,
                    app_args="100",
                    expected_output="Pi is roughly 3",
                    app_name="/spark",
                    args=args)


@pytest.mark.sanity
def test_sparkPi(app_name=utils.SPARK_APP_NAME):
    utils.run_tests(app_url=utils.SPARK_EXAMPLES,
                    app_args="100",
                    expected_output="Pi is roughly 3",
                    app_name=app_name,
                    args=["--class org.apache.spark.examples.SparkPi"])


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
                    args=["--py-files", py_file_url])


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
                    args=["--conf", "spark.mesos.network.name=dcos",
                          "--class", "org.apache.spark.examples.SparkPi"])


#@pytest.mark.skip("Enable when SPARK-21694 is merged and released in DC/OS Spark")
@pytest.mark.sanity
@pytest.mark.smoke
def test_cni_labels():
    driver_task_id = utils.submit_job(app_url=utils.SPARK_EXAMPLES,
                                      app_args="3000",   # Long enough to examine the Driver's & Executor's task infos
                                      args=["--conf", "spark.mesos.network.name=dcos",
                                            "--conf", "spark.mesos.network.labels=key1:val1,key2:val2",
                                            "--conf", "spark.cores.max={}".format(CNI_TEST_NUM_EXECUTORS),
                                            "--class", "org.apache.spark.examples.SparkPi"])

    # Wait until executors are running
    utils.wait_for_executors_running(SPARK_PI_FW_NAME, CNI_TEST_NUM_EXECUTORS)

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


@pytest.mark.sanity
@pytest.mark.smoke
def test_s3():
    def make_credential_secret(envvar, secret_path):
        rc, stdout, stderr = sdk_cmd.run_raw_cli("security secrets create {p} -v {e}"
                                                 .format(p=secret_path, e=os.environ[envvar]))
        assert rc == 0, "Failed to create secret {secret} from envvar {envvar}, stderr: {err}, stdout: {out}".format(
            secret=secret_path, envvar=envvar, err=stderr, out=stdout)

    LOGGER.info("Creating AWS secrets")

    aws_access_key_secret_path = "aws_access_key_id"
    aws_secret_access_key_path = "aws_secret_access_key"

    make_credential_secret(envvar="AWS_ACCESS_KEY_ID", secret_path="/{}".format(aws_access_key_secret_path))
    make_credential_secret(envvar="AWS_SECRET_ACCESS_KEY", secret_path="/{}".format(aws_secret_access_key_path))

    linecount_path = os.path.join(THIS_DIR, 'resources', 'linecount.txt')
    s3.upload_file(linecount_path)

    app_args = "--readUrl {} --writeUrl {}".format(
        s3.s3n_url('linecount.txt'),
        s3.s3n_url("linecount-out"))

    args = ["--conf", "spark.mesos.containerizer=mesos",
            "--conf",
            "spark.mesos.driver.secret.names=/{key},/{secret}".format(
                key=aws_access_key_secret_path, secret=aws_secret_access_key_path),
            "--conf",
            "spark.mesos.driver.secret.envkeys=AWS_ACCESS_KEY_ID,AWS_SECRET_ACCESS_KEY",
            "--class", "S3Job"]
    utils.run_tests(app_url=utils._scala_test_jar_url(),
                    app_args=app_args,
                    expected_output="Read 3 lines",
                    args=args)

    assert len(list(s3.list("linecount-out"))) > 0

    app_args = "--readUrl {} --countOnly".format(s3.s3n_url('linecount.txt'))

    args = ["--conf",
            "spark.mesos.driverEnv.AWS_ACCESS_KEY_ID={}".format(
                os.environ["AWS_ACCESS_KEY_ID"]),
            "--conf",
            "spark.mesos.driverEnv.AWS_SECRET_ACCESS_KEY={}".format(
                os.environ["AWS_SECRET_ACCESS_KEY"]),
            "--class", "S3Job"]
    utils.run_tests(app_url=utils._scala_test_jar_url(),
                    app_args=app_args,
                    expected_output="Read 3 lines",
                    args=args)

    app_args = "--countOnly --readUrl {}".format(s3.s3n_url('linecount.txt'))

    args = ["--conf",
            "spark.mesos.driverEnv.AWS_ACCESS_KEY_ID={}".format(
                os.environ["AWS_ACCESS_KEY_ID"]),
            "--conf",
            "spark.mesos.driverEnv.AWS_SECRET_ACCESS_KEY={}".format(
                os.environ["AWS_SECRET_ACCESS_KEY"]),
            "--class", "S3Job"]
    utils.run_tests(app_url=utils._scala_test_jar_url(),
                    app_args=app_args,
                    expected_output="Read 3 lines",
                    args=args)


# Skip DC/OS < 1.10, because it doesn't have adminrouter support for service groups.
@pytest.mark.skipif('shakedown.dcos_version_less_than("1.10")')
@pytest.mark.sanity
@pytest.mark.smoke
def test_marathon_group():
    app_id = utils.FOLDERED_SPARK_APP_NAME
    utils.require_spark(service_name=app_id, marathon_group=app_id)
    test_sparkPi(app_name=app_id)
    LOGGER.info("Uninstalling app_id={}".format(app_id))


@pytest.mark.sanity
def test_cli_multiple_spaces():
    utils.run_tests(app_url=utils.SPARK_EXAMPLES,
                    app_args="30",
                    expected_output="Pi is roughly 3",
                    args=["--conf ", "spark.cores.max=2",
                          " --class  ", "org.apache.spark.examples.SparkPi"])


# Skip DC/OS < 1.10, because it doesn't have support for file-based secrets.
@pytest.mark.skipif('shakedown.dcos_version_less_than("1.10")')
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
    shakedown.run_dcos_command('security secrets create /{} --value-file {}'.format(keystore_secret, keystore_path))
    shakedown.run_dcos_command('security secrets create /{} --value-file {}'.format(truststore_secret, truststore_path))
    shakedown.run_dcos_command('security secrets create /{} --value {}'.format(my_secret, my_secret_content))
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
        shakedown.run_dcos_command('security secrets delete /{}'.format(keystore_secret))
        shakedown.run_dcos_command('security secrets delete /{}'.format(truststore_secret))
        shakedown.run_dcos_command('security secrets delete /{}'.format(my_secret))


def _scala_test_jar_url():
    return s3.http_url(os.path.basename(os.environ["SCALA_TEST_JAR_PATH"]))
