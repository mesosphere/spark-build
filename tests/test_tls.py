import logging
import pytest

import dcos_utils
import spark_utils as utils

log = logging.getLogger(__name__)
secret_path = "/spark/keystore"

@pytest.fixture(scope="module", autouse=True)
def setup_spark(configure_security_spark, configure_universe):
    secret_file_name = "server.jks"
    dcos_utils.delete_secret(secret_path)
    dcos_utils.create_secret(secret_path, secret_file_name, True)
    service_options = {
        "service": {
            "tls": {
                "enabled": True,
                "protocol": "TLSv1.2",
                "keystore": "{}".format(secret_path),
                "keypassword": "deleteme",
                "keystore_password": "deleteme"
            }
        }
    }
    try:
        utils.upload_dcos_test_jar()
        utils.require_spark(additional_options=service_options)
        yield
    finally:
        dcos_utils.delete_secret(secret_path)
        utils.teardown_spark()


@pytest.mark.sanity
def test_driver_over_tls():
    utils.run_tests(
        app_url=utils.SPARK_EXAMPLES,
        app_args="100",
        expected_output="Pi is roughly 3",
        args=["--conf spark.ssl.enabled=true",
              "--conf spark.ssl.protocol=TLSv1.2",
              "--keystore-secret-path={}".format(secret_path),
              "--keystore-password=deleteme",
              "--private-key-password=deleteme",
              "--class org.apache.spark.examples.SparkPi"])
