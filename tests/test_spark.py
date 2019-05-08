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

import sdk_cmd
import sdk_security
import sdk_tasks
import sdk_utils

import spark_s3 as s3
import spark_utils as utils


log = logging.getLogger(__name__)
THIS_DIR = os.path.dirname(os.path.abspath(__file__))
SPARK_PI_FW_NAME = "Spark Pi"
CNI_TEST_NUM_EXECUTORS = 1


@pytest.fixture(scope='module', autouse=True)
def setup_spark(configure_security_spark, configure_universe):
    try:
        utils.upload_dcos_test_jar()
        utils.require_spark()
        yield
    finally:
        utils.teardown_spark()


@pytest.mark.sanity
def test_task_not_lost():
    driver_task_id = utils.submit_job(app_url=utils.SPARK_EXAMPLES,
                                      app_args="1500",   # Long enough to examine the Executor's task info
                                      args=["--conf spark.cores.max=1",
                                            "--class org.apache.spark.examples.SparkPi"])

    # Wait until executor is running
    sdk_tasks.check_running(SPARK_PI_FW_NAME, 1, timeout_seconds=600)

    # Check Executor task ID - should end with 0, the first task.
    # If it's > 0, that means the first task was lost.
    assert sdk_tasks.get_task_ids(SPARK_PI_FW_NAME, '')[0].endswith('-0')

    # Check job output
    utils.check_job_output(driver_task_id, "Pi is roughly 3")


@pytest.mark.sanity
def test_mesos_label_support():
    driver_task_id = utils.submit_job(app_url=utils.SPARK_EXAMPLES,
                                      app_args="150",
                                      args=["--conf spark.cores.max=1",
                                            "--conf spark.mesos.driver.labels=foo:bar", # pass a test label
                                            "--class org.apache.spark.examples.SparkPi"])

    driver_task_info = sdk_cmd._get_task_info(driver_task_id)
    expected = {'key': 'foo', 'value': 'bar'}
    assert expected in driver_task_info['labels']


@pytest.mark.sanity
def test_dispatcher_liveliness_after_malformed_request():
    # Get dispatcher ip and port
    dispatcher_details = sdk_cmd._get_task_info(utils.SPARK_PACKAGE_NAME)
    ip = dispatcher_details['statuses'][0]['container_status']['network_infos'][0]['ip_addresses'][0]['ip_address']
    port = dispatcher_details['discovery']['ports']['ports'][0]['number']

    # Sends resource/<filename> as a submission request to dispatcher and returns action field
    def submit_dispatcher_request(request_filename):
        with open(os.path.join(THIS_DIR, 'resources', request_filename), 'r') as file:
            request = file.read()
        curl_command = '''curl -d '{}' -H "Content-Type: application/json" -X POST "http://{}:{}/v1/submissions/create"''' \
            .format(request, ip, port)
        success, output = sdk_cmd.master_ssh(curl_command)
        assert success
        return json.loads(output)['action']

    # Perform valid, invalid and valid again requests
    assert submit_dispatcher_request('dispatcher_submit_request_valid.json') == 'CreateSubmissionResponse'
    assert submit_dispatcher_request('dispatcher_submit_request_missing_args.json') == 'ErrorResponse'
    assert submit_dispatcher_request('dispatcher_submit_request_valid.json') == 'CreateSubmissionResponse'


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

    log.info('Driver 1 state: %s, Driver 2 state: %s'%(data_1['driverState'], data_2['driverState']))
    return data_1['driverState'] == data_2["driverState"] == "FINISHED"


