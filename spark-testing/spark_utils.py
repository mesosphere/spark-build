import dcos.config
import dcos.http
import dcos.package
import logging
import os
import re
import sdk_security
import shakedown
import subprocess
import urllib
import urllib.parse

import spark_s3

SPARK_SERVICE_ACCOUNT = os.getenv("SPARK_SERVICE_ACCOUNT", "spark-service-acct")
SPARK_SERVICE_ACCOUNT_SECRET = os.getenv("SPARK_SERVICE_ACCOUNT_SECRET", "spark-service-acct-secret")
SPARK_APP_NAME = os.getenv("SPARK_APP_NAME", "/spark")
SPARK_USER = os.getenv("SPARK_USER", "nobody")
SPARK_DRIVER_ROLE = os.getenv("SPARK_DRIVER_ROLE", "*")
FOLDERED_SPARK_APP_NAME = "/path/to" + SPARK_APP_NAME
JOB_WAIT_TIMEOUT_SEC = 1800


def _init_logging():
    logging.basicConfig(level=logging.INFO)
    logging.getLogger('dcos').setLevel(logging.WARNING)
    logging.getLogger('requests').setLevel(logging.WARNING)


_init_logging()
LOGGER = logging.getLogger(__name__)
HDFS_KRB5_CONF='W2xpYmRlZmF1bHRzXQpkZWZhdWx0X3JlYWxtID0gTE9DQUwKZG5zX2xvb2t1cF9yZWFsbSA9IHRydWUKZG5zX2xvb2t1cF9rZGMgPSB0cnVlCnVkcF9wcmVmZXJlbmNlX2xpbWl0ID0gMQoKW3JlYWxtc10KICBMT0NBTCA9IHsKICAgIGtkYyA9IGtkYy5tYXJhdGhvbi5tZXNvczoyNTAwCiAgfQoKW2RvbWFpbl9yZWFsbV0KICAuaGRmcy5kY29zID0gTE9DQUwKICBoZGZzLmRjb3MgPSBMT0NBTAo='
SPARK_PACKAGE_NAME=os.getenv('SPARK_PACKAGE_NAME', 'spark')
SPARK_EXAMPLES = "http://downloads.mesosphere.com/spark/assets/spark-examples_2.11-2.0.1.jar"
HISTORY_PACKAGE_NAME = os.getenv("HISTORY_PACKAGE_NAME", "spark-history")
HISTORY_SERVICE_NAME = os.getenv("HISTORY_SERVICE_NAME", "spark-history")


def hdfs_enabled():
    return os.environ.get("HDFS_ENABLED") != "false"


def kafka_enabled():
    return os.environ.get("KAFKA_ENABLED") != "false"


def is_strict():
    return os.environ.get('SECURITY') == 'strict'


def streaming_job_launched(job_name):
    return shakedown.get_service(job_name) is not None


def streaming_job_running(job_name):
    f = shakedown.get_service(job_name)
    if f is None:
        return False
    else:
        return len([x for x in f.dict()["tasks"] if x["state"] == "TASK_RUNNING"]) > 0


def require_spark(service_name=None, use_hdfs=False, use_history=False, marathon_group=None,
                  strict_mode=is_strict(), user="nobody"):
    LOGGER.info("Ensuring Spark is installed.")
    _require_package(
        SPARK_PACKAGE_NAME,
        service_name,
        _get_spark_options(use_hdfs, use_history, marathon_group, strict_mode, user))
    _wait_for_spark(service_name)
    _require_spark_cli()


# This should be in shakedown (DCOS_OSS-679)
def _require_package(pkg_name, service_name=None, options={}, package_version=None):
    pkg_manager = dcos.package.get_package_manager()
    installed_pkgs = dcos.package.installed_packages(
        pkg_manager,
        None,
        None,
        False)

    pkg = next((pkg for pkg in installed_pkgs if pkg['name'] == pkg_name), None)
    if (pkg is not None) and (service_name is None):
        LOGGER.info("Package {} is already installed.".format(pkg_name))
    elif (pkg is not None) and (service_name in pkg['apps']):
        LOGGER.info("Package {} with app_id={} is already installed.".format(
            pkg_name,
            service_name))
    else:
        LOGGER.info("Installing package {}".format(pkg_name))
        shakedown.install_package(
            pkg_name,
            options_json=options,
            wait_for_completion=True,
            package_version=package_version)


