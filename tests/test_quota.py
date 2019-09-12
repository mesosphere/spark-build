import logging

import pytest

import dcos_utils
import sdk_marathon
import sdk_tasks
import sdk_utils
import spark_utils as utils

log = logging.getLogger(__name__)
DISPATCHER_ZK = "spark_mesos_dispatcher__dev__spark"
ROLES = ["spark_role", "custom_role", "dev"]
SERVICE_NAME = "/dev/spark"


@pytest.fixture(scope='module')
def configure_role_permissions(configure_security_spark):
    try:
        if sdk_utils.is_strict_mode():
            for role in ROLES:
                utils.grant_user_permissions("nobody", role, utils.SPARK_SERVICE_ACCOUNT)

            utils.grant_launch_task_permission("/dev/spark")
        yield
    finally:
        if sdk_utils.is_strict_mode():
            for role in ROLES:
                utils.revoke_user_permissions("nobody", role, utils.SPARK_SERVICE_ACCOUNT)

            utils.revoke_launch_task_permission("/dev/spark")


@pytest.fixture()
def create_group(group, enforce_group):
    log.info("Creating group '{}' with enforceGroup='{}'".format(group, enforce_group))

    try:
        sdk_marathon.delete_group(group)
        sdk_marathon.create_group(group, options={"enforceRole": enforce_group})
        yield
    finally:
        sdk_marathon.delete_group(group)


@pytest.fixture()
def setup_spark(configure_universe, configure_role_permissions, role, enforce_role):
    log.info("Installing Spark: service_name='{}', role='{}', enforce_role='{}'".format(SERVICE_NAME, role, enforce_role))
    options = {
        "service": {
            "name": SERVICE_NAME,
            "role": role,
            "enforce_role": enforce_role
        }
    }

    try:
        utils.upload_dcos_test_jar()
        utils.require_spark(service_name=SERVICE_NAME, additional_options=options, zk=DISPATCHER_ZK)
        yield
    finally:
        utils.teardown_spark(service_name=SERVICE_NAME, zk=DISPATCHER_ZK)


@pytest.mark.skipif(sdk_utils.dcos_version_less_than('1.14'),
                    reason="Group role enforcement is available only in DCOS v1.14 and higher")
@pytest.mark.sanity
@pytest.mark.parametrize('group,enforce_group,role,enforce_role', [
    ("dev", True, "spark_role", False),
    ("dev", True, "spark_role", True),
    ("dev", True, "dev", False),
    ("dev", True, "dev", True)
])
def test_marathon_group_enforced(create_group, setup_spark, group, enforce_group, role, enforce_role):
    log.info("Running test: group='{}', enforce_group='{}', service_name='{}', role='{}', enforce_role='{}'"
             .format(group, enforce_group, SERVICE_NAME, role, enforce_role))

    dispatcher_framework = dcos_utils.get_framework_json(SERVICE_NAME, completed=False)
    log.info("Dispatcher framework:\n{}".format(dispatcher_framework))
    assert group == dispatcher_framework["role"]

    # verifying submissions without role
    _submit_job_and_verify_role(expected_role=group)
    # verifying submissions with role equal to group role
    _submit_job_and_verify_role(expected_role=group, driver_role=group)

    # submissions with role different from group should be rejected
    _verify_submission_rejected(driver_role="{}/spark".format(group))


@pytest.mark.sanity
@pytest.mark.parametrize('role,enforce_role', [
    ("spark_role", False),
    ("custom_role", False)
])
def test_dispatcher_role_propagated(setup_spark, role, enforce_role):
    dispatcher_framework = dcos_utils.get_framework_json(SERVICE_NAME, completed=False)
    log.info("Dispatcher framework:\n{}".format(dispatcher_framework))
    assert role == dispatcher_framework["role"]

    _submit_job_and_verify_role(role)


@pytest.mark.sanity
@pytest.mark.parametrize('role,enforce_role', [
    ("spark_role", True)
])
def test_dispatcher_role_enforced(setup_spark, role, enforce_role):
    dispatcher_framework = dcos_utils.get_framework_json(SERVICE_NAME, completed=False)
    log.info("Dispatcher framework:\n{}".format(dispatcher_framework))
    assert role == dispatcher_framework["role"]

    _submit_job_and_verify_role(role)
    _verify_submission_rejected(driver_role="custom_role")


def _submit_job_and_verify_role(expected_role, driver_role=None):
    app_name = "MockTaskRunner"
    submit_args = ["--conf spark.cores.max=1", "--class {}".format(app_name)]

    submission_id = utils.submit_job(service_name=SERVICE_NAME,
                                     app_url=utils.dcos_test_jar_url(),
                                     app_args="1 300",
                                     driver_role=driver_role,
                                     args=submit_args)

    try:
        sdk_tasks.check_running(app_name, 1, timeout_seconds=300)
        driver_framework = dcos_utils.get_framework_json(app_name, completed=False)
        log.info("Driver framework:\n{}".format(driver_framework))
        assert expected_role == driver_framework["role"], \
            "Expected role '{}' but got '{}'".format(expected_role, driver_framework["role"])

    finally:
        log.info(f"Cleaning up. Attempting to kill driver: {submission_id}")
        utils.kill_driver(submission_id, service_name=SERVICE_NAME)


def _verify_submission_rejected(driver_role=None):
    app_name = "MockTaskRunner"
    submit_args = ["--conf spark.cores.max=1", "--class {}".format(app_name)]

    submission_id = None
    error = None
    try:
        submission_id = utils.submit_job(service_name=SERVICE_NAME,
                                         app_url=utils.dcos_test_jar_url(),
                                         driver_role=driver_role,
                                         app_args="1 300",
                                         args=submit_args)
    except Exception as err:
        error = err
    finally:
        if submission_id:
            utils.kill_driver(submission_id, service_name=SERVICE_NAME)

    assert error is not None
