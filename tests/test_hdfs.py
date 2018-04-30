import itertools
import logging
import os
import pytest
import json

import shakedown

import sdk_auth
import sdk_cmd
import sdk_hosts
import sdk_install
import sdk_marathon
import sdk_security
import sdk_tasks

from tests import hdfs_auth
import spark_utils as utils


log = logging.getLogger(__name__)
DEFAULT_HDFS_TASK_COUNT=10
GENERIC_HDFS_USER_PRINCIPAL = "hdfs@{realm}".format(realm=sdk_auth.REALM)
ALICE_PRINCIPAL = "alice@{realm}".format(realm=sdk_auth.REALM)
KEYTAB_SECRET_PATH = os.getenv("KEYTAB_SECRET_PATH", "__dcos_base64___keytab")
# To do: change when no longer using HDFS stub universe
HDFS_PACKAGE_NAME='beta-hdfs'
HDFS_SERVICE_NAME='hdfs'
KERBEROS_ARGS = ["--kerberos-principal", ALICE_PRINCIPAL,
                 "--keytab-secret-path", "/{}".format(KEYTAB_SECRET_PATH),
                 "--conf", "spark.mesos.driverEnv.SPARK_USER={}".format(utils.SPARK_USER)]
HDFS_CLIENT_ID = "hdfsclient"
SPARK_HISTORY_USER = "nobody"


@pytest.fixture(scope='module')
def configure_security_hdfs():
    yield from sdk_security.security_session(HDFS_SERVICE_NAME)


