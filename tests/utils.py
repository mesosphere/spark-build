import dcos.config
import dcos.http
import dcos.package

import json
import logging
import os
import re
import requests
import s3
import shakedown
import subprocess
import urllib


def _init_logging():
    logging.basicConfig(level=logging.INFO)
    logging.getLogger('dcos').setLevel(logging.WARNING)
    logging.getLogger('requests').setLevel(logging.WARNING)


_init_logging()
LOGGER = logging.getLogger(__name__)
DEFAULT_HDFS_TASK_COUNT=10
HDFS_PACKAGE_NAME='hdfs'
HDFS_SERVICE_NAME='hdfs'
SPARK_PACKAGE_NAME='spark'


def hdfs_enabled():
    return os.environ.get("HDFS_ENABLED") != "false"


def is_strict():
    return os.environ.get('SECURITY') == 'strict'


def require_hdfs():
    LOGGER.info("Ensuring HDFS is installed.")

    _require_package(
        HDFS_PACKAGE_NAME,
        _get_hdfs_options(),
        # Remove after HDFS-483 is fixed
        package_version='2.0.1-2.6.0-cdh5.11.0'
    )
    _wait_for_hdfs()


def require_spark(options={}, service_name=None):
    LOGGER.info("Ensuring Spark is installed.")

    _require_package(SPARK_PACKAGE_NAME, service_name, _get_spark_options(options))
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
        path = "/service{}".format(service_name) if service_name else "service/spark"
        spark_url = urllib.parse.urljoin(dcos_url, path)
        status_code = dcos.http.get(spark_url).status_code
        return status_code == 200

    shakedown.wait_for(pred)


def _require_spark_cli():
    LOGGER.info("Ensuring Spark CLI is installed.")
    installed_subcommands = dcos.package.installed_subcommands()
    if any(sub.name == SPARK_PACKAGE_NAME for sub in installed_subcommands):
        LOGGER.info("Spark CLI already installed.")
    else:
        LOGGER.info("Installing Spark CLI.")
        shakedown.run_dcos_command('package install --cli {}'.format(
            SPARK_PACKAGE_NAME))


def _get_hdfs_options():
    if is_strict():
        options = {'service': {'principal': 'service-acct', 'secret_name': 'secret'}}
    else:
        options = {"service": {}}

    options["service"]["beta-optin"] = True
    return options


def _wait_for_hdfs():
    shakedown.wait_for(_is_hdfs_ready, ignore_exceptions=False, timeout_seconds=25 * 60)


def _is_hdfs_ready(expected_tasks = DEFAULT_HDFS_TASK_COUNT):
    return is_service_ready(HDFS_SERVICE_NAME, expected_tasks)


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


def _get_spark_options(options = None):
    if options is None:
        options = {}

    if hdfs_enabled():
        options["hdfs"] = options.get("hdfs", {})
        options["hdfs"]["config-url"] = "http://api.hdfs.marathon.l4lb.thisdcos.directory/v1/endpoints"

    if is_strict():
        options["service"] = options.get("service", {})
        options["service"]["principal"] = "service-acct"

        options["security"] = options.get("security", {})
        options["security"]["mesos"] = options["security"].get("mesos", {})
        options["security"]["mesos"]["authentication"] = options["security"]["mesos"].get("authentication", {})
        options["security"]["mesos"]["authentication"]["secret_name"] = "secret"


    return options


def run_tests(app_url, app_args, expected_output, app_name, args=[]):
    task_id = submit_job(app_url=app_url,
                         app_args=app_args,
                         app_name=app_name,
                         args=args)
    check_job_output(task_id, expected_output)


def check_job_output(task_id, expected_output):
    LOGGER.info('Waiting for task id={} to complete'.format(task_id))
    shakedown.wait_for_task_completion(task_id)
    stdout = _task_log(task_id)

    if expected_output not in stdout:
        stderr = _task_log(task_id, "stderr")
        LOGGER.error("task stdout: {}".format(stdout))
        LOGGER.error("task stderr: {}".format(stderr))
        raise Exception("{} not found in stdout".format(expected_output))


class SecretHandler():
    def __init__(self, path, value):
        self.payload = json.dumps({"value": value})
        self.api_url = urllib.parse.urljoin(dcos.config.get_config_val("core.dcos_url"),
                                            "secrets/v1/secret/default/{}".format(path))
        self.token = dcos.config.get_config_val("core.dcos_acs_token")
        self.headers = {"Content-Type": "application/json", "Authorization": "token={}".format(self.token)}

    def create_secret(self):
        return requests.put(self.api_url, data=self.payload, headers=self.headers, verify=False)

    def delete_secret(self):
        return requests.delete(self.api_url, headers=self.headers, verify=False)


def upload_file(file_path):
    LOGGER.info("Uploading {} to s3://{}/{}".format(
        file_path,
        os.environ['S3_BUCKET'],
        os.environ['S3_PREFIX']))

    s3.upload_file(file_path)

    basename = os.path.basename(file_path)
    return s3.http_url(basename)


def submit_job(app_url, app_args, app_name="/spark", args=[]):
    if is_strict():
        args += ["--conf", 'spark.mesos.driverEnv.MESOS_MODULES=file:///opt/mesosphere/etc/mesos-scheduler-modules/dcos_authenticatee_module.json']
        args += ["--conf", 'spark.mesos.driverEnv.MESOS_AUTHENTICATEE=com_mesosphere_dcos_ClassicRPCAuthenticatee']
        args += ["--conf", 'spark.mesos.principal=service-acct']
    args_str = ' '.join(args + ["--conf", "spark.driver.memory=2g"])
    submit_args = ' '.join([args_str, app_url, app_args])
    cmd = 'dcos spark --name={app_name}  run --verbose --submit-args="{args}"'.format(app_name=app_name, args=submit_args)

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
    cmd = "dcos spark --name={app_name} kill {driver_id}".format(app_name=app_name, driver_id=driver_id)
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