def _wait_for_spark(service_name=None):
    def pred():
        dcos_url = dcos.config.get_config_val("core.dcos_url")
        path = "/service{}".format(service_name) if service_name else "service{}".format(SPARK_APP_NAME)
        spark_url = urllib.parse.urljoin(dcos_url, path)
        status_code = dcos.http.get(spark_url).status_code
        return status_code == 200

    shakedown.wait_for(pred, timeout_seconds=300)


def _require_spark_cli():
    LOGGER.info("Ensuring Spark CLI is installed.")
    installed_subcommands = dcos.package.installed_subcommands()
    if any(sub.name == SPARK_PACKAGE_NAME for sub in installed_subcommands):
        LOGGER.info("Spark CLI already installed.")
    else:
        LOGGER.info("Installing Spark CLI.")
        shakedown.run_dcos_command('package install --cli {} --yes'.format(
            SPARK_PACKAGE_NAME))


def is_service_ready(service_name, expected_tasks):
    running_tasks = [t for t in shakedown.get_service_tasks(service_name) \
                     if t['state'] == 'TASK_RUNNING']
    LOGGER.info("Waiting for {n} tasks got {m} for service {s}".format(n=expected_tasks,
                                                                       m=len(running_tasks),
                                                                       s=service_name))
    return len(running_tasks) >= expected_tasks


def no_spark_jobs(service_name):
    driver_ips = shakedown.get_service_ips(service_name)
    LOGGER.info("Waiting for drivers to finish or be killed, still seeing {}".format(len(driver_ips)))
    return len(driver_ips) == 0


def _get_spark_options(use_hdfs, use_history, marathon_group, strict_mode, user):
    options = {}
    options["service"] = options.get("service", {})
    options["service"]["user"] = user
    
    if marathon_group is not None:
        options["service"]["name"] = marathon_group

    if use_hdfs:
        options["hdfs"] = options.get("hdfs", {})
        options["hdfs"]["config-url"] = "http://api.hdfs.marathon.l4lb.thisdcos.directory/v1/endpoints"
        options["security"] = options.get("security", {})
        options["security"]["kerberos"] = options["security"].get("kerberos", {})
        options["security"]["kerberos"]["enabled"] = True
        options["security"]["kerberos"]["realm"] = "LOCAL"
        options["security"]["kerberos"]["kdc"] = options["security"]["kerberos"].get("kdc", {})
        options["security"]["kerberos"]["kdc"]["hostname"] = "kdc.marathon.autoip.dcos.thisdcos.directory"
        options["security"]["kerberos"]["kdc"]["port"] = 2500

    if use_history:
        dcos_url = dcos.config.get_config_val("core.dcos_url")
        history_url = urllib.parse.urljoin(dcos_url, "/service/{}".format(HISTORY_SERVICE_NAME))
        options["service"] = options.get("service", {})
        options["service"]["spark-history-server-url"] = history_url

    if strict_mode:
        options["service"] = options.get("service", {})
        options["service"]["service_account"] = SPARK_SERVICE_ACCOUNT
        options["service"]["service_account_secret"] = SPARK_SERVICE_ACCOUNT_SECRET

    return options


def run_tests(app_url, app_args, expected_output, app_name=SPARK_APP_NAME, args=[]):
    task_id = submit_job(app_url=app_url,
                         app_args=app_args,
                         app_name=app_name,
                         args=args)
    check_job_output(task_id, expected_output)


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
    LOGGER.info("Uploading {} to s3://{}/{}".format(
        file_path,
        os.environ['S3_BUCKET'],
        os.environ['S3_PREFIX']))

    spark_s3.upload_file(file_path)

    basename = os.path.basename(file_path)
    return spark_s3.http_url(basename)


