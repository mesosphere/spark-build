import itertools
import logging
import pytest

import sdk_auth
import sdk_cmd
import sdk_hosts
import sdk_install

from tests import utils


log = logging.getLogger(__name__)
DEFAULT_HDFS_TASK_COUNT=10
GENERIC_HDFS_USER_PRINCIPAL = "hdfs@{realm}".format(realm=sdk_auth.REALM)
# To do: change when no longer using HDFS stub universe
HDFS_PACKAGE_NAME='beta-hdfs'
HDFS_SERVICE_NAME='hdfs'


@pytest.fixture(scope='module')
def hdfs_with_kerberos():
    try:
        # To do: remove the following as soon as HDFS with kerberos is released
        log.warning('Temporarily using HDFS stub universe until kerberos is released')
        sdk_cmd.run_cli('package repo add --index=0 {} {}'.format(
            'hdfs-aws',
            'https://universe-converter.mesosphere.com/transform\?url\=https://infinity-artifacts.s3.amazonaws.com/beta-hdfs/20171114-113058-4QOGHmRCbNVsmSeE/stub-universe-beta-hdfs.json')
        )

        primaries = ["hdfs", "HTTP"]
        fqdn = "{service_name}.{host_suffix}".format(
            service_name=HDFS_SERVICE_NAME, host_suffix=sdk_hosts.AUTOIP_HOST_SUFFIX)
        instances = [
            "name-0-node",
            "name-0-zkfc",
            "name-1-node",
            "name-1-zkfc",
            "journal-0-node",
            "journal-1-node",
            "journal-2-node",
            "data-0-node",
            "data-1-node",
            "data-2-node",
        ]
        principals = []
        for (instance, primary) in itertools.product(instances, primaries):
            principals.append(
                "{primary}/{instance}.{fqdn}@{REALM}".format(
                    primary=primary,
                    instance=instance,
                    fqdn=fqdn,
                    REALM=sdk_auth.REALM
                )
            )
        principals.append(GENERIC_HDFS_USER_PRINCIPAL)

        kerberos_env = sdk_auth.KerberosEnvironment()
        kerberos_env.add_principals(principals)
        kerberos_env.finalize()
        service_kerberos_options = {
            "service": {
                "kerberos": {
                    "enabled": True,
                    "kdc_host_name": kerberos_env.get_host(),
                    "kdc_host_port": kerberos_env.get_port(),
                    "keytab_secret": kerberos_env.get_keytab_path(),
                    "primary": primaries[0],
                    "primary_http": primaries[1],
                    "realm": sdk_auth.REALM
                }
            }
        }

        sdk_install.uninstall(HDFS_PACKAGE_NAME, HDFS_SERVICE_NAME)
        sdk_install.install(
            HDFS_PACKAGE_NAME,
            HDFS_SERVICE_NAME,
            DEFAULT_HDFS_TASK_COUNT,
            additional_options=service_kerberos_options,
            timeout_seconds=30*60)

        yield kerberos_env

    finally:
        sdk_install.uninstall(HDFS_PACKAGE_NAME, HDFS_SERVICE_NAME)
        sdk_cmd.run_cli('package repo remove hdfs-aws')
        if kerberos_env:
            kerberos_env.cleanup()


@pytest.fixture(scope='module', autouse=True)
def setup_spark(hdfs_with_kerberos):
    try:
        utils.require_spark(use_hdfs=True)
        yield
    finally:
        utils.teardown_spark()


@pytest.mark.skipif(not utils.hdfs_enabled(), reason='HDFS_ENABLED is false')
@pytest.mark.sanity
def test_terasort_suite():
    jar_url = 'https://downloads.mesosphere.io/spark/examples/spark-terasort-1.1-jar-with-dependencies_2.11.jar'
    kerberos_args = ["--kerberos-principal", "hdfs/name-0-node.hdfs.autoip.dcos.thisdcos.directory@LOCAL",
                     "--keytab-secret-path", "/__dcos_base64___keytab"]

    teragen_args=["--class", "com.github.ehiggs.spark.terasort.TeraGen"] + kerberos_args
    utils.run_tests(app_url=jar_url,
                    app_args="1g hdfs:///terasort_in",
                    expected_output="Number of records written",
                    app_name="/spark",
                    args=teragen_args)

    terasort_args = ["--class", "com.github.ehiggs.spark.terasort.TeraSort"] + kerberos_args
    utils.run_tests(app_url=jar_url,
                    app_args="hdfs:///terasort_in hdfs:///terasort_out",
                    expected_output="",
                    app_name="/spark",
                    args=terasort_args)

    teravalidate_args = ["--class", "com.github.ehiggs.spark.terasort.TeraValidate"] + kerberos_args
    utils.run_tests(app_url=jar_url,
                    app_args="hdfs:///terasort_out hdfs:///terasort_validate",
                    expected_output="partitions are properly sorted",
                    app_name="/spark",
                    args=teravalidate_args)
