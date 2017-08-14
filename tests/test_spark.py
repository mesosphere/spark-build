# Env:
#   AWS_ACCESS_KEY_ID
#   AWS_SECRET_ACCESS_KEY
#   COMMONS_DIR
#   S3_BUCKET
#   S3_PREFIX
#   TEST_JAR_PATH // /path/to/mesos-spark-integration-tests.jar
#   SCALA_TEST_JAR_PATH // /path/to/dcos-spark-scala-tests.jar

import dcos.config
import logging
import os
import pytest
import s3
import shakedown

import utils
from utils import SPARK_PACKAGE_NAME, HDFS_PACKAGE_NAME, HDFS_SERVICE_NAME


LOGGER = logging.getLogger(__name__)
THIS_DIR = os.path.dirname(os.path.abspath(__file__))
SPARK_PI_FW_NAME = "Spark Pi"
CNI_TEST_NUM_EXECUTORS = 1


def setup_module(module):
    if utils.hdfs_enabled():
        utils.require_hdfs()
    utils.require_spark()
    utils.upload_file(os.environ["SCALA_TEST_JAR_PATH"])


def teardown_module(module):
    shakedown.uninstall_package_and_wait(SPARK_PACKAGE_NAME)
    if utils.hdfs_enabled():
        shakedown.uninstall_package_and_wait(HDFS_PACKAGE_NAME, HDFS_SERVICE_NAME)
        _run_janitor(HDFS_SERVICE_NAME)


@pytest.mark.sanity
def test_jar():
    master_url = ("https" if utils.is_strict() else "http") + "://leader.mesos:5050"
    spark_job_runner_args = '{} dcos \\"*\\" spark:only 2 --auth-token={}'.format(
        master_url,
        shakedown.dcos_acs_token())
    jar_url = utils.upload_file(os.getenv('TEST_JAR_PATH'))
    utils.run_tests(jar_url,
                    spark_job_runner_args,
                    "All tests passed",
                    ["--class", 'com.typesafe.spark.test.mesos.framework.runners.SparkJobRunner'])


@pytest.mark.sanity
def test_teragen():
    if utils.hdfs_enabled():
        jar_url = 'https://downloads.mesosphere.io/spark/examples/spark-terasort-1.0-jar-with-dependencies_2.11.jar'
        utils.run_tests(jar_url,
                        "1g hdfs:///terasort_in",
                        "Number of records written",
                        ["--class", "com.github.ehiggs.spark.terasort.TeraGen"])


@pytest.mark.sanity
def test_python():
    python_script_path = os.path.join(THIS_DIR, 'jobs', 'python', 'pi_with_include.py')
    python_script_url = utils.upload_file(python_script_path)
    py_file_path = os.path.join(THIS_DIR, 'jobs', 'python', 'PySparkTestInclude.py')
    py_file_url = utils.upload_file(py_file_path)
    utils.run_tests(python_script_url,
                    "30",
                    "Pi is roughly 3",
                    ["--py-files", py_file_url])


@pytest.mark.skip(reason="must be run manually against a kerberized HDFS")
def test_kerberos():
    '''This test must be run manually against a kerberized HDFS cluster.
    Instructions for setting one up are here:
    https://docs.google.com/document/d/1lqlEIs98j1VsAyoEYnhYoaNmYylcoaBAwHpD29yKjU4.
    You must set 'principal' and 'keytab' to the appropriate values,
    and change 'krb5.conf' to the name of some text file you've
    written to HDFS.

    '''

    principal = "nn/ip-10-0-2-134.us-west-2.compute.internal@LOCAL"
    keytab = "nn.ip-10-0-2-134.us-west-2.compute.internal.keytab"
    utils.run_tests(
        "http://infinity-artifacts.s3.amazonaws.com/spark/sparkjob-assembly-1.0.jar",
        "hdfs:///krb5.conf",
        "number of words in",
        ["--class", "HDFSWordCount",
         "--principal",  principal,
         "--keytab", keytab,
         "--conf", "sun.security.krb5.debug=true"])


