import shakedown

import logging
import os
import re
import urllib
import urllib.parse

import sdk_cmd
import sdk_install
import sdk_security
import sdk_utils

import spark_s3

DCOS_SPARK_TEST_JAR_PATH_ENV = "DCOS_SPARK_TEST_JAR_PATH"
DCOS_SPARK_TEST_JAR_PATH = os.getenv(DCOS_SPARK_TEST_JAR_PATH_ENV, None)
DCOS_SPARK_TEST_JAR_URL_ENV = "DCOS_SPARK_TEST_JAR_URL"
DCOS_SPARK_TEST_JAR_URL = os.getenv(DCOS_SPARK_TEST_JAR_URL_ENV, None)

MESOS_SPARK_TEST_JAR_PATH_ENV = "MESOS_SPARK_TEST_JAR_PATH"
MESOS_SPARK_TEST_JAR_PATH = os.getenv(MESOS_SPARK_TEST_JAR_PATH_ENV, None)
MESOS_SPARK_TEST_JAR_URL_ENV = "MESOS_SPARK_TEST_JAR_URL"
MESOS_SPARK_TEST_JAR_URL = os.getenv(MESOS_SPARK_TEST_JAR_URL_ENV, None)

SPARK_SERVICE_ACCOUNT = os.getenv("SPARK_SERVICE_ACCOUNT", "spark-service-acct")
SPARK_SERVICE_ACCOUNT_SECRET = os.getenv("SPARK_SERVICE_ACCOUNT_SECRET", "spark-service-acct-secret")
SPARK_SERVICE_NAME = os.getenv("SPARK_SERVICE_NAME", "spark")
FOLDERED_SPARK_SERVICE_NAME = "/path/to/" + SPARK_SERVICE_NAME
SPARK_USER = os.getenv("SPARK_USER", "nobody")
SPARK_DRIVER_ROLE = os.getenv("SPARK_DRIVER_ROLE", "*")
JOB_WAIT_TIMEOUT_SEC = 1800

LOGGER = logging.getLogger(__name__)

SPARK_PACKAGE_NAME = os.getenv("SPARK_PACKAGE_NAME", "spark")
SPARK_EXAMPLES = "http://downloads.mesosphere.com/spark/assets/spark-examples_2.11-2.0.1.jar"


def _check_tests_assembly():
    if not DCOS_SPARK_TEST_JAR_URL and not os.path.exists(DCOS_SPARK_TEST_JAR_PATH):
        raise Exception('''Missing URL or path to file dcos-spark-scala-tests-assembly-[...].jar:
    - No URL: {}={}
    - File not found: {}={}'''.format(
        DCOS_SPARK_TEST_JAR_URL_ENV, DCOS_SPARK_TEST_JAR_URL,
        DCOS_SPARK_TEST_JAR_PATH_ENV, DCOS_SPARK_TEST_JAR_PATH))


def _check_mesos_integration_tests_assembly():
    if not MESOS_SPARK_TEST_JAR_URL and not os.path.exists(MESOS_SPARK_TEST_JAR_PATH):
        raise Exception('''Missing URL or path to file mesos-spark-integration-tests-assembly-[...].jar:
    - No URL: {}={}
    - File not found: {}={}'''.format(
        MESOS_SPARK_TEST_JAR_URL_ENV, MESOS_SPARK_TEST_JAR_URL,
        MESOS_SPARK_TEST_JAR_PATH_ENV, MESOS_SPARK_TEST_JAR_PATH))


def hdfs_enabled():
    return os.environ.get("HDFS_ENABLED") != "false"


def kafka_enabled():
    return os.environ.get("KAFKA_ENABLED") != "false"


def require_spark(service_name=SPARK_SERVICE_NAME, additional_options={}, zk='spark_mesos_dispatcher'):
    teardown_spark(service_name, zk)

    sdk_install.install(
        SPARK_PACKAGE_NAME,
        service_name,
        0,
        additional_options=_get_spark_options(service_name, additional_options),
        wait_for_deployment=False, # no deploy plan
        insert_strict_options=False) # lacks principal + secret_name options

    # wait for dispatcher to be reachable over HTTP
    sdk_cmd.service_request('GET', service_name, '', timeout_seconds=300)


# Note: zk may be customized in spark via 'spark.deploy.zookeeper.dir'
def teardown_spark(service_name=SPARK_SERVICE_NAME, zk='spark_mesos_dispatcher'):
    sdk_install.uninstall(
        SPARK_PACKAGE_NAME,
        service_name,
        role='spark-role-unused',
        service_account='spark-principal-ignored',
        zk=zk)

    if not sdk_utils.dcos_version_less_than('1.10'):
        # On 1.10+, sdk_uninstall doesn't run janitor. However Spark always needs it for ZK cleanup.
        sdk_install.retried_run_janitor(service_name, 'spark-role-unused', 'spark-principal-ignored', zk)


def _get_spark_options(service_name, additional_options):
    options = {
        "service": {
            "user": "nobody",
            "name": service_name
        }
    }

    if sdk_utils.is_strict_mode():
        # At the moment, we do this by hand because Spark doesn't quite line up with other services
        # with these options, and sdk_install assumes that we're following those conventions
        # Specifically, Spark's config.json lacks: service.principal, service.secret_name
        options["service"]["service_account"] = SPARK_SERVICE_ACCOUNT
        options["service"]["service_account_secret"] = SPARK_SERVICE_ACCOUNT_SECRET

    return sdk_install.merge_dictionaries(options, additional_options)


