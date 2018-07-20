import base64
import logging
import os
import pytest

import spark_s3 as s3
import spark_utils as utils

import sdk_auth
import sdk_cmd
import sdk_hosts
import sdk_install
import sdk_tasks
import sdk_security


LOGGER = logging.getLogger(__name__)
THIS_DIR = os.path.dirname(os.path.abspath(__file__))

PRODUCER_SERVICE_NAME = "Spark->Kafka Producer"

DEFAULT_KAFKA_TASK_COUNT=3
KERBERIZED_KAFKA = True
KAFKA_KRB5_ORIG = b'''[libdefaults]
default_realm = LOCAL

[realms]
  LOCAL = {
    kdc = kdc.marathon.autoip.dcos.thisdcos.directory:2500
  }
'''
KAFKA_KRB5 = base64.b64encode(KAFKA_KRB5_ORIG).decode('utf8')

KAFKA_PACKAGE_NAME = os.getenv("KAFKA_PACKAGE_NAME", "kafka")
KAFKA_SERVICE_NAME = os.getenv("KAFKA_SERVICE_NAME", ("secure-kafka" if KERBERIZED_KAFKA else "kafka"))


@pytest.fixture(scope='module')
def configure_security_kafka():
    yield from sdk_security.security_session(KAFKA_SERVICE_NAME)


@pytest.fixture(scope='module')
def kerberized_kafka(configure_security_kafka):
    try:
        fqdn = "{service_name}.{host_suffix}".format(service_name=KAFKA_SERVICE_NAME,
                                                     host_suffix=sdk_hosts.AUTOIP_HOST_SUFFIX)

        brokers = ["kafka-0-broker", "kafka-1-broker", "kafka-2-broker"]

        principals = []
        for b in brokers:
            principals.append("kafka/{instance}.{domain}@{realm}".format(
                instance=b,
                domain=fqdn,
                realm=sdk_auth.REALM))

        principals.append("client@{realm}".format(realm=sdk_auth.REALM))

        kerberos_env = sdk_auth.KerberosEnvironment()
        kerberos_env.add_principals(principals)
        kerberos_env.finalize()

        service_kerberos_options = {
            "service": {
                "name": KAFKA_SERVICE_NAME,
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
            }
        }

        sdk_install.uninstall(KAFKA_PACKAGE_NAME, KAFKA_SERVICE_NAME)
        sdk_install.install(
            KAFKA_PACKAGE_NAME,
            KAFKA_SERVICE_NAME,
            DEFAULT_KAFKA_TASK_COUNT,
            additional_options=service_kerberos_options,
            timeout_seconds=30 * 60)

        yield kerberos_env

    finally:
        sdk_install.uninstall(KAFKA_PACKAGE_NAME, KAFKA_SERVICE_NAME)
        kerberos_env.cleanup()


@pytest.fixture(scope='module')
def configure_security_spark():
    yield from utils.spark_security_session()


@pytest.fixture(scope='module', autouse=True)
def setup_spark(kerberized_kafka, configure_security_spark, configure_universe):
    try:
        utils.upload_dcos_test_jar()
        utils.require_spark()
        yield
    finally:
        utils.teardown_spark()


@pytest.mark.sanity
@pytest.mark.smoke
@pytest.mark.skipif(not utils.kafka_enabled(), reason='KAFKA_ENABLED is false')
def test_spark_and_kafka():
    kerberos_flag = "true" if KERBERIZED_KAFKA else "false"  # flag for using kerberized kafka given to app
    stop_count = "48"  # some reasonable number
    test_pipeline(
        kerberos_flag=kerberos_flag,
        jar_uri=utils.dcos_test_jar_url(),
        keytab_secret="__dcos_base64___keytab",
        stop_count=stop_count,
        spark_service_name=utils.SPARK_SERVICE_NAME)


def test_pipeline(kerberos_flag, stop_count, jar_uri, keytab_secret, spark_service_name, jaas_uri=None):
    stop_count = str(stop_count)
    kerberized = True if kerberos_flag == "true" else False
    broker_dns = sdk_cmd.svc_cli(KAFKA_PACKAGE_NAME, KAFKA_SERVICE_NAME, 'endpoints broker', json=True)['dns'][0]
    topic = "top1"

    big_file, big_file_url = "file:///mnt/mesos/sandbox/big.txt", "http://norvig.com/big.txt"

    # arguments to the application
    producer_args = " ".join([broker_dns, big_file, topic, kerberos_flag])

    uris = "spark.mesos.uris={}".format(big_file_url)

    if kerberized and jaas_uri is None:
        jaas_path = os.path.join(THIS_DIR, "resources", "spark-kafka-client-jaas.conf")
        s3.upload_file(jaas_path)
        _uri = s3.http_url("spark-kafka-client-jaas.conf")
        uris += ",{}".format(_uri)
    else:
        uris += ",{}".format(jaas_uri)

    common_args = [
        "--conf", "spark.mesos.containerizer=mesos",
        "--conf", "spark.scheduler.maxRegisteredResourcesWaitingTime=2400s",
        "--conf", "spark.scheduler.minRegisteredResourcesRatio=1.0",
        "--conf", uris
    ]

    kerberos_args = [
        "--conf", "spark.mesos.driver.secret.names={}".format(keytab_secret),
        "--conf", "spark.mesos.driver.secret.filenames=kafka-client.keytab",
        "--conf", "spark.mesos.executor.secret.names={}".format(keytab_secret),
        "--conf", "spark.mesos.executor.secret.filenames=kafka-client.keytab",
        "--conf", "spark.mesos.task.labels=DCOS_SPACE:/{}".format(spark_service_name),
        "--conf", "spark.executorEnv.KRB5_CONFIG_BASE64={}".format(KAFKA_KRB5),
        "--conf", "spark.mesos.driverEnv.KRB5_CONFIG_BASE64={}".format(KAFKA_KRB5),
        "--conf", "spark.driver.extraJavaOptions=-Djava.security.auth.login.config="
                  "/mnt/mesos/sandbox/spark-kafka-client-jaas.conf",
        "--conf", "spark.executor.extraJavaOptions="
                  "-Djava.security.auth.login.config=/mnt/mesos/sandbox/spark-kafka-client-jaas.conf",
    ]

    producer_config = ["--conf", "spark.cores.max=2", "--conf", "spark.executor.cores=2",
                       "--class", "KafkaFeeder"] + common_args

    if kerberized:
        producer_config += kerberos_args

    producer_id = utils.submit_job(app_url=jar_uri,
                                   app_args=producer_args,
                                   service_name=spark_service_name,
                                   args=producer_config)

    sdk_tasks.check_running(KAFKA_SERVICE_NAME, 1, timeout_seconds=600)

    consumer_config = ["--conf", "spark.cores.max=4", "--class", "KafkaConsumer"] + common_args

    if kerberized:
        consumer_config += kerberos_args

    consumer_args = " ".join([broker_dns, topic, stop_count, kerberos_flag])

    utils.run_tests(app_url=jar_uri,
                    app_args=consumer_args,
                    expected_output="Read {} words".format(stop_count),
                    service_name=spark_service_name,
                    args=consumer_config)

    utils.kill_driver(producer_id, spark_service_name)
