import shakedown

import json
import logging
import os
import re
import retrying
import urllib
import urllib.parse

import sdk_cmd
import sdk_install
import sdk_security
import sdk_utils

import spark_s3
import dcos_utils

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
SPARK_HISTORY_USER = SPARK_USER
SPARK_DOCKER_USER = os.getenv("SPARK_DOCKER_USER", None)
SPARK_DOCKER_IMAGE = os.getenv("DOCKER_DIST_IMAGE", "mesosphere/spark-dev")

SPARK_DRIVER_ROLE = os.getenv("SPARK_DRIVER_ROLE", "*")

JOB_WAIT_TIMEOUT_MINUTES = 15
JOB_WAIT_TIMEOUT_SECONDS = JOB_WAIT_TIMEOUT_MINUTES * 60

log = logging.getLogger(__name__)

SPARK_PACKAGE_NAME = os.getenv("SPARK_PACKAGE_NAME", "spark")
SPARK_EXAMPLES = "http://downloads.mesosphere.com/spark/assets/spark-examples_2.11-2.4.0.jar"

start_agent_cmd = "sudo systemctl start dcos-mesos-slave"
stop_agent_cmd = "sudo systemctl stop dcos-mesos-slave"
check_agent_cmd = "sudo systemctl is-active dcos-mesos-slave"


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
        additional_options=get_spark_options(service_name, additional_options),
        wait_for_deployment=False, # no deploy plan
        insert_strict_options=False) # lacks principal + secret_name options

    # wait for dispatcher to be reachable over HTTP
    sdk_cmd.service_request('GET', service_name, '', timeout_seconds=300)


# Note: zk may be customized in spark via 'spark.deploy.zookeeper.dir'
def teardown_spark(service_name=SPARK_SERVICE_NAME, zk='spark_mesos_dispatcher'):
    sdk_install.uninstall(
        SPARK_PACKAGE_NAME,
        service_name,
        role=re.escape('*'),
        service_account='spark-service-acct',
        zk=zk)

    if not sdk_utils.dcos_version_less_than('1.10'):
        # On 1.10+, sdk_uninstall doesn't run janitor. However Spark always needs it for ZK cleanup.
        sdk_install.retried_run_janitor(service_name, re.escape('*'), 'spark-service-acct', zk)


def get_spark_options(service_name, additional_options):
    options = {
        "service": {
            "user": SPARK_USER,
            "name": service_name
        }
    }

    if SPARK_DOCKER_USER is not None:
        options["service"]["docker_user"] = SPARK_DOCKER_USER

    if sdk_utils.is_strict_mode():
        # At the moment, we do this by hand because Spark doesn't quite line up with other services
        # with these options, and sdk_install assumes that we're following those conventions
        # Specifically, Spark's config.json lacks: service.principal, service.secret_name
        options["service"]["service_account"] = SPARK_SERVICE_ACCOUNT
        options["service"]["service_account_secret"] = SPARK_SERVICE_ACCOUNT_SECRET

    print(sdk_install.merge_dictionaries(options, additional_options))

    return sdk_install.merge_dictionaries(options, additional_options)


def get_dispatcher_task(service_name=SPARK_SERVICE_NAME):
    tasks_json = json.loads(sdk_cmd.run_cli("task --json"))

    tasks = []
    for task in tasks_json:
        if task["name"] == service_name:
            tasks.append(task)

    assert len(tasks) == 1, "More than one task with name {} is running".format(service_name)
    return tasks[0]


def run_tests(app_url, app_args, expected_output, service_name=SPARK_SERVICE_NAME, driver_role=SPARK_DRIVER_ROLE, args=[]):
    driver_id = submit_job(app_url=app_url, app_args=app_args, service_name=service_name, driver_role=driver_role, args=args)
    try:
        check_job_output(driver_id, expected_output)
    except TimeoutError:
        log.error("Timed out waiting for job output, will attempt to cleanup and kill driver: {}".format(driver_id))
        raise
    finally:
        kill_driver(driver_id, service_name=service_name)


