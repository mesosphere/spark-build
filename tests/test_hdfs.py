import base64
import itertools
import json
import logging
import os
import pytest
import retrying

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

DEFAULT_HDFS_TASK_COUNT = 10
GENERIC_HDFS_USER_PRINCIPAL = "hdfs@{realm}".format(realm=sdk_auth.REALM)
ALICE_USER = "alice"
ALICE_PRINCIPAL = "{user}@{realm}".format(user=ALICE_USER, realm=sdk_auth.REALM)
KEYTAB_SECRET_PATH = os.getenv("KEYTAB_SECRET_PATH", "__dcos_base64___keytab")

HDFS_PACKAGE_NAME = 'hdfs'
HDFS_SERVICE_NAME = 'hdfs'
HISTORY_PACKAGE_NAME = os.getenv("HISTORY_PACKAGE_NAME", "spark-history")
HISTORY_SERVICE_NAME = os.getenv("HISTORY_SERVICE_NAME", "spark-history")

HDFS_DATA_DIR = '/users/{}'.format(ALICE_USER)
HDFS_HISTORY_DIR = '/history'

HDFS_KRB5_CONF_ORIG = '''[libdefaults]
default_realm = %(realm)s
dns_lookup_realm = true
dns_lookup_kdc = true
udp_preference_limit = 1

[realms]
  %(realm)s = {
    kdc = kdc.marathon.mesos:2500
  }

[domain_realm]
  .hdfs.dcos = %(realm)s
  hdfs.dcos = %(realm)s
''' % {"realm": sdk_auth.REALM} # avoid format() due to problems with "{" in string
HDFS_KRB5_CONF = base64.b64encode(HDFS_KRB5_CONF_ORIG.encode('utf8')).decode('utf8')

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
                "name": HDFS_SERVICE_NAME,
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
        hdfs_cmd("rm -r -skipTrash {}".format(HDFS_DATA_DIR))
        hdfs_cmd("mkdir -p {}".format(HDFS_DATA_DIR))
        hdfs_cmd("chown {}:users {}".format(ALICE_USER, HDFS_DATA_DIR))
        yield

    finally:
        sdk_marathon.destroy_app(HDFS_CLIENT_ID)


def hdfs_cmd(cmd):
    rc, _, _ = sdk_cmd.marathon_task_exec(HDFS_CLIENT_ID, "bin/hdfs dfs -{}".format(cmd))
    if rc != 0:
        raise Exception("HDFS command failed with code {}: {}".format(rc, cmd))