@pytest.mark.sanity
def test_unique_task_ids():
    log.info('Submitting two sample Spark Applications')
    submit_args = ["--conf spark.cores.max=1", "--class org.apache.spark.examples.SparkPi"]

    driver_id_1 = utils.submit_job(app_url=utils.SPARK_EXAMPLES,
                                   app_args="100",
                                   args=submit_args)

    driver_id_2 = utils.submit_job(app_url=utils.SPARK_EXAMPLES,
                                   app_args="100",
                                   args=submit_args)

    log.info('Two Spark Applications submitted. Driver 1 ID: %s, Driver 2 ID: %s'%(driver_id_1,driver_id_2))
    log.info('Waiting for completion. Polling state')
    completed = wait_for_jobs_completion(driver_id_1, driver_id_2)

    assert completed == True, 'Sample Spark Applications failed to successfully complete within given time'
    out = sdk_cmd.run_cli("task --completed --json")
    data = json.loads(out)

    log.info('Collecting tasks that belong to the drivers created in this test')
    task_ids = []
    for d in data:
        if driver_id_1 in d['framework_id'] or driver_id_2 in d['framework_id']:
            task_ids.append(d['id'])

    log.info('Tasks found: %s'%(' '.join(task_ids)))
    assert len(task_ids) == len(set(task_ids)), 'Task ids for two independent Spark Applications contain duplicates'


@pytest.mark.xfail(sdk_utils.is_strict_mode(), reason="Currently fails in strict mode")
@pytest.mark.skip(reason="Currently fails due to CI misconfiguration") #TODO: Fix CI/update mesos-integration-tests
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
        args=["--conf spark.driver.extraJavaOptions='-XX:+PrintGCDetails -XX:+PrintGCTimeStamps -Dparam3=\\\"valA valB\\\"'",
              "--class MultiConfs"])


@pytest.mark.sanity
def test_jars_flag(service_name=utils.SPARK_SERVICE_NAME):
    uploadedJarUrl = utils.dcos_test_jar_url()
    jarName = uploadedJarUrl.split("/")[-1] # dcos-spark-scala-assembly-XX-SNAPSHOT.jar
    utils.run_tests(
        app_url=utils.SPARK_EXAMPLES, # submit an app that does not include class 'MultiConfs'
        app_args="",
        expected_output="spark.driver.extraClassPath,/mnt/mesos/sandbox/{}".format(jarName),
        service_name=service_name,
        args=["--jars {}".format(uploadedJarUrl),
              "--class MultiConfs"])

@pytest.mark.sanity
def test_packages_flag():
    utils.run_tests(
        app_url=utils.dcos_test_jar_url(),
        app_args="20",
        expected_output="210",
        args=["--packages com.google.guava:guava:23.0",
              "--class ProvidedPackages"])


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
def test_supervise_conflict_frameworkid():
    job_service_name = "MockTaskRunner"

    @retrying.retry(
        wait_fixed=1000,
        stop_max_delay=600 * 1000,
        retry_on_result=lambda res: not res)
    def wait_job_present(present):
        svc = shakedown.get_service(job_service_name)
        if present:
            return svc is not None
        else:
            return svc is None

    job_args = ["--supervise",
                "--class", "MockTaskRunner",
                "--conf", "spark.cores.max=1",
                "--conf", "spark.executors.cores=1"]

    try:
        driver_id = utils.submit_job(app_url=utils.dcos_test_jar_url(),
                app_args="1 1800",
                service_name=utils.SPARK_SERVICE_NAME,
                args=job_args)
        log.info("Started supervised driver {}".format(driver_id))

        wait_job_present(True)
        log.info("Job has registered")

        sdk_tasks.check_running(job_service_name, 1)
        log.info("Job has running executors")

        service_info = shakedown.get_service(job_service_name).dict()
        driver_regex = "spark.mesos.driver.frameworkId={}".format(service_info['id'])
        kill_status = sdk_cmd.kill_task_with_pattern(driver_regex, service_info['hostname'])

        wait_job_present(False)

        wait_job_present(True)
        log.info("Job has re-registered")
        sdk_tasks.check_running(job_service_name, 1)
        log.info("Job has re-started")

        restarted_service_info = shakedown.get_service(job_service_name).dict()
        assert service_info['id'] != restarted_service_info['id'], "Job has restarted with same framework Id"
    finally:
        kill_info = utils.kill_driver(driver_id, utils.SPARK_SERVICE_NAME)
        log.info("{}".format(kill_info))
        assert json.loads(kill_info)["success"], "Failed to kill spark job"
        wait_job_present(False)
