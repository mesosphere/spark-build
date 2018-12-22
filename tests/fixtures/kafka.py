import base64
import logging
import os

import pytest
import sdk_install
import sdk_security
import sdk_utils
import spark_s3 as s3

LOGGER = logging.getLogger(__name__)

PRODUCER_SERVICE_NAME = "Spark->Kafka Producer"

DEFAULT_KAFKA_TASK_COUNT = 3
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
KAFKA_SERVICE_ACCOUNT = "{}-service-acct".format(KAFKA_SERVICE_NAME)
KAFKA_SERVICE_ACCOUNT_SECRET = "{}-secret".format(KAFKA_SERVICE_NAME)
THIS_DIR = os.path.dirname(os.path.abspath(__file__))

KEYTAB_SECRET = "__dcos_base64___keytab"

def upload_jaas():
    jaas_path = os.path.join(THIS_DIR, "..", "resources", "spark-kafka-client-jaas.conf")
    s3.upload_file(jaas_path)
    return s3.http_url("spark-kafka-client-jaas.conf")


def get_kerberized_kafka_spark_conf(spark_service_name, keytab_secret=KEYTAB_SECRET):
    return [
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


@pytest.fixture(scope='session')
def configure_security_kafka():
    yield from sdk_security.security_session(framework_name=KAFKA_SERVICE_NAME,
                                             service_account=KAFKA_SERVICE_ACCOUNT,
                                             secret=KAFKA_SERVICE_ACCOUNT_SECRET)


@pytest.fixture(scope='session')
def kerberized_kafka(configure_security_kafka, kerberos_options):
    try:
        additional_options = {
            "service": {
                "name": KAFKA_SERVICE_NAME,
                "security": kerberos_options
            },
            "kafka": {
                "default_replication_factor": 3,
                "num_partitions": 32
            }
        }

        if sdk_utils.is_strict_mode():
            additional_options["service"]["service_account"] = KAFKA_SERVICE_ACCOUNT
            additional_options["service"]["principal"] = KAFKA_SERVICE_ACCOUNT
            additional_options["service"]["service_account_secret"] = KAFKA_SERVICE_ACCOUNT_SECRET
            additional_options["service"]["secret_name"] = KAFKA_SERVICE_ACCOUNT_SECRET

        sdk_install.uninstall(KAFKA_PACKAGE_NAME, KAFKA_SERVICE_NAME)
        sdk_install.install(
            KAFKA_PACKAGE_NAME,
            KAFKA_SERVICE_NAME,
            DEFAULT_KAFKA_TASK_COUNT,
            additional_options=additional_options,
            timeout_seconds=30 * 60)

        yield

    finally:
        sdk_install.uninstall(KAFKA_PACKAGE_NAME, KAFKA_SERVICE_NAME)
