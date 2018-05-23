#!/usr/bin/env python3

"""
kafka_cassandra_streaming_test.py

Usage:
    ./kafka_cassandra_streaming_test.py <dispatcher_file> <infrastructure_file> <submissions_output_file> [options]

Arguments:
    dispatcher_file                     file path to dispatchers list
    infrastructure_file                 file path to infrastructure description
                                        (contains package names, service names
                                        and their configuration)
    submissions_output_file             file path to output `dispatcher name`,`submission ID` pairs

Options:
    --jar <URL>                         hosted JAR URL
    --num-producers-per-dispatcher <n>  number of producers per dispatcher to create [default: 1]
    --num-consumers-per-producer <n>    number of consumers for producer to create [default: 1]
    --producer-number-of-words <n>      number of total words published by producers [default: 1]
    --producer-words-per-second <n>     number of words per second published by producers [default: 1]
    --producer-spark-cores-max <n>      spark.cores.max [default: 2]
    --producer-spark-executor-cores <n> spark.executor.cores [default: 2]
    --consumer-batch-size-seconds <n>   number seconds accumulating entries for each batch request [default: 10]
    --consumer-write-to-cassandra       write to Cassandra [default: False]
    --consumer-spark-cores-max <n>      spark.cores.max [default: 1]
    --consumer-spark-executor-cores <n> spark.executor.cores [default: 1]
"""


import logging
import json

from docopt import docopt

import sdk_cmd
import spark_utils

log = logging.getLogger(__name__)


DEFAULT_JAR = 'http://infinity-artifacts.s3.amazonaws.com/scale-tests/dcos-spark-scala-tests-assembly-20180523-fa29ab5.jar'
PRODUCER_CLASS_NAME = 'KafkaRandomFeeder'
CONSUMER_CLASS_NAME = 'KafkaWordCount'
SPARK_PACKAGE_NAME = 'spark'
COMMON_CONF = [
    "--supervise",
    "--conf", "spark.mesos.containerizer=mesos",
    "--conf", "spark.mesos.driver.failoverTimeout=30",
    "--conf", "spark.port.maxRetries=32",
    "--conf", "spark.mesos.executor.docker.image=mesosphere/spark-dev:7081f3483a0d904992994edbed07abbc5110f003-815904ac6c6604ac82368a44d69f8a7423bcb8dc",
    "--conf", "spark.mesos.executor.home=/opt/spark/dist",
    "--conf", "spark.scheduler.maxRegisteredResourcesWaitingTime=2400s",
    "--conf", "spark.scheduler.minRegisteredResourcesRatio=1.0"
]


def _install_package_cli(package_name):
    cmd = "package install {package_name} --yes --cli".format(package_name=package_name)
    rt, stdout, _ = sdk_cmd.run_raw_cli(cmd)
    assert rt == 0, "Failed to install CLI for {package_name}"


def _service_endpoint_dns(package_name, service_name, endpoint_name):
    cmd = "{package_name} --name={service_name} endpoints {endpoint_name}".format(
        package_name=package_name,
        service_name=service_name,
        endpoint_name=endpoint_name)
    rt, stdout, _ = sdk_cmd.run_raw_cli(cmd)
    assert rt == 0, "Failed to get {endpoint_name} endpoints"
    return json.loads(stdout)["dns"]


def _submit_producer(kafka_broker_dns,
                     app_name,
                     driver_role,
                     kafka_topics,
                     number_of_words,
                     words_per_second,
                     spark_cores_max,
                     spark_executor_cores):
    app_args = ["--appName",        PRODUCER_CLASS_NAME,
                "--brokers",        ",".join(kafka_broker_dns),
                "--topics",         kafka_topics,
                "--numberOfWords",  str(number_of_words),
                "--wordsPerSecond", str(words_per_second)]

    app_config = ["--conf",  "spark.cores.max={}".format(spark_cores_max),
                  "--conf",  "spark.executor.cores={}".format(spark_executor_cores),
                  "--class", PRODUCER_CLASS_NAME]

    args = app_config + COMMON_CONF

    submission_id = spark_utils.submit_job(
        app_url=jar,
        app_args=" ".join(str(a) for a in app_args),
        app_name=app_name,
        args=args,
        driver_role=driver_role,
        verbose=False)

    return submission_id


