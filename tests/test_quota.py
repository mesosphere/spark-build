import logging

import pytest

import dcos_utils
import sdk_marathon
import sdk_tasks
import sdk_utils
import spark_utils as utils

log = logging.getLogger(__name__)
DISPATCHER_ZK = "spark_mesos_dispatcher__dev__spark"


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
def setup_spark(configure_universe, service_name, role, enforce_role):
    log.info("Installing Spark: service_name='{}', role='{}', enforce_role='{}'".format(service_name, role, enforce_role))
    options = {
        "service": {
            "name": service_name,
            "role": role,
            "enforce_role": enforce_role
        }
    }

    try:
        utils.upload_dcos_test_jar()
        utils.require_spark(service_name=service_name, additional_options=options, zk=DISPATCHER_ZK)
        yield
    finally:
        utils.teardown_spark(service_name=service_name, zk=DISPATCHER_ZK)


@pytest.mark.skipif(sdk_utils.dcos_version_less_than('1.14'),
                    reason="Group role enforcement is available only in DCOS v1.14 and higher")
@pytest.mark.sanity
@pytest.mark.parametrize('group,enforce_group,service_name,role,enforce_role', [
    ("dev", True, "/dev/spark", "spark_role", False),
    ("dev", True, "/dev/spark", "spark_role", True),
    ("dev", True, "/dev/spark", "dev", False),
    ("dev", True, "/dev/spark", "dev", True)
])
def test_marathon_group_enforced(create_group, setup_spark, group, enforce_group, service_name, role, enforce_role):
    log.info("Running test: group='{}', enforce_group='{}', service_name='{}', role='{}', enforce_role='{}'"
             .format(group, enforce_group, service_name, role, enforce_role))

    dispatcher_framework = dcos_utils.get_framework_json(service_name, completed=False)
    assert dispatcher_framework["role"] == group

    # verifying submissions without role
    _submit_job_and_verify_role(service_name, expected_role=group)
    # verifying submissions with role equal to group role
    _submit_job_and_verify_role(service_name, expected_role=group, driver_role=group)

    # submissions with role different from group should be rejected
    _verify_submission_rejected(service_name, driver_role="{}/spark".format(group))


@pytest.mark.sanity
@pytest.mark.parametrize('service_name,role,enforce_role', [
    ("/dev/spark", "spark_role", False),
    ("/dev/spark", "custom_role", False)
])
def test_dispatcher_role_propagated(setup_spark, service_name, role, enforce_role):
    _submit_job_and_verify_role(service_name, role)


@pytest.mark.sanity
@pytest.mark.parametrize('service_name,role,enforce_role', [
    ("/dev/spark", "spark_role", True)
])
def test_dispatcher_role_enforced(setup_spark, service_name, role, enforce_role):
    _submit_job_and_verify_role(service_name, role)
    _verify_submission_rejected(service_name, driver_role="custom_role")


def _submit_job_and_verify_role(service_name, expected_role, driver_role=None):
    app_name = "MockTaskRunner"
    submit_args = ["--conf spark.cores.max=1", "--class {}".format(app_name)]

    submission_id = utils.submit_job(service_name=service_name,
                                     app_url=utils.dcos_test_jar_url(),
                                     app_args="1 300",
                                     driver_role=driver_role,
                                     args=submit_args)

    try:
        sdk_tasks.check_running(app_name, 1, timeout_seconds=300)
        driver_framework = dcos_utils.get_framework_json(app_name, completed=False)
        assert driver_framework["role"] == expected_role, \
            "Expected role '{}' but got '{}'".format(expected_role, driver_framework["role"])

    finally:
        log.info(f"Cleaning up. Attempting to kill driver: {submission_id}")
        utils.kill_driver(submission_id, service_name=service_name)


def _verify_submission_rejected(service_name, driver_role=None):
    app_name = "MockTaskRunner"
    submit_args = ["--conf spark.cores.max=1", "--class {}".format(app_name)]

    submission_id = None
    error = None
    try:
        submission_id = utils.submit_job(service_name=service_name,
                                         app_url=utils.dcos_test_jar_url(),
                                         driver_role=driver_role,
                                         app_args="1 300",
                                         args=submit_args)
    except Exception as err:
        error = err
    finally:
        if submission_id:
            utils.kill_driver(submission_id, service_name=service_name)

    assert error is not None
