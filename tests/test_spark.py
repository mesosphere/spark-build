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
import s3
import json
import shakedown

import utils
from utils import SPARK_PACKAGE_NAME, HDFS_PACKAGE_NAME, HDFS_SERVICE_NAME


LOGGER = logging.getLogger(__name__)
THIS_DIR = os.path.dirname(os.path.abspath(__file__))
SPARK_PI_FW_NAME = "Spark Pi"
CNI_TEST_NUM_EXECUTORS = 1
SPARK_EXAMPLES = "http://downloads.mesosphere.com/spark/assets/spark-examples_2.11-2.0.1.jar"
SECRET_NAME = "secret"
SECRET_CONTENTS = "mgummelt"


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
def test_jar(app_name="/spark"):
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
def test_sparkPi():
    utils.run_tests(app_url=SPARK_EXAMPLES,
                    app_args="100",
                    expected_output="Pi is roughly 3",
                    app_name="/spark",
                    args=["--class org.apache.spark.examples.SparkPi"])


@pytest.mark.sanity
def test_teragen():
    if utils.hdfs_enabled():
        jar_url = 'https://downloads.mesosphere.io/spark/examples/spark-terasort-1.0-jar-with-dependencies_2.11.jar'
        utils.run_tests(app_url=jar_url,
                        app_args="1g hdfs:///terasort_in",
                        expected_output="Number of records written",
                        app_name="/spark",
                        args=["--class", "com.github.ehiggs.spark.terasort.TeraGen"])


@pytest.mark.sanity
def test_supervise():
    def streaming_job_registered():
        return shakedown.get_service("HdfsWordCount") is not None

    def streaming_job_is_not_running():
        return not streaming_job_registered()

    def has_running_executors():
        f = shakedown.get_service("HdfsWordCount")
        if f is None:
            return False
        else:
            return len([x for x in f.dict()["tasks"] if x["state"] == "TASK_RUNNING"]) > 0

    driver_id = utils.submit_job(app_url=SPARK_EXAMPLES,
                                 app_args="file:///mnt/mesos/sandbox/",
                                 app_name="/spark",
                                 args=["--supervise",
                                       "--class", "org.apache.spark.examples.streaming.HdfsWordCount",
                                       "--conf", "spark.cores.max=8",
                                       "--conf", "spark.executors.cores=4"])
    LOGGER.info("Started supervised driver {}".format(driver_id))
    shakedown.wait_for(lambda: streaming_job_registered(),
                       ignore_exceptions=False,
                       timeout_seconds=600)
    LOGGER.info("Job has registered")
    shakedown.wait_for(lambda: has_running_executors(),
                       ignore_exceptions=False,
                       timeout_seconds=600)
    LOGGER.info("Job has running executors")

    host = shakedown.get_service("HdfsWordCount").dict()["hostname"]
    id = shakedown.get_service("HdfsWordCount").dict()["id"]
    driver_regex = "spark.mesos.driver.frameworkId={}".format(id)
    shakedown.kill_process_on_host(hostname=host, pattern=driver_regex)

    shakedown.wait_for(lambda: streaming_job_registered(),
                       ignore_exceptions=False,
                       timeout_seconds=600)
    LOGGER.info("Job has re-registered")
    shakedown.wait_for(lambda: has_running_executors(),
                       ignore_exceptions=False,
                       timeout_seconds=600)
    LOGGER.info("Job has re-started")
    out = utils.kill_driver(driver_id, "/spark")
    LOGGER.info("{}".format(out))
    out = json.loads(out)
    assert out["success"], "Failed to kill spark streaming job"
    shakedown.wait_for(lambda: streaming_job_is_not_running(),
                       ignore_exceptions=False,
                       timeout_seconds=600)