@pytest.mark.sanity
def test_r():
    r_script_path = os.path.join(THIS_DIR, 'jobs', 'R', 'dataframe.R')
    r_script_url = utils.upload_file(r_script_path)
    utils.run_tests(r_script_url,
               '',
               "Justin")


@pytest.mark.sanity
def test_cni():
    SPARK_EXAMPLES="http://downloads.mesosphere.com/spark/assets/spark-examples_2.11-2.0.1.jar"
    utils.run_tests(SPARK_EXAMPLES,
               "",
               "Pi is roughly 3",
               ["--conf", "spark.mesos.network.name=dcos",
                "--class", "org.apache.spark.examples.SparkPi"])


@pytest.mark.skip("Enable when SPARK-21694 is merged and released in DC/OS Spark")
@pytest.mark.sanity
def test_cni_labels():
    SPARK_EXAMPLES="http://downloads.mesosphere.com/spark/assets/spark-examples_2.11-2.0.1.jar"
    driver_task_id = utils.submit_job(SPARK_EXAMPLES,
                               "3000",   # Long enough to examine the Driver's & Executor's task infos
                               ["--conf", "spark.mesos.network.name=dcos",
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
def test_s3():
    linecount_path = os.path.join(THIS_DIR, 'resources', 'linecount.txt')
    s3.upload_file(linecount_path)

    app_args = "{} {}".format(
        s3.s3n_url('linecount.txt'),
        s3.s3n_url("linecount-out"))

    args = ["--conf",
            "spark.mesos.driverEnv.AWS_ACCESS_KEY_ID={}".format(
                os.environ["AWS_ACCESS_KEY_ID"]),
            "--conf",
            "spark.mesos.driverEnv.AWS_SECRET_ACCESS_KEY={}".format(
                os.environ["AWS_SECRET_ACCESS_KEY"]),
            "--class", "S3Job"]
    utils.run_tests(_scala_test_jar_url(),
                    app_args,
                    "",
                    args)

    assert len(list(s3.list("linecount-out"))) > 0


# Skip DC/OS < 1.10, because it doesn't have adminrouter support for service groups.
@pytest.mark.skipif('shakedown.dcos_version_less_than("1.10")')
@pytest.mark.sanity
def test_marathon_group():
    app_id = "/path/to/spark"
    options = {"service": {"name": app_id}}
    utils.require_spark(options=options, service_name=app_id)
    dcos.config.set_val("spark.app_id", app_id)

    try:
        test_jar()

        LOGGER.info("Uninstalling app_id={}".format(app_id))
        shakedown.uninstall_package_and_wait(SPARK_PACKAGE_NAME, app_id)
    finally:
        dcos.config.unset("spark.app_id")


@pytest.mark.skip(reason="Skip until secrets are released in DC/OS Spark: SPARK-466")
@pytest.mark.sanity
def test_secrets():
    try:
        secret_name = "secret"
        secret_contents = "mgummelt"
        utils.create_secret(secret_name, secret_contents)

        secret_file_name = "secret_file"
        output = "Contents of file {}: {}".format(secret_file_name, secret_contents)
        args = ["--conf", "spark.mesos.containerizer=mesos",
                "--conf", "spark.mesos.driver.secret.name={}".format(secret_name),
                "--conf", "spark.mesos.driver.secret.filename={}".format(secret_file_name),
                "--class", "SecretsJob"]
        utils.run_tests(_scala_test_jar_url(),
                        secret_file_name,
                        output,
                        args)
    finally:
        utils.delete_secret(secret_name)


def _run_janitor(service_name):
    janitor_cmd = (
        'docker run mesosphere/janitor /janitor.py '
        '-r {svc}-role -p {svc}-principal -z dcos-service-{svc} --auth_token={auth}')
    shakedown.run_command_on_master(janitor_cmd.format(
        svc=service_name,
        auth=shakedown.dcos_acs_token()))


def _scala_test_jar_url():
    return s3.http_url(os.path.basename(os.environ["SCALA_TEST_JAR_PATH"]))
