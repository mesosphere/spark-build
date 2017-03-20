# Env:
#   AWS_ACCESS_KEY_ID
#   AWS_SECRET_ACCESS_KEY
#   COMMONS_DIR
#   S3_BUCKET
#   S3_PREFIX
#   TEST_JAR_PATH // /path/to/mesos-spark-integration-tests.jar
#   SCALA_TEST_JAR_PATH // /path/to/dcos-spark-scala-tests.jar

import dcos.config
import dcos.http
import dcos.package

import logging
import os
import pytest
import re
import s3
import shakedown
import subprocess
import time
import urllib


def _init_logging():
    logging.basicConfig(level=logging.INFO)
    logging.getLogger('dcos').setLevel(logging.WARNING)


_init_logging()
LOGGER = logging.getLogger(__name__)
THIS_DIR = os.path.dirname(os.path.abspath(__file__))


def setup_module(module):
    if _hdfs_enabled():
        _require_hdfs()
    _require_spark()


def teardown_module(module):
    shakedown.uninstall_package_and_wait('spark')
    if _hdfs_enabled():
        shakedown.uninstall_package_and_wait('hdfs')
        _run_janitor('hdfs')


def test_jar():
    master_url = ("https" if _is_strict() else "http") + "://leader.mesos:5050"
    spark_job_runner_args = '{} dcos \\"*\\" spark:only 2 --auth-token={}'.format(
        master_url,
        shakedown.dcos_acs_token())
    jar_url = _upload_file(os.getenv('TEST_JAR_PATH'))
    _run_tests(jar_url,
               spark_job_runner_args,
               "All tests passed",
               ["--class", 'com.typesafe.spark.test.mesos.framework.runners.SparkJobRunner'])


def test_teragen():
    if _hdfs_enabled():
        jar_url = "https://downloads.mesosphere.io/spark/examples/spark-terasort-1.0-jar-with-dependencies_2.11.jar"
        _run_tests(jar_url,
                   "1g hdfs:///terasort_in",
                   "Number of records written",
                   ["--class", "com.github.ehiggs.spark.terasort.TeraGen"])


