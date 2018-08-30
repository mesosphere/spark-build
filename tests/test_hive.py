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
hive_agent_ip = ""
hive_agent_hostname = ""
hdfs_base_url = ""

GENERIC_HDFS_USER_PRINCIPAL = "hdfs@{realm}".format(realm=sdk_auth.REALM)
ALICE_USER = "alice"
ALICE_PRINCIPAL = "{user}@{realm}".format(user=ALICE_USER, realm=sdk_auth.REALM)
HIVE_APP_ID = "cdh5-hadoop-hive-kerberos"
THIS_DIR = os.path.dirname(os.path.abspath(__file__))


def _get_agent_ip():
    nodes = sdk_cmd.get_json_output("node --json")
    for node in nodes:
        if node["type"] == "agent":
            agent_ip = node["hostname"]
            break
    return agent_ip


@pytest.fixture(scope='module')
def setup_kdc_kerberos():
    try:
        global hive_agent_ip
        hive_agent_ip = _get_agent_ip()

        ok, stdout = sdk_cmd.agent_ssh(hive_agent_ip, "echo $HOSTNAME")
        if not ok:
            raise Exception("Failed to get agent hostname, stdout: {}".format(stdout))
        log.info("got hostname: '{}'".format(stdout))
        global hive_agent_hostname
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
        yield kerberos_env

    finally:
        #kerberos_env.cleanup()
        log.info("kerberos_env cleanup")


def _hdfs_cmd(cmd):
    rc, _, _ = sdk_cmd.marathon_task_exec(HIVE_APP_ID, "/usr/local/hadoop/bin/hdfs dfs -{}".format(cmd))
    if rc != 0:
        raise Exception("HDFS command failed with code {}: {}".format(rc, cmd))


def _upload_hdfs_config(file_name):
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
def setup_hadoop_hive(setup_kdc_kerberos):
    try:
        # TODO: replace with Marathon readiness check in kdc app
        log.info("Waiting for kdc.marathon.mesos to resolve ...")
        time.sleep(30)

        # Run the Hive Docker image in Marathon
        curr_dir = os.path.dirname(os.path.realpath(__file__))
        app_def_path = "{}/resources/hadoop-hive-kerberos.json".format(curr_dir)
        with open(app_def_path) as f:
            hive_app_def = json.load(f)
        hive_app_def["id"] = HIVE_APP_ID
        hive_app_def["constraints"] = [["hostname", "IS", hive_agent_ip]]
        sdk_marathon.install_app(hive_app_def)
        # Wait for Sentry and Hive to be ready
        # TODO: replace with Marathon readiness check
        log.info("Sleeping 120s ...")
        time.sleep(120)

        # HDFS client configuration
        core_site_url = _upload_hdfs_config("core-site.xml")
        _upload_hdfs_config("hdfs-site.xml")
        global hdfs_base_url
        hdfs_base_url = os.path.dirname(core_site_url)
        yield

    finally:
        #sdk_marathon.destroy_app(HIVE_APP_ID)
        log.info("setup_hive cleanup")


@pytest.fixture(scope='module')
def configure_security_spark():
    yield from spark_utils.spark_security_session()


@pytest.fixture(scope='module', autouse=True)
def setup_spark(setup_kdc_kerberos, setup_hadoop_hive, configure_security_spark):
    try:
        additional_options = {
            "hdfs": {
                "config-url": hdfs_base_url
            },
            "security": {
                "kerberos": {
                    "enabled": True,
                    "realm": sdk_auth.REALM,
                    "kdc": {
                        "hostname": setup_kdc_kerberos.get_host(),
                        "port": int(setup_kdc_kerberos.get_port())
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
def test_hive(setup_hadoop_hive, setup_spark):
    # Job writes to this hdfs directory
    _hdfs_cmd("chmod a+w /")

    _grant_hive_privileges()

    jar_url = spark_utils.dcos_test_jar_url()
    app_args = "thrift://{}:9083".format(hive_agent_hostname)
    keytab_secret_path = "__dcos_base64___keytab"
    kerberos_args = ["--kerberos-principal", ALICE_PRINCIPAL,
                     "--keytab-secret-path", "/{}".format(keytab_secret_path),
                     "--conf", "spark.mesos.driverEnv.SPARK_USER={}".format(spark_utils.SPARK_USER)]
    submit_args = ["--class", "HiveFull"] + kerberos_args \
                  + ["--conf", "spark.mesos.executor.docker.image=mesosphere/spark-dev:081e586fa721ccb2f41d9f38c0b87d324a6caca4-67fa977eef418bb9d6a3f234b1191c558ab2b264"]

    expected_output = "Test completed successfully"
    spark_utils.run_tests(app_url=jar_url,
                          app_args=app_args,
                          expected_output=expected_output,
                          args=submit_args)