def submit_job(app_url, app_args, app_name=SPARK_APP_NAME, args=[], spark_user=SPARK_USER,
               driver_role=SPARK_DRIVER_ROLE, verbose=True):
    if is_strict():
        args += ["--conf", 'spark.mesos.driverEnv.SPARK_USER={}'.format(spark_user)]
        args += ["--conf", 'spark.mesos.principal={}'.format(SPARK_SERVICE_ACCOUNT)]
    args_str = ' '.join(args + ["--conf", "spark.driver.memory=2g"] +
                        ["--conf", "spark.mesos.role={}".format(driver_role)])
    submit_args = ' '.join([args_str, app_url, app_args])
    verbose_flag = "--verbose" if verbose else ""
    cmd = 'dcos {pkg_name} --name={app_name} run {verbose_flag} --submit-args="{args}"'.format(
        pkg_name=SPARK_PACKAGE_NAME,
        app_name=app_name,
        verbose_flag=verbose_flag,
        args=submit_args)

    LOGGER.info("Running {}".format(cmd))
    stdout = subprocess.check_output(cmd, shell=True).decode('utf-8')

    LOGGER.info("stdout: {}".format(stdout))

    regex = r"Submission id: (\S+)"
    match = re.search(regex, stdout)
    return match.group(1)


def wait_for_executors_running(framework_name, num_executors, wait_time=600):
    LOGGER.info("Waiting for executor task to be RUNNING...")
    shakedown.wait_for(lambda: is_service_ready(framework_name, num_executors),
                       ignore_exceptions=False,
                       timeout_seconds=wait_time)


def kill_driver(driver_id, app_name):
    LOGGER.info("Killing {}".format(driver_id))
    cmd = "dcos {spark_package} --name={app_name} kill {driver_id}"\
        .format(spark_package=SPARK_PACKAGE_NAME, app_name=app_name, driver_id=driver_id)
    out = subprocess.check_output(cmd, shell=True).decode("utf-8")
    return out


def _task_log(task_id, filename=None):
    cmd = "dcos task log --completed --lines=1000 {}".format(task_id) + \
          ("" if filename is None else " {}".format(filename))

    LOGGER.info("Running {}".format(cmd))
    stdout = subprocess.check_output(cmd, shell=True).decode('utf-8')
    return stdout


def is_framework_completed(fw_name):
    # The framework is not Active or Inactive
    return shakedown.get_service(fw_name, True) is None


def _run_janitor():
    janitor_cmd = (
        'docker run mesosphere/janitor /janitor.py '
        '-r spark-role -p spark-principal -z spark_mesos_dispatcher --auth_token={auth}')
    shakedown.run_command_on_master(janitor_cmd.format(
        auth=shakedown.dcos_acs_token()))


def teardown_spark():
    shakedown.uninstall_package_and_wait(SPARK_PACKAGE_NAME)
    _run_janitor()


def _scala_test_jar_url():
    return spark_s3.http_url(os.path.basename(os.environ["SCALA_TEST_JAR_PATH"]))


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

    def grant_driver_permission(service_account_name, app_id):
        dcosurl, headers = sdk_security.get_dcos_credentials()
        # double-encoded (why?)
        app_id_encoded = urllib.parse.quote(
            urllib.parse.quote(app_id, safe=''),
            safe=''
        )
        sdk_security.grant(
            dcosurl,
            headers,
            service_account_name,
            "dcos:mesos:master:task:app_id:{}".format(app_id_encoded),
            "Spark drivers may execute Mesos tasks"
        )

    def setup_security():
        LOGGER.info('Setting up strict-mode security for Spark')
        sdk_security.create_service_account(service_account_name=service_account, service_account_secret=secret)
        sdk_security.grant_permissions(
            linux_user=user,
            role_name=role,
            service_account_name=service_account
        )
        grant_driver_permission(service_account, SPARK_APP_NAME)
        grant_driver_permission(service_account, FOLDERED_SPARK_APP_NAME)
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
        if is_strict():
            setup_security()
        yield
    finally:
        if is_strict():
            cleanup_security()
