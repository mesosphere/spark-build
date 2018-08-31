import json
import logging
import os
import pytest
import tempfile
import time

import sdk_auth
import sdk_cmd
import sdk_marathon

import spark_utils


log = logging.getLogger(__name__)

GENERIC_HDFS_USER_PRINCIPAL = "hdfs@{realm}".format(realm=sdk_auth.REALM)
ALICE_USER = "alice"
ALICE_PRINCIPAL = "{user}@{realm}".format(user=ALICE_USER, realm=sdk_auth.REALM)
HIVE_APP_ID = "cdh5-hadoop-hive-kerberos"
THIS_DIR = os.path.dirname(os.path.abspath(__file__))


class KerberosSetup:
    def __init__(self, kerberos_env, hive_agent_ip, hive_agent_hostname):
        self.kerberos_env = kerberos_env
        self.hive_agent_ip = hive_agent_ip
        self.hive_agent_hostname = hive_agent_hostname


class HadoopSetup:
    def __init__(self, kerberos_setup, hdfs_base_url, hive_config_url):
        self.kerberos_setup = kerberos_setup
        self.hdfs_base_url = hdfs_base_url
        self.hive_config_url = hive_config_url


def _get_agent_ip():
    nodes = sdk_cmd.get_json_output("node --json")
    for node in nodes:
        if node["type"] == "agent":
            agent_ip = node["hostname"]
            break
    return agent_ip


@pytest.fixture(scope='module')
def kerberos_setup():
    try:
        hive_agent_ip = _get_agent_ip()

        ok, stdout = sdk_cmd.agent_ssh(hive_agent_ip, "echo $HOSTNAME")
        if not ok:
            raise Exception("Failed to get agent hostname, stdout: {}".format(stdout))
        log.info("got hostname: '{}'".format(stdout))
        hive_agent_hostname = stdout.rstrip()

        primaries = ["alice", "hdfs", "HTTP", "yarn", "hive", "sentry"]
        principals = [ "{primary}/{instance}@{REALM}".format(
            primary=primary,
            instance=hive_agent_hostname,
            REALM=sdk_auth.REALM
        ) for primary in primaries ]
        principals.append(GENERIC_HDFS_USER_PRINCIPAL)
        principals.append(ALICE_PRINCIPAL)

        kerberos_env = sdk_auth.KerberosEnvironment()
        kerberos_env.add_principals(principals)
        kerberos_env.finalize()
        yield KerberosSetup(kerberos_env, hive_agent_ip, hive_agent_hostname)

    finally:
        kerberos_env.cleanup()


def _hdfs_cmd(cmd):
    rc, _, _ = sdk_cmd.marathon_task_exec(HIVE_APP_ID, "/usr/local/hadoop/bin/hdfs dfs -{}".format(cmd))
    if rc != 0:
        raise Exception("HDFS command failed with code {}: {}".format(rc, cmd))


def _upload_hadoop_config(file_name, hive_agent_hostname):
    template_local_path = os.path.join(THIS_DIR, 'resources', "{}.template".format(file_name))
    with open(template_local_path, 'r') as f:
        template_contents = f.read()

    with tempfile.TemporaryDirectory() as temp_dir:
        local_path = os.path.join(temp_dir, file_name)
        with open(local_path, 'w') as fp:
            fp.write(template_contents.replace("{{HOSTNAME}}", hive_agent_hostname))
        url = spark_utils.upload_file(local_path)
    return url


@pytest.fixture(scope='module')
def hadoop_setup(kerberos_setup):
    try:
        # TODO: replace with Marathon readiness check in kdc app?
        #log.info("Waiting for kdc.marathon.mesos to resolve ...")
        #time.sleep(10)

        # Run the Hive Docker image in Marathon
        curr_dir = os.path.dirname(os.path.realpath(__file__))
        app_def_path = "{}/resources/hadoop-hive-kerberos.json".format(curr_dir)
        with open(app_def_path) as f:
            hive_app_def = json.load(f)
        hive_app_def["id"] = HIVE_APP_ID
        hive_app_def["constraints"] = [["hostname", "IS", kerberos_setup.hive_agent_ip]]
        sdk_marathon.install_app(hive_app_def)
        # Wait for Sentry and Hive to be ready
        # TODO: replace with Marathon health check
        log.info("Sleeping 120s ...")
        time.sleep(120)

        # HDFS client configuration
        core_site_url = _upload_hadoop_config("core-site.xml", kerberos_setup.hive_agent_hostname)
        _upload_hadoop_config("hdfs-site.xml", kerberos_setup.hive_agent_hostname)
        hive_config_url = _upload_hadoop_config("hive-site.xml", kerberos_setup.hive_agent_hostname)
        hdfs_base_url = os.path.dirname(core_site_url)
        yield HadoopSetup(kerberos_setup, hdfs_base_url, hive_config_url)

    finally:
        sdk_marathon.destroy_app(HIVE_APP_ID)


@pytest.fixture(scope='module')
def configure_security_spark():
    yield from spark_utils.spark_security_session()


@pytest.fixture(scope='module', autouse=True)
def setup_spark(kerberos_setup, hadoop_setup, configure_security_spark):
    try:
        spark_utils.upload_dcos_test_jar()
        additional_options = {
            "hdfs": {
                "config-url": hadoop_setup.hdfs_base_url
            },
            "security": {
                "kerberos": {
                    "enabled": True,
                    "realm": sdk_auth.REALM,
                    "kdc": {
                        "hostname": kerberos_setup.kerberos_env.get_host(),
                        "port": int(kerberos_setup.kerberos_env.get_port())
                    }
                }
            }
        }
        spark_utils.require_spark(additional_options=additional_options)
        yield
    finally:
        spark_utils.teardown_spark()


def _grant_hive_privileges():
    rc, _, err = sdk_cmd.marathon_task_exec(HIVE_APP_ID, "/etc/grant-hive-privileges.sh")
    if rc != 0:
        raise Exception("Hive script failed with code {}: {}".format(rc, err))


@pytest.mark.sanity
def test_hive(hadoop_setup, setup_spark):
    # Job writes to this hdfs directory
    _hdfs_cmd("chmod a+w /")

    _grant_hive_privileges()

    jar_url = spark_utils.dcos_test_jar_url()
    app_args = "thrift://{}:9083".format(hadoop_setup.kerberos_setup.hive_agent_hostname)
    keytab_secret_path = "__dcos_base64___keytab"
    kerberos_args = ["--kerberos-principal", ALICE_PRINCIPAL,
                     "--keytab-secret-path", "/{}".format(keytab_secret_path),
                     "--conf", "spark.mesos.driverEnv.SPARK_USER={}".format(spark_utils.SPARK_USER)]
    # TODO: remove the following docker image once the fix is in the Spark distribution
    submit_args = ["--class", "HiveFull"] + kerberos_args \
                  + ["--conf", "spark.mesos.executor.docker.image=susanxhuynh/spark:sentry-hive-test"] \
                  + ["--conf", "spark.mesos.uris={}".format(hadoop_setup.hive_config_url)]

    expected_output = "Test completed successfully"
    spark_utils.run_tests(app_url=jar_url,
                          app_args=app_args,
                          expected_output=expected_output,
                          args=submit_args)
