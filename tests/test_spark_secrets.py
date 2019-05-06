import logging
import pytest
import os

import sdk_cmd
import sdk_utils

import dcos_utils
import spark_utils as utils

log = logging.getLogger(__name__)
auth_token = sdk_cmd.run_cli('config show core.dcos_acs_token', print_output=False).strip()

@pytest.fixture(scope='module', autouse=True)
def setup_spark(configure_security_spark, configure_universe):
    try:
        utils.upload_dcos_test_jar()
        utils.require_spark()
        yield
    finally:
        utils.teardown_spark()


@sdk_utils.dcos_ee_only
@pytest.mark.sanity
def test_env_based_ref_secret():
    secret_path = "/spark/secret-name"
    secret_value = "secret-value"
    dcos_utils.delete_secret(secret_path)
    dcos_utils.create_secret(secret_path, secret_value, False)
    try:
        utils.run_tests(
            app_url=utils.dcos_test_jar_url(),
            app_args=auth_token,
            expected_output=secret_value,
            args=["--conf=spark.mesos.driver.secret.names={}".format(secret_path),
                  "--conf=spark.mesos.driver.secret.envkeys=SECRET_ENV_KEY",
                  "--class SecretConfs"])
    finally:
        dcos_utils.delete_secret(secret_path)


@sdk_utils.dcos_ee_only
@pytest.mark.sanity
def test_value_secret():
    secret_value = "secret-value"
    utils.run_tests(
        app_url=utils.dcos_test_jar_url(),
        app_args=auth_token,
        expected_output=secret_value,
        args=["--conf=spark.mesos.driver.secret.values={}".format(secret_value),
              "--conf=spark.mesos.driver.secret.envkeys=SECRET_ENV_KEY",
              "--class SecretConfs"])


@sdk_utils.dcos_ee_only
@pytest.mark.sanity
def test_file_based_ref_secret():
    secret_path = "/spark/secret-name"
    secret_file_name = "secret.file"
    secret_value = "secret-value"
    with open(secret_file_name, 'w') as secret_file:
        secret_file.write(secret_value)
    dcos_utils.delete_secret(secret_path)
    dcos_utils.create_secret(secret_path, secret_file_name, True)
    try:
        utils.run_tests(
            app_url=utils.dcos_test_jar_url(),
            app_args=auth_token,
            expected_output=secret_value,
            args=["--conf=spark.mesos.driver.secret.names={}".format(secret_path),
                  "--conf=spark.mesos.driver.secret.filenames={}".format(secret_file_name),
                  "--class SecretConfs"])
    finally:
        dcos_utils.delete_secret(secret_path)
        if os.path.exists(secret_file_name):
            os.remove(secret_file_name)