@pytest.mark.sanity
def test_python():
    python_script_path = os.path.join(THIS_DIR, 'jobs', 'python', 'pi_with_include.py')
    python_script_url = utils.upload_file(python_script_path)
    py_file_path = os.path.join(THIS_DIR, 'jobs', 'python', 'PySparkTestInclude.py')
    py_file_url = utils.upload_file(py_file_path)
    utils.run_tests(app_url=python_script_url,
                    app_args="30",
                    expected_output="Pi is roughly 3",
                    app_name="/spark",
                    args=["--py-files", py_file_url])


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
        app_url="http://infinity-artifacts.s3.amazonaws.com/spark/sparkjob-assembly-1.0.jar",
        app_args="hdfs:///krb5.conf",
        expected_output="number of words in",
        app_name="/spark",
        args=["--class", "HDFSWordCount",
         "--principal",  principal,
         "--keytab", keytab,
         "--conf", "sun.security.krb5.debug=true"])


@pytest.mark.sanity
def test_r():
    r_script_path = os.path.join(THIS_DIR, 'jobs', 'R', 'dataframe.R')
    r_script_url = utils.upload_file(r_script_path)
    utils.run_tests(app_url=r_script_url,
                    app_args='',
                    expected_output="Justin",
                    app_name="/spark")


@pytest.mark.sanity
def test_cni():
    SPARK_EXAMPLES="http://downloads.mesosphere.com/spark/assets/spark-examples_2.11-2.0.1.jar"
    utils.run_tests(app_url=SPARK_EXAMPLES,
                    app_args="",
                    expected_output="Pi is roughly 3",
                    app_name="/spark",
                    args=["--conf", "spark.mesos.network.name=dcos",
                          "--class", "org.apache.spark.examples.SparkPi"])


#@pytest.mark.skip("Enable when SPARK-21694 is merged and released in DC/OS Spark")
@pytest.mark.sanity
def test_cni_labels():
    driver_task_id = utils.submit_job(app_url=SPARK_EXAMPLES,
                                      app_args="3000",   # Long enough to examine the Driver's & Executor's task infos
                                      app_name="/spark",
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
    utils.run_tests(app_url=_scala_test_jar_url(),
                    app_args=app_args,
                    expected_output="",
                    app_name="/spark",
                    args=args)

    assert len(list(s3.list("linecount-out"))) > 0


# Skip DC/OS < 1.10, because it doesn't have adminrouter support for service groups.
@pytest.mark.skipif('shakedown.dcos_version_less_than("1.10")')
@pytest.mark.sanity
def test_marathon_group():
    app_id = "/path/to/spark"
    options = {"service": {"name": app_id}}
    utils.require_spark(options=options, service_name=app_id)
    test_jar(app_name=app_id)
    LOGGER.info("Uninstalling app_id={}".format(app_id))
    #shakedown.uninstall_package_and_wait(SPARK_PACKAGE_NAME, app_id)


@pytest.mark.sanity
def test_secrets():
    secrets_handler = utils.SecretHandler(SECRET_NAME, SECRET_CONTENTS)
    r = secrets_handler.create_secret()
    assert r.ok, "Error creating secret, {}".format(r.content)
    secret_file_name = "secret_file"
    output = "Contents of file {}: {}".format(secret_file_name, SECRET_CONTENTS)
    args = ["--conf", "spark.mesos.containerizer=mesos",
            "--conf", "spark.mesos.driver.secret.name={}".format(SECRET_NAME),
            "--conf", "spark.mesos.driver.secret.filename={}".format(secret_file_name),
            "--class", "SecretsJob"]
    utils.run_tests(app_url=_scala_test_jar_url(),
                    app_args=secret_file_name,
                    expected_output=output,
                    app_name="/spark",
                    args=args)
    r = secrets_handler.delete_secret()
    if not r.ok:
        LOGGER.warn("Error when deleting secret, {}".format(r.content))


def _run_janitor(service_name):
    janitor_cmd = (
        'docker run mesosphere/janitor /janitor.py '
        '-r {svc}-role -p {svc}-principal -z dcos-service-{svc} --auth_token={auth}')
    shakedown.run_command_on_master(janitor_cmd.format(
        svc=service_name,
        auth=shakedown.dcos_acs_token()))


def _scala_test_jar_url():
    return s3.http_url(os.path.basename(os.environ["SCALA_TEST_JAR_PATH"]))
