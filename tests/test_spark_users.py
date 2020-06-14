import logging

import pytest

import sdk_cmd
import sdk_tasks
import sdk_utils
import shakedown
import spark_utils as utils
import docker_utils

log = logging.getLogger(__name__)

SERVICE_NAME = "test-users"
DISPATCHER_ZK = "spark_mesos_dispatcher" + SERVICE_NAME

LIST_USERS_CMD = "ps aux | grep java | cut -d' ' -f1 | uniq | tail -1"


@pytest.fixture(scope='module')
def configure_user_permissions(configure_security_spark):
    """Tests in this module require permissions for 'root' user, we can't use `spark_utils.spark_security_session` here
       because it drops service account completely during teardown. To lower down amount of boilerplate code in tests
       'configure_security_spark' fixture is defined with 'session' scope thus dropped service account won't be
       recreated in tests executed after the current one.
    """
    try:
        if sdk_utils.is_strict_mode():
            utils.grant_launch_task_permission(SERVICE_NAME)
            utils.grant_user_permissions("root")
        yield
    finally:
        if sdk_utils.is_strict_mode():
            utils.revoke_launch_task_permission(SERVICE_NAME)
            utils.revoke_user_permissions("root")


@pytest.fixture()
def setup_spark(configure_user_permissions, configure_universe, use_ucr_containerizer, user):
    options = {
        "service": {
            "name": SERVICE_NAME,
            "user": user,
            "UCR_containerizer": use_ucr_containerizer
        }
    }

    try:
        utils.upload_dcos_test_jar()
        utils.require_spark(service_name=SERVICE_NAME, additional_options=options, zk=DISPATCHER_ZK)
        yield
    finally:
        utils.teardown_spark(service_name=SERVICE_NAME, zk=DISPATCHER_ZK)


@pytest.mark.sanity
@pytest.mark.parametrize('user,use_ucr_containerizer,use_ucr_for_spark_submit', [
    ("nobody", True, True),
    ("nobody", True, False),
    ("nobody", False, True),
    ("nobody", False, False),
    ("root", True, True),
    ("root", True, False),
    ("root", False, True),
    ("root", False, False)
])
def test_user_propagation(setup_spark, user, use_ucr_containerizer, use_ucr_for_spark_submit):
    dispatcher_task = utils.get_dispatcher_task(service_name=SERVICE_NAME)
    _check_task_user(dispatcher_task, user, use_ucr_containerizer)

    extra_args = []
    if not use_ucr_for_spark_submit:
        extra_args = ["--conf spark.mesos.containerizer=docker"]
        if user == "nobody":
            extra_args = extra_args + ["--conf spark.mesos.executor.docker.parameters=user=99"]

    _submit_job_and_verify_users(user, use_ucr_for_spark_submit, extra_args=extra_args)


@pytest.mark.sanity
@pytest.mark.parametrize('user,user_override,use_ucr_containerizer,use_ucr_for_spark_submit', [
    ("root", "nobody", True, True),
    ("root", "nobody", True, False),
    ("root", "nobody", False, True),
    ("root", "nobody", False, False)
])
def test_user_overrides(setup_spark,  user, user_override, use_ucr_containerizer, use_ucr_for_spark_submit):
    """This test uses overrides for 'root' user only to lower down total amount of tests
       while preserving containerizers combinations. User override functionality is independent
       from any specific username, thus submitting jobs to Dispatcher running as 'root' with
       jobs running as 'nobody' is sufficient to test it.
    """
    dispatcher_task = utils.get_dispatcher_task(service_name=SERVICE_NAME)
    _check_task_user(dispatcher_task, user, use_ucr_containerizer)

    extra_args = [f"--conf spark.mesos.driverEnv.SPARK_USER={user_override}"]
    if not use_ucr_for_spark_submit:
        extra_args = extra_args + [
            "--conf spark.mesos.containerizer=docker",
            "--conf spark.mesos.executor.docker.parameters=user=99"
        ]

    _submit_job_and_verify_users(user_override, use_ucr_for_spark_submit, extra_args=extra_args)


def _submit_job_and_verify_users(user, use_ucr_for_spark_submit, extra_args=[]):
    app_name = "MockTaskRunner"

    submit_args = ["--conf spark.cores.max=1",
                   "--class {}".format(app_name)] + extra_args

    driver_task_id = utils.submit_job(service_name=SERVICE_NAME,
                                      app_url=utils.dcos_test_jar_url(),
                                      app_args="1 300",
                                      args=submit_args)
    try:
        sdk_tasks.check_running(app_name, 1, timeout_seconds=300)
        driver_task = shakedown.get_task(driver_task_id, completed=False)
        executor_tasks = shakedown.get_service_tasks(app_name)

        for task in [driver_task] + executor_tasks:
            log.info(f"Checking task '{task['id']}'")
            _check_task_user(task, user, use_ucr_for_spark_submit)

    finally:
        log.info(f"Cleaning up. Attempting to kill driver: {driver_task_id}")
        utils.kill_driver(driver_task_id, service_name=SERVICE_NAME)


def _check_task_user(task, user, use_ucr):
    if use_ucr:
        _check_mesos_task_user(task, user)
    else:
        _check_docker_task_user(task, user)


def _check_mesos_task_user(task, user):
    if "user" in task:
        assert user == task["user"], f"Mesos Task['user'] = {task['user']} doesn't match expected user '{user}'"
    else:
        log.warning(f"Mesos task doesn't have a user specified, skipping the TaskInfo check")

    users = sdk_cmd.run_cli(f"task exec {task['id']} {LIST_USERS_CMD}")
    assert user == users.rstrip(), f"Expected '{user}' but 'ps aux' returned unexpected user(s): {users}"


def _check_docker_task_user(task, user):
    container_user = docker_utils.docker_inspect(task, format_options="--format='{{.Config.User}}'")
    log.info(f"Docker container user: {container_user}")
    assert container_user.rstrip() in ["99", user], \
        f"[Docker] Expected either '99' or '{user}' in container configuration but found: {container_user.rstrip()}"

    users = docker_utils.docker_exec(task, LIST_USERS_CMD)
    log.info(f"Docker process user: {users}")
    assert user == users.rstrip(), f"[Docker] Expected '{user}' but 'ps aux' returned unexpected user(s): {users}"
