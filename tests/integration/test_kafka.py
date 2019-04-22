import logging
import os
import pytest
import sdk_cmd
import sdk_tasks
import sdk_utils
import spark_utils as utils

from tests.integration.fixture_kafka import KERBERIZED_KAFKA, KAFKA_PACKAGE_NAME, KAFKA_SERVICE_NAME, KEYTAB_SECRET
from tests.integration.fixture_kafka import get_kerberized_kafka_spark_conf, upload_jaas

LOGGER = logging.getLogger(__name__)
THIS_DIR = os.path.dirname(os.path.abspath(__file__))


@pytest.fixture(scope='module')
def setup_spark(kerberized_kafka, configure_security_spark, configure_universe):
    try:
        utils.upload_dcos_test_jar()
        utils.require_spark()
        yield
    finally:
        utils.teardown_spark()


@sdk_utils.dcos_ee_only
@pytest.mark.sanity
@pytest.mark.smoke
@pytest.mark.skipif(not utils.kafka_enabled(), reason='KAFKA_ENABLED is false')
def test_spark_and_kafka(setup_spark):
    kerberos_flag = "true" if KERBERIZED_KAFKA else "false"  # flag for using kerberized kafka given to app
    stop_count = "48"  # some reasonable number
    test_pipeline(
        kerberos_flag=kerberos_flag,
        jar_uri=utils.dcos_test_jar_url(),
        keytab_secret=KEYTAB_SECRET,
        stop_count=stop_count,
        spark_service_name=utils.SPARK_SERVICE_NAME)


def test_pipeline(kerberos_flag, stop_count, jar_uri, keytab_secret, spark_service_name, jaas_uri=None):
    stop_count = str(stop_count)
    kerberized = True if kerberos_flag == "true" else False
    broker_dns = sdk_cmd.svc_cli(KAFKA_PACKAGE_NAME, KAFKA_SERVICE_NAME, 'endpoints broker', json=True)['dns'][0]
    topic = "top1"

    big_file, big_file_url = "file:///mnt/mesos/sandbox/big.txt", "https://infinity-soak.s3.amazonaws.com/data/norvig/big.txt"

    # arguments to the application
    producer_args = " ".join([broker_dns, big_file, topic, kerberos_flag])

    uris = "spark.mesos.uris={}".format(big_file_url)

    if kerberized and jaas_uri is None:
        _uri = upload_jaas()
        uris += ",{}".format(_uri)
    else:
        uris += ",{}".format(jaas_uri)

    common_args = [
        "--conf", "spark.mesos.containerizer=mesos",
        "--conf", "spark.scheduler.maxRegisteredResourcesWaitingTime=2400s",
        "--conf", "spark.scheduler.minRegisteredResourcesRatio=1.0",
        "--conf", uris
    ]

    kerberos_args = get_kerberized_kafka_spark_conf(spark_service_name, keytab_secret)

    producer_config = ["--conf", "spark.cores.max=2", "--conf", "spark.executor.cores=1",
                       "--class", "KafkaFeeder"] + common_args

    if kerberized:
        producer_config += kerberos_args

    producer_id = utils.submit_job(app_url=jar_uri,
                                   app_args=producer_args,
                                   service_name=spark_service_name,
                                   args=producer_config)

    sdk_tasks.check_running(KAFKA_SERVICE_NAME, 1, timeout_seconds=600)

    consumer_config = ["--conf", "spark.cores.max=2", "--conf", "spark.executor.cores=1",
                       "--class", "KafkaConsumer"] + common_args

    if kerberized:
        consumer_config += kerberos_args

    consumer_args = " ".join([broker_dns, topic, stop_count, kerberos_flag])

    try:
        utils.run_tests(app_url=jar_uri,
                    app_args=consumer_args,
                    expected_output="Read {} words".format(stop_count),
                    service_name=spark_service_name,
                    args=consumer_config)
    finally:
        utils.kill_driver(producer_id, spark_service_name)