def submit_job(
        app_url,
        app_args,
        service_name=SPARK_SERVICE_NAME,
        args=[],
        spark_user=None,
        driver_role=SPARK_DRIVER_ROLE,
        verbose=True,
        principal=SPARK_SERVICE_ACCOUNT,
        use_cli=True):

    conf_args = args.copy()

    if driver_role:
        conf_args += ['--conf', 'spark.mesos.role={}'.format(driver_role)]

    if SPARK_DOCKER_USER is not None:
        conf_args += ['--conf', 'spark.mesos.executor.docker.parameters=user={}'.format(SPARK_DOCKER_USER)]

    if not list(filter(lambda x: "spark.driver.memory=" in x, conf_args)):
        conf_args += ['--conf', 'spark.driver.memory=2g']

    if sdk_utils.is_strict_mode():
        conf_args += [
            '--conf spark.mesos.principal={}'.format(principal)
        ]

    if spark_user is not None:
        conf_args += [
            '--conf spark.mesos.driverEnv.SPARK_USER={}'.format(spark_user)
        ]

    if not list(filter(lambda x: "spark.mesos.containerizer=" in x, conf_args)):
        conf_args += ['--conf', 'spark.mesos.containerizer=mesos']

    submit_args = ' '.join([' '.join(conf_args), app_url, app_args])
    verbose_flag = "--verbose" if verbose else ""
    result = None

    if use_cli:
        stdout = sdk_cmd.svc_cli(
            SPARK_PACKAGE_NAME,
            service_name,
            'run {} --submit-args="{}"'.format(verbose_flag, submit_args))
        result = re.search(r"Submission id: (\S+)", stdout)
    else:
        docker_cmd = "sudo docker run --net=host -ti {} bin/spark-submit {}".format(SPARK_DOCKER_IMAGE, submit_args)
        ssh_opts = "--option UserKnownHostsFile=/dev/null --option StrictHostKeyChecking=no"

        log.info("Running Docker command on leader: {}".format(docker_cmd))
        _, stdout, stderr = sdk_cmd.run_raw_cli("node ssh --master-proxy --leader --user={} {} '{}'".format(sdk_cmd.LINUX_USER, ssh_opts, docker_cmd))
        result = re.search(r'"submissionId" : "(\S+)"', stdout)

    if not result:
        raise Exception("Unable to find submission ID in stdout:\n{}".format(stdout))
    return result.group(1)


def check_job_output(task_id, expected_output):
    log.info('Waiting for task id={} to complete'.format(task_id))
    shakedown.wait_for_task_completion(task_id, timeout_sec=JOB_WAIT_TIMEOUT_SECONDS)
    stdout = _task_log(task_id)

    if expected_output not in stdout:
        stderr = _task_log(task_id, "stderr")
        log.error("task stdout: {}".format(stdout))
        log.error("task stderr: {}".format(stderr))
        raise Exception("{} not found in stdout".format(expected_output))


# Reads the logs and matches each line for specified regular expressions.
# Returns a map of [regular expression] -> [list of matched line numbers]
def log_matches(task_id, filename, expressions):
    output = _task_log(task_id, filename)
    matched_lines = {}
    for exp in expressions:
        matched_lines[exp] = []
    for line_number, line in enumerate(output.splitlines()):
        for exp in expressions:
            if re.search(exp, line):
                matched_lines[exp].append(line_number)
    return matched_lines


@retrying.retry(
        wait_fixed=5000,
        stop_max_delay=600 * 1000,
        retry_on_result=lambda res: not res)
def wait_for_running_job_output(task_id, expected_line):
    stdout = sdk_cmd.run_cli("task log --lines=1000 {}".format(task_id))
    result = expected_line in stdout
    log.info('Checking for {} in STDOUT:\n{}\nResult: {}'.format(expected_line, stdout, result))
    return result


def upload_file(file_path):
    spark_s3.upload_file(file_path)
    return spark_s3.http_url(os.path.basename(file_path))


def upload_dcos_test_jar():
    _check_tests_assembly()

    global DCOS_SPARK_TEST_JAR_URL
    if DCOS_SPARK_TEST_JAR_URL is None:
        DCOS_SPARK_TEST_JAR_URL = upload_file(DCOS_SPARK_TEST_JAR_PATH)
    else:
        log.info("Using provided DC/OS test jar URL: {}".format(DCOS_SPARK_TEST_JAR_URL))
    return DCOS_SPARK_TEST_JAR_URL


def upload_mesos_test_jar():
    _check_mesos_integration_tests_assembly()

    global MESOS_SPARK_TEST_JAR_URL
    if MESOS_SPARK_TEST_JAR_URL is None:
        MESOS_SPARK_TEST_JAR_URL = upload_file(MESOS_SPARK_TEST_JAR_PATH)
    else:
        log.info("Using provided Mesos test jar URL: {}".format(DCOS_SPARK_TEST_JAR_URL))
    return MESOS_SPARK_TEST_JAR_URL


def dcos_test_jar_url():
    _check_tests_assembly()

    if DCOS_SPARK_TEST_JAR_URL is None:
        return spark_s3.http_url(os.path.basename(DCOS_SPARK_TEST_JAR_PATH))
    return DCOS_SPARK_TEST_JAR_URL


def kill_driver(driver_id, service_name=SPARK_SERVICE_NAME):
    return sdk_cmd.svc_cli(SPARK_PACKAGE_NAME, service_name, "kill {}".format(driver_id))


def _task_log(task_id, filename=None):
    return sdk_cmd.run_cli("task log --completed --lines=1000 {}".format(task_id) + \
          ("" if filename is None else " {}".format(filename)))