def run_tests(app_url, app_args, expected_output, service_name=SPARK_SERVICE_NAME, args=[]):
    task_id = submit_job(app_url=app_url, app_args=app_args, service_name=service_name, args=args)
    check_job_output(task_id, expected_output)


def submit_job(
        app_url,
        app_args,
        service_name=SPARK_SERVICE_NAME,
        args=[],
        spark_user=SPARK_USER,
        driver_role=SPARK_DRIVER_ROLE,
        verbose=True,
        principal=SPARK_SERVICE_ACCOUNT):

    conf_args = args.copy()

    conf_args += [
        '--conf spark.driver.memory=2g',
        '--conf spark.mesos.role={}'.format(driver_role)
    ]

    if sdk_utils.is_strict_mode():
        conf_args += [
            '--conf spark.mesos.driverEnv.SPARK_USER={}'.format(spark_user),
            '--conf spark.mesos.principal={}'.format(principal)
        ]

    submit_args = ' '.join([' '.join(conf_args), app_url, app_args])
    verbose_flag = "--verbose" if verbose else ""
    stdout = sdk_cmd.svc_cli(
        SPARK_PACKAGE_NAME,
        service_name,
        'run {} --submit-args="{}"'.format(verbose_flag, submit_args))
    result = re.search(r"Submission id: (\S+)", stdout)
    if not result:
        raise Exception("Unable to find submission ID in stdout:\n{}".format(stdout))
    return result.group(1)


def check_job_output(task_id, expected_output):
    LOGGER.info('Waiting for task id={} to complete'.format(task_id))
    shakedown.wait_for_task_completion(task_id, timeout_sec=JOB_WAIT_TIMEOUT_SEC)
    stdout = _task_log(task_id)

    if expected_output not in stdout:
        stderr = _task_log(task_id, "stderr")
        LOGGER.error("task stdout: {}".format(stdout))
        LOGGER.error("task stderr: {}".format(stderr))
        raise Exception("{} not found in stdout".format(expected_output))


def upload_file(file_path):
    spark_s3.upload_file(file_path)
    return spark_s3.http_url(os.path.basename(file_path))


def upload_dcos_test_jar():
    _check_tests_assembly()

    global DCOS_SPARK_TEST_JAR_URL
    if DCOS_SPARK_TEST_JAR_URL is None:
        DCOS_SPARK_TEST_JAR_URL = upload_file(DCOS_SPARK_TEST_JAR_PATH)
    else:
        LOGGER.info("Using provided DC/OS test jar URL: {}".format(DCOS_SPARK_TEST_JAR_URL))
    return DCOS_SPARK_TEST_JAR_URL


def upload_mesos_test_jar():
    _check_mesos_integration_tests_assembly()

    global MESOS_SPARK_TEST_JAR_URL
    if MESOS_SPARK_TEST_JAR_URL is None:
        MESOS_SPARK_TEST_JAR_URL = upload_file(MESOS_SPARK_TEST_JAR_PATH)
    else:
        LOGGER.info("Using provided Mesos test jar URL: {}".format(DCOS_SPARK_TEST_JAR_URL))
    return MESOS_SPARK_TEST_JAR_URL


def dcos_test_jar_url():
    _check_tests_assembly()

    if DCOS_SPARK_TEST_JAR_URL is None:
        return spark_s3.http_url(os.path.basename(DCOS_SPARK_TEST_JAR_PATH))
    return DCOS_SPARK_TEST_JAR_URL


def kill_driver(driver_id, service_name):
    return sdk_cmd.svc_cli(SPARK_PACKAGE_NAME, service_name, "kill {}".format(driver_id))


def _task_log(task_id, filename=None):
    return sdk_cmd.run_cli("task log --completed --lines=1000 {}".format(task_id) + \
          ("" if filename is None else " {}".format(filename)))


def spark_security_session():
    '''
    Spark strict mode setup is slightly different from dcos-commons, so can't use sdk_security::security_session.
    Differences:
    (1) the role is "*", (2) the driver itself is a framework and needs permission to execute tasks.
    '''
    user = SPARK_USER
    role = '*'
    service_account = SPARK_SERVICE_ACCOUNT
    secret = SPARK_SERVICE_ACCOUNT_SECRET

    def grant_driver_permission(service_account_name, service_name):
        app_id = "/{}".format(service_name.lstrip("/"))
        # double-encoded (why?)
        app_id = urllib.parse.quote(
            urllib.parse.quote(app_id, safe=''),
            safe=''
        )
        sdk_security._grant(service_account_name,
                            "dcos:mesos:master:task:app_id:{}".format(app_id),
                            description="Spark drivers may execute Mesos tasks",
                            action="create")

    def setup_security():
        LOGGER.info('Setting up strict-mode security for Spark')
        sdk_security.create_service_account(service_account_name=service_account, service_account_secret=secret)
        sdk_security.grant_permissions(
            linux_user=user,
            role_name=role,
            service_account_name=service_account
        )
        grant_driver_permission(service_account, SPARK_SERVICE_NAME)
        grant_driver_permission(service_account, FOLDERED_SPARK_SERVICE_NAME)
        LOGGER.info('Finished setting up strict-mode security for Spark')

    def cleanup_security():
        LOGGER.info('Cleaning up strict-mode security for Spark')
        sdk_security.revoke_permissions(
            linux_user=user,
            role_name=role,
            service_account_name=service_account
        )
        sdk_security.delete_service_account(service_account, secret)
        LOGGER.info('Finished cleaning up strict-mode security for Spark')

    try:
        if sdk_utils.is_strict_mode():
            setup_security()
        yield
    finally:
        if sdk_utils.is_strict_mode():
            cleanup_security()
