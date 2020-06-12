import base64
import logging
import json
import os
import pytest
import sdk_agents
import sdk_auth
import sdk_cmd
import sdk_install
import sdk_marathon
import sdk_security
import sdk_utils
import shakedown
import spark_utils as utils

from tests.integration import hdfs_auth

LOGGER = logging.getLogger(__name__)

DEFAULT_HDFS_TASK_COUNT = 10
GENERIC_HDFS_USER_PRINCIPAL = "hdfs@{realm}".format(realm=sdk_auth.REALM)
ALICE_USER = "alice"
ALICE_PRINCIPAL = "{user}@{realm}".format(user=ALICE_USER, realm=sdk_auth.REALM)
KEYTAB_SECRET_PATH = os.getenv("KEYTAB_SECRET_PATH", "__dcos_base64___keytab")

HDFS_PACKAGE_NAME = 'hdfs'
HDFS_SERVICE_NAME = 'hdfs'
HDFS_SERVICE_ACCOUNT = "{}-service-acct".format(HDFS_SERVICE_NAME)
HDFS_SERVICE_ACCOUNT_SECRET = "{}-secret".format(HDFS_SERVICE_NAME)
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
''' % {"realm": sdk_auth.REALM}  # avoid format() due to problems with "{" in string
HDFS_KRB5_CONF = base64.b64encode(HDFS_KRB5_CONF_ORIG.encode('utf8')).decode('utf8')

SPARK_SUBMIT_HDFS_KERBEROS_ARGS = ["--kerberos-principal", ALICE_PRINCIPAL,
                 "--keytab-secret-path", "/{}".format(KEYTAB_SECRET_PATH),
                 "--conf", "spark.mesos.driverEnv.SPARK_USER={}".format(utils.SPARK_USER)]

HDFS_CLIENT_ID = "hdfsclient"
SPARK_HISTORY_USER = "nobody"


@pytest.fixture(scope="package")
def install_krb_workstation():
    for agent in sdk_agents.get_agents():
        sdk_cmd.agent_ssh(agent["hostname"], "sudo yum install krb5-workstation -y")
    yield


@pytest.fixture(scope='package')
def configure_security_hdfs():
    yield from sdk_security.security_session(framework_name=HDFS_SERVICE_NAME,
                                             service_account=HDFS_SERVICE_ACCOUNT,
                                             secret=HDFS_SERVICE_ACCOUNT_SECRET)


@pytest.fixture(scope='package')
def hdfs_with_kerberos(install_krb_workstation, configure_security_hdfs, kerberos_options):
    try:
        additional_options = {
            "service": {
                "name": HDFS_SERVICE_NAME,
                "security": kerberos_options
            },
            "hdfs": {
                "security_auth_to_local": hdfs_auth.get_principal_to_user_mapping()
            }
        }

        if sdk_utils.is_strict_mode():
            additional_options["service"]["service_account"] = HDFS_SERVICE_ACCOUNT
            additional_options["service"]["principal"] = HDFS_SERVICE_ACCOUNT
            additional_options["service"]["service_account_secret"] = HDFS_SERVICE_ACCOUNT_SECRET
            additional_options["service"]["secret_name"] = HDFS_SERVICE_ACCOUNT_SECRET

        sdk_install.uninstall(HDFS_PACKAGE_NAME, HDFS_SERVICE_NAME)
        sdk_install.install(
            HDFS_PACKAGE_NAME,
            HDFS_SERVICE_NAME,
            DEFAULT_HDFS_TASK_COUNT,
            additional_options=additional_options,
            timeout_seconds=30 * 60)

        yield

    finally:
        sdk_install.uninstall(HDFS_PACKAGE_NAME, HDFS_SERVICE_NAME)


@pytest.fixture(scope='package')
def setup_hdfs_client(hdfs_with_kerberos):
    try:
        curr_dir = os.path.dirname(os.path.realpath(__file__))
        app_def_path = "{}/../resources/hdfsclient.json".format(curr_dir)
        with open(app_def_path) as f:
            hdfsclient_app_def = json.load(f)
        hdfsclient_app_def["id"] = HDFS_CLIENT_ID
        hdfsclient_app_def["secrets"]["hdfs_keytab"]["source"] = KEYTAB_SECRET_PATH
        sdk_marathon.install_app(hdfsclient_app_def)

        sdk_auth.kinit(HDFS_CLIENT_ID, keytab="hdfs.keytab", principal=GENERIC_HDFS_USER_PRINCIPAL)
        hdfs_cmd("rm -r -f -skipTrash {}".format(HDFS_DATA_DIR))
        hdfs_cmd("mkdir -p {}".format(HDFS_DATA_DIR))
        hdfs_cmd("chown {}:users {}".format(ALICE_USER, HDFS_DATA_DIR))
        yield

    finally:
        sdk_marathon.destroy_app(HDFS_CLIENT_ID)


def hdfs_cmd(cmd):
    LOGGER.info('Running command %s', cmd)
    rc, _, _ = sdk_cmd.marathon_task_exec(HDFS_CLIENT_ID, "bin/hdfs dfs -{}".format(cmd))
    if rc != 0:
        raise Exception("HDFS command failed with code {}: {}".format(rc, cmd))


@pytest.fixture(scope='package')
def setup_history_server(hdfs_with_kerberos, setup_hdfs_client, configure_universe):
    try:
        LOGGER.info('Preparing to install History Server')
        sdk_auth.kinit(HDFS_CLIENT_ID, keytab="hdfs.keytab", principal=GENERIC_HDFS_USER_PRINCIPAL)

        LOGGER.info('Creating History Server HDFS directory')
        hdfs_cmd("rm -r -f -skipTrash {}".format(HDFS_HISTORY_DIR))
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
            wait_for_deployment=False,  # no deploy plan
            insert_strict_options=False)  # no standard service_account/etc options
        yield

    finally:
        sdk_install.uninstall(HISTORY_PACKAGE_NAME, HISTORY_SERVICE_NAME)


@pytest.fixture(scope='package')
def kerberized_spark(setup_history_server, hdfs_with_kerberos, kerberos_options, configure_security_spark, configure_universe):
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
