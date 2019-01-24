import logging
import os

import pytest
import sdk_auth
import sdk_install
import sdk_utils
import shakedown
import spark_utils as utils

log = logging.getLogger(__name__)

from tests.fixtures.hdfs import hdfs_cmd, HDFS_KRB5_CONF, HDFS_SERVICE_NAME, HDFS_CLIENT_ID, KEYTAB_SECRET_PATH, GENERIC_HDFS_USER_PRINCIPAL
from tests.fixtures.hdfs import SPARK_SUBMIT_HDFS_KERBEROS_ARGS

HISTORY_PACKAGE_NAME = os.getenv("HISTORY_PACKAGE_NAME", "spark-history")
HISTORY_SERVICE_NAME = os.getenv("HISTORY_SERVICE_NAME", "spark-history")

HDFS_HISTORY_DIR = '/history'
SPARK_HISTORY_USER = "nobody"


SPARK_HISTORY_SERVICE_OPTIONS = {
    "service": {
        "name": HISTORY_SERVICE_NAME,
        "user": SPARK_HISTORY_USER,
        "UCR_containerizer": True,
        "log-dir": "hdfs://hdfs{}".format(HDFS_HISTORY_DIR),
        "hdfs-config-url": "http://api.{}.marathon.l4lb.thisdcos.directory/v1/endpoints"
            .format(HDFS_SERVICE_NAME)
    },
    "security": {
        "kerberos": {
            "enabled": True,
            "krb5conf": HDFS_KRB5_CONF,
            "principal": GENERIC_HDFS_USER_PRINCIPAL,
            "keytab": KEYTAB_SECRET_PATH
        }
    }
}


@pytest.fixture()
def setup_history_server(hdfs_with_kerberos, setup_hdfs_client, configure_universe, use_ucr_containerizer):
    try:
        sdk_auth.kinit(HDFS_CLIENT_ID, keytab="hdfs.keytab", principal=GENERIC_HDFS_USER_PRINCIPAL)
        hdfs_cmd("rm -r -skipTrash {}".format(HDFS_HISTORY_DIR))
        hdfs_cmd("mkdir {}".format(HDFS_HISTORY_DIR))
        hdfs_cmd("chmod 1777 {}".format(HDFS_HISTORY_DIR))

        options = SPARK_HISTORY_SERVICE_OPTIONS

        if not use_ucr_containerizer:
            user_options = {
                "service": {
                    "UCR_containerizer": False,
                    "docker_user": "99"
                }
            }

            options = sdk_install.merge_dictionaries(options, user_options)

        sdk_install.uninstall(HISTORY_PACKAGE_NAME, HISTORY_SERVICE_NAME)
        sdk_install.install(
            HISTORY_PACKAGE_NAME,
            HISTORY_SERVICE_NAME,
            0,
            additional_options=options,
            wait_for_deployment=False,  # no deploy plan
            insert_strict_options=False)  # no standard service_account/etc options
        yield

    finally:
        sdk_install.uninstall(HISTORY_PACKAGE_NAME, HISTORY_SERVICE_NAME)


@pytest.fixture()
def spark_with_history_server(setup_history_server, kerberos_options, configure_security_spark):
    try:
        additional_options = {
            "hdfs": {
                "config-url": "http://api.{}.marathon.l4lb.thisdcos.directory/v1/endpoints".format(HDFS_SERVICE_NAME)
            },
            "security": kerberos_options,
            "service": {
                "spark-history-server-url": shakedown.dcos_url_path("/service/{}".format(HISTORY_SERVICE_NAME))
            }
        }

        utils.require_spark(additional_options=additional_options)
        yield
    finally:
        utils.teardown_spark()


@sdk_utils.dcos_ee_only
@pytest.mark.skipif(not utils.hdfs_enabled(), reason='HDFS_ENABLED is false')
@pytest.mark.sanity
@pytest.mark.parametrize('use_ucr_containerizer', [
    True,
    False
])
def test_history_server(spark_with_history_server):
    job_args = ["--class", "org.apache.spark.examples.SparkPi",
                "--conf", "spark.eventLog.enabled=true",
                "--conf", "spark.eventLog.dir=hdfs://hdfs{}".format(HDFS_HISTORY_DIR)]

    utils.run_tests(app_url=utils.SPARK_EXAMPLES,
                    app_args="100",
                    expected_output="Pi is roughly 3",
                    service_name="spark",
                    args=(job_args + SPARK_SUBMIT_HDFS_KERBEROS_ARGS))

#     TODO: add SHS REST check to verify it's working