def grant_user_permissions(user, role="*", service_account=SPARK_SERVICE_ACCOUNT):
    log.info(f"Adding user permissions for Marathon. User: {user}")
    sdk_security.grant_permissions(
        linux_user=user,
        role_name="slave_public",
        service_account_name="dcos_marathon"
    )

    log.info(f"Adding user permissions for {service_account}. User: {user}, role: {role}")
    sdk_security.grant_permissions(
        linux_user=user,
        role_name=role,
        service_account_name=service_account
    )


def revoke_user_permissions(user, role="*", service_account=SPARK_SERVICE_ACCOUNT):
    log.info(f"Revoking user permissions for Marathon. User: {user}")
    sdk_security.grant_permissions(
        linux_user=user,
        role_name="slave_public",
        service_account_name="dcos_marathon"
    )

    log.info(f"Revoking user permissions for {service_account}. User: {user}, role: {role}")
    sdk_security.revoke_permissions(
        linux_user=user,
        role_name=role,
        service_account_name=service_account
    )


def _escape_service_name(service_name):
    app_id = "/{}".format(service_name.lstrip("/"))
    # double-encoded (why?)
    return urllib.parse.quote(
        urllib.parse.quote(app_id, safe=''),
        safe=''
    )


def grant_launch_task_permission(service_name, service_account_name=SPARK_SERVICE_ACCOUNT):
    log.info(f"Granting launch task permission to service account: {service_account_name}, service: {service_name}")
    app_id = _escape_service_name(service_name)
    sdk_security._grant(service_account_name,
                        "dcos:mesos:master:task:app_id:{}".format(app_id),
                        description="Spark drivers may execute Mesos tasks",
                        action="create")


def revoke_launch_task_permission(service_name, service_account_name=SPARK_SERVICE_ACCOUNT):
    log.info(f"Revoking launch task permission to service account: {service_account_name}, service: {service_name}")
    app_id = _escape_service_name(service_name)
    sdk_security._revoke(service_account_name,
                        "dcos:mesos:master:task:app_id:{}".format(app_id),
                        description="Spark drivers may execute Mesos tasks",
                        action="create")


def spark_security_session(users=[SPARK_USER], service_names=[SPARK_SERVICE_NAME, FOLDERED_SPARK_SERVICE_NAME]):
    '''
    Spark strict mode setup is slightly different from dcos-commons, so can't use sdk_security::security_session.
    Differences:
    (1) the role is "*", (2) the driver itself is a framework and needs permission to execute tasks.
    '''
    role = '*'
    service_account = SPARK_SERVICE_ACCOUNT
    secret = SPARK_SERVICE_ACCOUNT_SECRET

    def setup_security():
        log.info('Setting up strict-mode security for Spark')
        sdk_security.create_service_account(service_account_name=service_account, service_account_secret=secret)

        for user in users:
            grant_user_permissions(user, role, service_account)

        for service_name in service_names:
            grant_launch_task_permission(service_name)

        log.info('Finished setting up strict-mode security for Spark')

    def cleanup_security():
        log.info('Cleaning up strict-mode security for Spark')

        for user in users:
            revoke_user_permissions(user, role, service_account)

        # TODO: improve security setup/teardown to make it more fine-grained (allow different service names/accts/users)
        # tracking issue: https://jira.mesosphere.com/browse/DCOS-50933
        sdk_security.delete_service_account(service_account, secret)
        log.info('Finished cleaning up strict-mode security for Spark')

    try:
        if not sdk_utils.is_open_dcos():
            sdk_security.install_enterprise_cli()

        if sdk_utils.is_strict_mode():
            setup_security()
        yield
    finally:
        if sdk_utils.is_strict_mode():
            cleanup_security()


def restart_task_agent_and_verify_state(host_ip, task, expected_state):
    dcos_utils.agent_ssh(host_ip, stop_agent_cmd)
    _check_agent_status(host_ip, "inactive")
    dcos_utils.agent_ssh(host_ip, start_agent_cmd)
    _check_agent_status(host_ip, "active")
    _wait_for_task_status(task["id"], expected_state)


@retrying.retry(
    wait_fixed=5000,
    stop_max_delay=120 * 1000,
    retry_on_result=lambda res: not res)
def _check_agent_status(host_ip, expected_status):
    status = dcos_utils.agent_ssh(host_ip, check_agent_cmd)
    log.info(f"Checking status of agent at host {host_ip}, expected: {expected_status}, actual: {status}")
    return expected_status == status


@retrying.retry(
    wait_fixed=5000,
    stop_max_delay=120 * 1000,
    retry_on_result=lambda res: not res)
def _wait_for_task_status(task_id, expected_state):
    completed = expected_state != "TASK_RUNNING"
    task = shakedown.get_task(task_id, completed=completed)
    assert task is not None
    log.info(f"Checking task state for '{task_id}', expected: {expected_state}, actual: {task['state']}")
    return expected_state == task["state"]