@pytest.fixture(scope='module')
def setup_history_server(hdfs_with_kerberos, setup_hdfs_client, configure_universe):
    try:
        sdk_auth.kinit(HDFS_CLIENT_ID, keytab="hdfs.keytab", principal=GENERIC_HDFS_USER_PRINCIPAL)
        hdfs_cmd("rm -r -skipTrash {}".format(HDFS_HISTORY_DIR))
        hdfs_cmd("mkdir {}".format(HDFS_HISTORY_DIR))
        hdfs_cmd("chmod 1777 {}".format(HDFS_HISTORY_DIR))

        sdk_install.uninstall(HISTORY_PACKAGE_NAME, HISTORY_SERVICE_NAME)
        sdk_install.install(
            HISTORY_PACKAGE_NAME,
            HISTORY_SERVICE_NAME,
            0,
            additional_options={
                "service": {
                    "name": HISTORY_SERVICE_NAME,
                    "user": SPARK_HISTORY_USER,
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
            },
            wait_for_deployment=False, # no deploy plan
            insert_strict_options=False) # no standard service_account/etc options
        yield

    finally:
        sdk_install.uninstall(HISTORY_PACKAGE_NAME, HISTORY_SERVICE_NAME)


@pytest.fixture(scope='module', autouse=True)
def setup_spark(hdfs_with_kerberos, setup_history_server, configure_security_spark, configure_universe):
    try:
        additional_options = {
            "hdfs": {
                "config-url": "http://api.{}.marathon.l4lb.thisdcos.directory/v1/endpoints".format(HDFS_SERVICE_NAME)
            },
            "security": {
                "kerberos": {
                    "enabled": True,
                    "realm": sdk_auth.REALM,
                    "kdc": {
                        "hostname": hdfs_with_kerberos.get_host(),
                        "port": int(hdfs_with_kerberos.get_port())
                    }
                }
            },
            "service": {
                "spark-history-server-url": shakedown.dcos_url_path("/service/{}".format(HISTORY_SERVICE_NAME))
            }
        }
        utils.require_spark(additional_options=additional_options)
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
    data_dir = "hdfs://{}".format(HDFS_DATA_DIR)
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
    @retrying.retry(
        wait_fixed=1000,
        stop_max_delay=600*1000,
        retry_on_result=lambda res: not res)
    def wait_job_present(present):
        svc = shakedown.get_service(JOB_SERVICE_NAME)
        if present:
            return svc is not None
        else:
            return svc is None

    JOB_SERVICE_NAME = "RecoverableNetworkWordCount"

    job_args = ["--supervise",
                "--class", "org.apache.spark.examples.streaming.RecoverableNetworkWordCount",
                "--conf", "spark.cores.max=8",
                "--conf", "spark.executors.cores=4"]

    data_dir = "hdfs://{}".format(HDFS_DATA_DIR)
    driver_id = utils.submit_job(app_url=utils.SPARK_EXAMPLES,
                                 app_args="10.0.0.1 9090 {dir}/netcheck {dir}/outfile".format(dir=data_dir),
                                 service_name=utils.SPARK_SERVICE_NAME,
                                 args=(KERBEROS_ARGS + job_args))
    log.info("Started supervised driver {}".format(driver_id))
    wait_job_present(True)
    log.info("Job has registered")
    sdk_tasks.check_running(JOB_SERVICE_NAME, 1)
    log.info("Job has running executors")

    service_info = shakedown.get_service(JOB_SERVICE_NAME).dict()
    driver_regex = "spark.mesos.driver.frameworkId={}".format(service_info['id'])
    shakedown.kill_process_on_host(hostname=service_info['hostname'], pattern=driver_regex)

    wait_job_present(True)
    log.info("Job has re-registered")
    sdk_tasks.check_running(JOB_SERVICE_NAME, 1)
    log.info("Job has re-started")
    out = utils.kill_driver(driver_id, utils.SPARK_SERVICE_NAME)
    log.info("{}".format(out))
    out = json.loads(out)
    assert out["success"], "Failed to kill spark streaming job"
    wait_job_present(False)


@pytest.mark.skipif(not utils.hdfs_enabled(), reason='HDFS_ENABLED is false')
@pytest.mark.sanity
def test_history():
    job_args = ["--class", "org.apache.spark.examples.SparkPi",
                "--conf", "spark.eventLog.enabled=true",
                "--conf", "spark.eventLog.dir=hdfs://hdfs{}".format(HDFS_HISTORY_DIR)]
    utils.run_tests(app_url=utils.SPARK_EXAMPLES,
                    app_args="100",
                    expected_output="Pi is roughly 3",
                    service_name="spark",
                    args=(job_args + KERBEROS_ARGS))


@pytest.mark.skipif(not utils.hdfs_enabled(), reason='HDFS_ENABLED is false')
@pytest.mark.sanity
def test_history_kdc_config(hdfs_with_kerberos):
    history_service_with_kdc_config = "spark-history-with-kdc-config"
    try:
        # This deployment will fail if kerberos is not configured properly.
        sdk_install.uninstall(HISTORY_PACKAGE_NAME, history_service_with_kdc_config)
        sdk_install.install(
            HISTORY_PACKAGE_NAME,
            history_service_with_kdc_config,
            0,
            additional_options={
                "service": {
                    "name": history_service_with_kdc_config,
                    "user": SPARK_HISTORY_USER,
                    "log-dir": "hdfs://hdfs{}".format(HDFS_HISTORY_DIR),
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
            wait_for_deployment=False, # no deploy plan
            insert_strict_options=False) # no standard service_account/etc options

    finally:
        sdk_marathon.destroy_app(history_service_with_kdc_config)