@pytest.fixture(scope='module')
def hdfs_with_kerberos(configure_security_hdfs):
    try:
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
        principals.append(ALICE_PRINCIPAL)

        kerberos_env = sdk_auth.KerberosEnvironment()
        kerberos_env.add_principals(principals)
        kerberos_env.finalize()
        service_kerberos_options = {
            "service": {
                "security": {
                    "kerberos": {
                        "enabled": True,
                        "kdc": {
                            "hostname": kerberos_env.get_host(),
                            "port": int(kerberos_env.get_port())
                        },
                        "keytab_secret": kerberos_env.get_keytab_path(),
                        "realm": kerberos_env.get_realm()
                    }
                }
            },
            "hdfs": {
                "security_auth_to_local": hdfs_auth.get_principal_to_user_mapping()
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


@pytest.fixture(scope='module')
def configure_security_spark():
    yield from utils.spark_security_session()


@pytest.fixture(scope='module')
def setup_hdfs_client(hdfs_with_kerberos):
    try:
        curr_dir = os.path.dirname(os.path.realpath(__file__))
        app_def_path = "{}/resources/hdfsclient.json".format(curr_dir)
        with open(app_def_path) as f:
            hdfsclient_app_def = json.load(f)
        hdfsclient_app_def["id"] = HDFS_CLIENT_ID
        hdfsclient_app_def["secrets"]["hdfs_keytab"]["source"] = KEYTAB_SECRET_PATH
        sdk_marathon.install_app(hdfsclient_app_def)

        sdk_auth.kinit(HDFS_CLIENT_ID, keytab="hdfs.keytab", principal=GENERIC_HDFS_USER_PRINCIPAL)
        hdfs_cmd("mkdir -p /users/alice")
        hdfs_cmd("chown alice:users /users/alice")
        yield

    finally:
        sdk_marathon.destroy_app(HDFS_CLIENT_ID)


def hdfs_cmd(cmd):
    sdk_tasks.task_exec(HDFS_CLIENT_ID, "bin/hdfs dfs -{}".format(cmd))


@pytest.fixture(scope='module')
def setup_history_server(hdfs_with_kerberos, setup_hdfs_client, configure_universe):
    try:
        sdk_auth.kinit(HDFS_CLIENT_ID, keytab="hdfs.keytab", principal=GENERIC_HDFS_USER_PRINCIPAL)
        hdfs_cmd("mkdir /history")
        hdfs_cmd("chmod 1777 /history")

        shakedown.install_package(
            package_name=utils.HISTORY_PACKAGE_NAME,
            options_json={
                "service": {
                    "user": SPARK_HISTORY_USER,
                    "hdfs-config-url": "http://api.{}.marathon.l4lb.thisdcos.directory/v1/endpoints"
                        .format(HDFS_SERVICE_NAME)
                },
                "security": {
                    "kerberos": {
                        "enabled": True,
                        "krb5conf": utils.HDFS_KRB5_CONF,
                        "principal": GENERIC_HDFS_USER_PRINCIPAL,
                        "keytab": KEYTAB_SECRET_PATH
                    }
                }
            },
            wait_for_completion=True  # wait for it to become healthy
        )
        yield

    finally:
        sdk_marathon.destroy_app(utils.HISTORY_SERVICE_NAME)


@pytest.fixture(scope='module', autouse=True)
def setup_spark(hdfs_with_kerberos, setup_history_server, configure_security_spark, configure_universe):
    try:
        utils.require_spark(use_hdfs=True, use_history=True)
        yield
    finally:
        utils.teardown_spark()


def _run_terasort_job(terasort_class, app_args, expected_output):
    jar_url = 'https://downloads.mesosphere.io/spark/examples/spark-terasort-1.1-jar-with-dependencies_2.11.jar'
    submit_args = ["--class", terasort_class] + KERBEROS_ARGS
    utils.run_tests(app_url=jar_url,
                    app_args=" ".join(app_args),
                    expected_output=expected_output,
                    args=submit_args)


@pytest.mark.skipif(not utils.hdfs_enabled(), reason='HDFS_ENABLED is false')
@pytest.mark.sanity
def test_terasort_suite():
    data_dir = "hdfs:///users/alice"
    terasort_in = "{}/{}".format(data_dir, "terasort_in")
    terasort_out = "{}/{}".format(data_dir, "terasort_out")
    terasort_validate = "{}/{}".format(data_dir, "terasort_validate")

    _run_terasort_job(terasort_class="com.github.ehiggs.spark.terasort.TeraGen",
                      app_args=["1g", terasort_in],
                      expected_output="Number of records written")

    _run_terasort_job(terasort_class="com.github.ehiggs.spark.terasort.TeraSort",
                      app_args=[terasort_in, terasort_out],
                      expected_output="")

    _run_terasort_job(terasort_class="com.github.ehiggs.spark.terasort.TeraValidate",
                      app_args=[terasort_out, terasort_validate],
                      expected_output="partitions are properly sorted")


@pytest.mark.skipif(not utils.hdfs_enabled(), reason='HDFS_ENABLED is false')
@pytest.mark.sanity
def test_supervise():
    def streaming_job_registered():
        return shakedown.get_service(JOB_SERVICE_NAME) is not None

    def streaming_job_is_not_running():
        return not streaming_job_registered()

    def has_running_executors():
        f = shakedown.get_service(JOB_SERVICE_NAME)
        if f is None:
            return False
        else:
            return len([x for x in f.dict()["tasks"] if x["state"] == "TASK_RUNNING"]) > 0

    JOB_SERVICE_NAME = "RecoverableNetworkWordCount"

    job_args = ["--supervise",
                "--class", "org.apache.spark.examples.streaming.RecoverableNetworkWordCount",
                "--conf", "spark.cores.max=8",
                "--conf", "spark.executors.cores=4"]

    data_dir = "hdfs:///users/alice"
    driver_id = utils.submit_job(app_url=utils.SPARK_EXAMPLES,
                                 app_args="10.0.0.1 9090 {dir}/netcheck {dir}/outfile".format(dir=data_dir),
                                 app_name=utils.SPARK_APP_NAME,
                                 args=(KERBEROS_ARGS + job_args))
    log.info("Started supervised driver {}".format(driver_id))
    shakedown.wait_for(lambda: streaming_job_registered(),
                       ignore_exceptions=False,
                       timeout_seconds=600)
    log.info("Job has registered")
    shakedown.wait_for(lambda: has_running_executors(),
                       ignore_exceptions=False,
                       timeout_seconds=600)
    log.info("Job has running executors")

    host = shakedown.get_service(JOB_SERVICE_NAME).dict()["hostname"]
    id = shakedown.get_service(JOB_SERVICE_NAME).dict()["id"]
    driver_regex = "spark.mesos.driver.frameworkId={}".format(id)
    shakedown.kill_process_on_host(hostname=host, pattern=driver_regex)

    shakedown.wait_for(lambda: streaming_job_registered(),
                       ignore_exceptions=False,
                       timeout_seconds=600)
    log.info("Job has re-registered")
    shakedown.wait_for(lambda: has_running_executors(),
                       ignore_exceptions=False,
                       timeout_seconds=600)
    log.info("Job has re-started")
    out = utils.kill_driver(driver_id, utils.SPARK_APP_NAME)
    log.info("{}".format(out))
    out = json.loads(out)
    assert out["success"], "Failed to kill spark streaming job"
    shakedown.wait_for(lambda: streaming_job_is_not_running(),
                       ignore_exceptions=False,
                       timeout_seconds=600)


@pytest.mark.skipif(not utils.hdfs_enabled(), reason='HDFS_ENABLED is false')
@pytest.mark.sanity
def test_history():
    job_args = ["--class", "org.apache.spark.examples.SparkPi",
                "--conf", "spark.eventLog.enabled=true",
                "--conf", "spark.eventLog.dir=hdfs://hdfs/history"]
    utils.run_tests(app_url=utils.SPARK_EXAMPLES,
                    app_args="100",
                    expected_output="Pi is roughly 3",
                    app_name="/spark",
                    args=(job_args + KERBEROS_ARGS))


@pytest.mark.skipif(not utils.hdfs_enabled(), reason='HDFS_ENABLED is false')
@pytest.mark.sanity
def test_history_kdc_config(hdfs_with_kerberos):
    history_service_with_kdc_config = "spark-history-with-kdc-config"
    try:
        # This deployment will fail if kerberos is not configured properly.
        shakedown.install_package(
            package_name=utils.HISTORY_PACKAGE_NAME,
            options_json={
                "service": {
                    "name": history_service_with_kdc_config,
                    "user": SPARK_HISTORY_USER,
                    "hdfs-config-url": "http://api.{}.marathon.l4lb.thisdcos.directory/v1/endpoints"
                        .format(HDFS_SERVICE_NAME)
                },
                "security": {
                    "kerberos": {
                        "enabled": True,
                        "kdc": {
                            "hostname": hdfs_with_kerberos.get_host(),
                            "port": int(hdfs_with_kerberos.get_port())
                        },
                        "realm": sdk_auth.REALM,
                        "principal": GENERIC_HDFS_USER_PRINCIPAL,
                        "keytab": KEYTAB_SECRET_PATH
                    }
                }
            },
            wait_for_completion=True,  # wait for it to become healthy
            timeout_sec=240
        )

    finally:
        sdk_marathon.destroy_app(history_service_with_kdc_config)
