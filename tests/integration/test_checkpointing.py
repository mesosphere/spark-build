import logging

import pytest
import sdk_auth
import sdk_cmd
import sdk_tasks
import sdk_utils
import shakedown
import spark_utils as utils

from tests.integration.fixture_hdfs import SPARK_SUBMIT_HDFS_KERBEROS_ARGS, HDFS_CLIENT_ID, GENERIC_HDFS_USER_PRINCIPAL
from tests.integration.fixture_hdfs import hdfs_cmd
from tests.integration.fixture_kafka import KAFKA_SERVICE_NAME, KAFKA_PACKAGE_NAME
from tests.integration.fixture_kafka import get_kerberized_kafka_spark_conf, upload_jaas

LOGGER = logging.getLogger(__name__)
HDFS_CHECKPOINT_DIR = "hdfs://hdfs/checkpoints"
HDFS_TMP_DIR = "/tmp"
KAFKA_TEST_TOPIC = "streaming_test"
SPARK_APPLICATION_NAME = "StructuredStreamingWithCheckpointing"
SPARK_SECURITY_PROTOCOL = "SASL_PLAINTEXT"


def setup_hdfs_paths():
    sdk_auth.kinit(HDFS_CLIENT_ID, keytab="hdfs.keytab", principal=GENERIC_HDFS_USER_PRINCIPAL)
    hdfs_cmd("rm -r -f -skipTrash {}".format(HDFS_CHECKPOINT_DIR))
    hdfs_cmd("mkdir {}".format(HDFS_CHECKPOINT_DIR))
    hdfs_cmd("chmod 1777 {}".format(HDFS_CHECKPOINT_DIR))

    hdfs_cmd("rm -r -f -skipTrash {}".format(HDFS_TMP_DIR))
    hdfs_cmd("mkdir {}".format(HDFS_TMP_DIR))
    hdfs_cmd("chmod 1777 {}".format(HDFS_TMP_DIR))


def feed_sample_data(jar_uri, kafka_brokers, topic, common_args, messages):
    producer_args = ["--class", "KerberizedKafkaProducer"] + common_args
    producer_id = utils.submit_job(app_url=jar_uri,
                                   app_args="{} {} {} {}".format("kafka", kafka_brokers, topic, ' '.join(messages)),
                                   service_name=utils.SPARK_SERVICE_NAME,
                                   args=producer_args)

    # validating producer output
    utils.check_job_output(producer_id, "{} messages sent to Kafka".format(len(messages)))


@sdk_utils.dcos_ee_only
@pytest.mark.skipif(not utils.hdfs_enabled(), reason='HDFS_ENABLED is false')
@pytest.mark.sanity
def test_structured_streaming_recovery(kerberized_spark, kerberized_kafka):
    kafka_brokers = ','.join(sdk_cmd.svc_cli(KAFKA_PACKAGE_NAME, KAFKA_SERVICE_NAME, 'endpoints broker', json=True)['dns'])
    LOGGER.info("Kafka brokers: {}".format(kafka_brokers))

    _uri = upload_jaas()
    uris = "spark.mesos.uris={}".format(_uri)

    jar_uri = utils.upload_dcos_test_jar()

    kafka_kerberos_args = get_kerberized_kafka_spark_conf(utils.SPARK_SERVICE_NAME)
    LOGGER.info("Spark Kerberos configuration for Kafka:\n{}".format('\n'.join(kafka_kerberos_args)))

    common_args = [
        "--conf", "spark.mesos.containerizer=mesos",
        "--conf", "spark.scheduler.maxRegisteredResourcesWaitingTime=2400s",
        "--conf", "spark.scheduler.minRegisteredResourcesRatio=1.0",
        "--conf", uris
    ] + kafka_kerberos_args

    # configuring streaming job and HDFS folders
    setup_hdfs_paths()

    # running kafka producer
    message_set_a = ["abc"] * 100
    feed_sample_data(jar_uri, kafka_brokers, KAFKA_TEST_TOPIC, common_args, message_set_a)

    spark_submit_args = ["--supervise",
                         "--class", "StructuredStreamingWithCheckpointing",
                         "--conf", "spark.cores.max=2",
                         "--conf", "spark.executor.cores=1",
                         "--conf", "spark.sql.shuffle.partitions=2",
                         "--conf", "spark.executor.memory=2g"] + common_args

    application_args = "{} {} {} {}".format(kafka_brokers, KAFKA_TEST_TOPIC, HDFS_CHECKPOINT_DIR, SPARK_SECURITY_PROTOCOL)

    driver_task_id = utils.submit_job(app_url=jar_uri,
                                      app_args=application_args,
                                      service_name=utils.SPARK_SERVICE_NAME,
                                      args=(SPARK_SUBMIT_HDFS_KERBEROS_ARGS + spark_submit_args))

    # Wait until executor is running
    LOGGER.info("Starting supervised driver {}".format(driver_task_id))
    sdk_tasks.check_running(SPARK_APPLICATION_NAME, expected_task_count=1, timeout_seconds=600)

    # validating Structured Streaming topic consumption
    expected_output_a = "{}|  {}".format(message_set_a[0], len(message_set_a))
    LOGGER.info("Validating Structured Streaming topic consumption, waiting for output {}".format(expected_output_a))
    utils.wait_for_running_job_output(driver_task_id, expected_output_a)

    # killing the driver
    service_info = shakedown.get_service(SPARK_APPLICATION_NAME).dict()
    driver_regex = "spark.mesos.driver.frameworkId={}".format(service_info['id'])
    sdk_cmd.kill_task_with_pattern(agent_host=service_info['hostname'], pattern=driver_regex)

    # sending more data to Kafka
    message_set_b = ["def"] * 100
    feed_sample_data(jar_uri, kafka_brokers, KAFKA_TEST_TOPIC, common_args + kafka_kerberos_args, message_set_b)

    # checkpointing validation
    sdk_tasks.check_running(SPARK_APPLICATION_NAME, expected_task_count=1, timeout_seconds=600)
    LOGGER.info("Streaming job has re-started")

    # validating Structured Streaming resumed topic consumption
    expected_output_b = "{}|  {}".format(message_set_b[0], len(message_set_b))
    LOGGER.info("Validating that consumption resumed from checkpoint, waiting for output '{}' and '{}'"
                .format(expected_output_a, expected_output_b))

    utils.wait_for_running_job_output(driver_task_id, expected_output_a)
    utils.wait_for_running_job_output(driver_task_id, expected_output_b)