def test_python():
    python_script_path = os.path.join(THIS_DIR, 'jobs', 'python', 'pi_with_include.py')
    python_script_url = _upload_file(python_script_path)
    py_file_path = os.path.join(THIS_DIR, 'jobs', 'python', 'PySparkTestInclude.py')
    py_file_url = _upload_file(py_file_path)
    _run_tests(python_script_url,
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
    _run_tests(
        "http://infinity-artifacts.s3.amazonaws.com/spark/sparkjob-assembly-1.0.jar",
        "hdfs:///krb5.conf",
        "number of words in",
        ["--class", "HDFSWordCount",
         "--principal",  principal,
         "--keytab", keytab,
         "--conf", "sun.security.krb5.debug=true"])


def test_r():
    r_script_path = os.path.join(THIS_DIR, 'jobs', 'R', 'dataframe.R')
    r_script_url = _upload_file(r_script_path)
    _run_tests(r_script_url,
               '',
               "Justin")


def test_cni():
    SPARK_EXAMPLES="http://downloads.mesosphere.com/spark/assets/spark-examples_2.11-2.0.1.jar"
    _run_tests(SPARK_EXAMPLES,
               "",
               "Pi is roughly 3",
               ["--conf", "spark.mesos.network.name=dcos",
                "--class", "org.apache.spark.examples.SparkPi"])


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
    _run_tests(_upload_file(os.environ["SCALA_TEST_JAR_PATH"]),
               app_args,
               "",
               args)

    assert len(list(s3.list("linecount-out"))) > 0


def _hdfs_enabled():
    return os.environ.get("HDFS_ENABLED") != "false"


def _require_hdfs():
    LOGGER.info("Ensuring HDFS is installed.")

    _require_package('hdfs', _get_hdfs_options())
    _wait_for_hdfs()


def _require_spark():
    LOGGER.info("Ensuring Spark is installed.")

    _require_package('spark', _get_spark_options())
    _wait_for_spark()


# This should be in shakedown (DCOS_OSS-679)
def _require_package(pkg_name, options = {}):
    pkg_manager = dcos.package.get_package_manager()
    installed_pkgs = dcos.package.installed_packages(pkg_manager, None, None, False)

    if any(pkg['name'] == pkg_name for pkg in installed_pkgs):
        LOGGER.info("Package {} already installed.".format(pkg_name))
    else:
        LOGGER.info("Installing package {}".format(pkg_name))
        shakedown.install_package(
            pkg_name,
            options_json=options,
            wait_for_completion=True)


def _wait_for_spark():
    def pred():
        dcos_url = dcos.config.get_config_val("core.dcos_url")
        spark_url = urllib.parse.urljoin(dcos_url, "/service/spark")
        status_code = dcos.http.get(spark_url).status_code
        return status_code == 200

    shakedown.wait_for(pred)


def _get_hdfs_options():
    if _is_strict():
        options = {'service': {'principal': 'service-acct', 'secret_name': 'secret'}}
    else:
        options = {}
    return options


def _wait_for_hdfs():
    shakedown.wait_for(_is_hdfs_ready, ignore_exceptions=False, timeout_seconds=900)


DEFAULT_HDFS_TASK_COUNT=10
def _is_hdfs_ready(expected_tasks = DEFAULT_HDFS_TASK_COUNT):
    running_tasks = [t for t in shakedown.get_service_tasks('hdfs') \
                     if t['state'] == 'TASK_RUNNING']
    return len(running_tasks) >= expected_tasks


def _get_spark_options():
    if _hdfs_enabled():
        options = {"hdfs":
                   {"config-url":
                    "http://api.hdfs.marathon.l4lb.thisdcos.directory/v1/endpoints"}}
    else:
        options = {}

    if _is_strict():
        options.update({'service':
                        {"principal": "service-acct"},
                        "security":
                        {"mesos":
                         {"authentication":
                          {"secret_name": "secret"}}}})

    return options


def _install_spark():
    options = {"hdfs":
               {"config-url":
                "http://api.hdfs.marathon.l4lb.thisdcos.directory/v1/endpoints"}}

    if _is_strict():
        options['service'] = {"user": "nobody",
                              "principal": "service-acct"}
        options['security'] = {"mesos": {"authentication": {"secret_name": "secret"}}}

    shakedown.install_package('spark', options_json=options, wait_for_completion=True)

    def pred():
        dcos_url = dcos.config.get_config_val("core.dcos_url")
        spark_url = urllib.parse.urljoin(dcos_url, "/service/spark")
        status_code = dcos.http.get(spark_url).status_code
        return status_code == 200

    shakedown.spinner.wait_for(pred)


def _is_strict():
    return os.environ.get('SECURITY') == 'strict'


def _run_janitor(service_name):
    janitor_cmd = (
        'docker run mesosphere/janitor /janitor.py '
        '-r {svc}-role -p {svc}-principal -z dcos-service-{svc} --auth_token={auth}')
    shakedown.run_command_on_master(janitor_cmd.format(
        svc=service_name,
        auth=shakedown.dcos_acs_token()))


def _run_tests(app_url, app_args, expected_output, args=[]):
    task_id = _submit_job(app_url, app_args, args)
    LOGGER.info('Waiting for task id={} to complete'.format(task_id))
    shakedown.wait_for_task_completion(task_id)
    log = _task_log(task_id)
    LOGGER.info("task log: {}".format(log))
    assert expected_output in log


def _submit_job(app_url, app_args, args=[]):
    if _is_strict():
        config['spark.mesos.driverEnv.MESOS_MODULES'] = \
            'file:///opt/mesosphere/etc/mesos-scheduler-modules/dcos_authenticatee_module.json'
        config['spark.mesos.driverEnv.MESOS_AUTHENTICATEE'] = 'com_mesosphere_dcos_ClassicRPCAuthenticatee'
        config['spark.mesos.principal'] = 'service-acct'
    args_str = ' '.join(args + ["--conf", "spark.driver.memory=2g"])
    submit_args = ' '.join([args_str, app_url, app_args])
    cmd = 'dcos --log-level=DEBUG spark --verbose run --submit-args="{0}"'.format(submit_args)

    LOGGER.info("Running {}".format(cmd))
    stdout = subprocess.check_output(cmd, shell=True).decode('utf-8')

    LOGGER.info("stdout: {}".format(stdout))

    regex = r"Submission id: (\S+)"
    match = re.search(regex, stdout)
    return match.group(1)


def _upload_file(file_path):
    print("Uploading {} to s3://{}/{}".format(
        file_path,
        os.environ['S3_BUCKET'],
        os.environ['S3_PREFIX']))

    s3.upload_file(file_path)

    basename = os.path.basename(file_path)
    return s3.http_url(basename)


def _task_log(task_id):
    cmd = "dcos task log --completed --lines=1000 {}".format(task_id)
    LOGGER.info("Running {}".format(cmd))
    stdout = subprocess.check_output(cmd, shell=True).decode('utf-8')
    return stdout