def _submit_consumer(kafka_broker_dns,
                     cassandra_native_client_dns,
                     app_name,
                     driver_role,
                     kafka_topics,
                     kafka_group_id,
                     write_to_cassandra,
                     batch_size_seconds,
                     cassandra_keyspace,
                     cassandra_table,
                     spark_cores_max,
                     spark_executor_cores):
    app_args = ["--appName",           CONSUMER_CLASS_NAME,
                "--brokers",           ",".join(kafka_broker_dns),
                "--topics",            kafka_topics,
                "--groupId",           kafka_group_id,
                "--batchSizeSeconds",  str(batch_size_seconds),
                "--cassandraKeyspace", cassandra_keyspace,
                "--cassandraTable",    cassandra_table]

    if not write_to_cassandra:
        app_args.extend(["--shouldNotWriteToCassandra"])

    cassandra_hosts = map(lambda x: x.split(':')[0], cassandra_native_client_dns)
    cassandra_port = cassandra_native_client_dns[0].split(':')[1]

    app_config = ["--conf",  "spark.cores.max={}".format(spark_cores_max),
                  "--conf",  "spark.executor.cores={}".format(spark_executor_cores),
                  "--conf",  "spark.cassandra.connection.host={}".format(",".join(cassandra_hosts)),
                  "--conf",  "spark.cassandra.connection.port={}".format(cassandra_port),
                  "--class", CONSUMER_CLASS_NAME]

    args = app_config + COMMON_CONF

    submission_id = spark_utils.submit_job(
        app_url=jar,
        app_args=" ".join(str(a) for a in app_args),
        app_name=app_name,
        args=args,
        driver_role=driver_role,
        verbose=False)

    return submission_id


def append_submission(output_file: str, dispatcher_app_name: str, submission_id: str):
    with open(output_file, "a") as f:
        f.write("{},{}\n".format(dispatcher_app_name, submission_id))


if __name__ == "__main__":
    args = docopt(__doc__)

    with open(args["<dispatcher_file>"]) as f:
        dispatchers = f.read().splitlines()

    with open(args["<infrastructure_file>"]) as f:
        infrastructure = json.loads(f.read())
        # We might make this script handle multiple Zookeeper/Kafka/Cassandra
        # clusters in the future. For now it only handles a single cluster of
        # each service.
        zookeeper = infrastructure['zookeeper'][0]
        kafka = infrastructure['kafka'][0]
        cassandra = infrastructure['cassandra'][0]

    jar                           = args["--jar"] if args["--jar"] else DEFAULT_JAR
    submissions_output_file       = args["<submissions_output_file>"]
    kafka_package_name            = kafka['package_name']
    kafka_service_name            = kafka['service']['name']
    kafka_num_brokers             = kafka['brokers']['count']
    cassandra_package_name        = cassandra['package_name']
    cassandra_service_name        = cassandra['service']['name']
    cassandra_num_nodes           = cassandra['nodes']['count']
    num_producers_per_dispatcher  = int(args['--num-producers-per-dispatcher'])
    num_consumers_per_producer    = int(args['--num-consumers-per-producer'])
    producer_number_of_words      = int(args['--producer-number-of-words'])
    producer_words_per_second     = int(args['--producer-words-per-second'])
    producer_spark_cores_max      = int(args['--producer-spark-cores-max'])
    producer_spark_executor_cores = int(args['--producer-spark-executor-cores'])
    consumer_write_to_cassandra   = args['--consumer-write-to-cassandra']
    consumer_batch_size_seconds   = int(args['--consumer-batch-size-seconds'])
    consumer_spark_cores_max      = int(args['--consumer-spark-cores-max'])
    consumer_spark_executor_cores = int(args['--consumer-spark-executor-cores'])

    log.info("Dispatchers: \n{}".format("\n".join(dispatchers)))

    _install_package_cli(kafka_package_name)
    _install_package_cli(cassandra_package_name)
    _install_package_cli(SPARK_PACKAGE_NAME)

    kafka_broker_dns = _service_endpoint_dns(kafka_package_name, kafka_service_name, "broker")
    cassandra_native_client_dns = _service_endpoint_dns(cassandra_package_name, cassandra_service_name, "native-client")

    for dispatcher in dispatchers:
        dispatcher_app_name, _, driver_role = dispatcher.split(",")

        for producer_idx in range(0, num_producers_per_dispatcher):
            producer_name = '{}-{}'.format(dispatcher_app_name.replace("/", "__"),
                                           producer_idx)
            # TODO: make sure Kafka topic exists?
            kafka_topics = producer_name
            producer_cassandra_keyspace = producer_name.replace('-', '_')

            producer_submission_id = _submit_producer(
                kafka_broker_dns,
                dispatcher_app_name,
                driver_role,
                kafka_topics,
                producer_number_of_words,
                producer_words_per_second,
                producer_spark_cores_max,
                producer_spark_executor_cores)

            append_submission(
                submissions_output_file,
                dispatcher_app_name,
                producer_submission_id)

            for consumer_idx in range(0, num_consumers_per_producer):
                consumer_name = '{}-{}'.format(producer_name, consumer_idx)
                consumer_kafka_group_id = consumer_name
                consumer_cassandra_table = 'table_{}'.format(consumer_idx)

                consumer_submission_id = _submit_consumer(
                    kafka_broker_dns,
                    cassandra_native_client_dns,
                    dispatcher_app_name,
                    driver_role,
                    kafka_topics,
                    consumer_kafka_group_id,
                    consumer_write_to_cassandra,
                    consumer_batch_size_seconds,
                    producer_cassandra_keyspace,
                    consumer_cassandra_table,
                    consumer_spark_cores_max,
                    consumer_spark_executor_cores)

                append_submission(
                    submissions_output_file,
                    dispatcher_app_name,
                    consumer_submission_id)
