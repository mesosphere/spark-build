#!/usr/bin/env python3

"""
kafka_cassandra_streaming_test.py

Usage:
    ./kafka_cassandra_streaming_test.py <dispatcher_file> [options]

Arguments:
    dispatcher_file                   file path to dispatchers list

Options:
    --jar <URL>                         hosted JAR URL
    --kafka-package-name <name>         name of Kafka package [default: kafka]
    --kafka-service-name <name>         name of Kafka service [default: kafka-spark-cassandra/kafka]
    --kafka-num-brokers <n>             number of Kafka brokers [default: 5]
    --cassandra-package-name <name>     name of Cassandra package [default: cassandra]
    --cassandra-service-name <name>     name of Cassandra service [default: kafka-spark-cassandra/cassandra]
    --cassandra-num-nodes <n>           number of Cassandra nodes [default: 5]
    --num-producers <n>                 number of producers to create [default: 1]
    --num-consumers-per-producer <n>    number of consumers to create for each producer [default: 1]
    --producer-spark-cores-max <n>      spark.cores.max [default: 2]
    --producer-spark-executor-cores <n> spark.executor.cores [default: 2]
    --producer-words-per-second <n>     number words per second published by producers [default: 1]
    --consumer-batch-size-seconds <n>   number seconds accumulating entries for each batch request [default: 10]
    --consumer-spark-cores-max <n>      spark.cores.max [default: 1]
    --consumer-spark-executor-cores <n> spark.executor.cores [default: 1]
"""


import logging
import json

from docopt import docopt

import sdk_cmd
import spark_utils

log = logging.getLogger(__name__)


DEFAULT_JAR = 'https://infinity-artifacts.s3.amazonaws.com/soak/spark/dcos-spark-scala-tests-assembly-0.2-SNAPSHOT.jar'
PRODUCER_CLASS_NAME = 'KafkaRandomFeeder'
CONSUMER_CLASS_NAME = 'KafkaWordCount'
COMMON_CONF = [
    "--supervise",
    "--conf", "spark.mesos.containerizer=mesos",
    "--conf", "spark.mesos.driver.failoverTimeout=30",
    "--conf", "spark.port.maxRetries=32",
    "--conf", "spark.mesos.executor.docker.image=mesosphere/spark:latest",
    "--conf", "spark.mesos.executor.home=/opt/spark/dist",
    "--conf", "spark.scheduler.maxRegisteredResourcesWaitingTime=2400s",
    "--conf", "spark.scheduler.minRegisteredResourcesRatio=1.0"
]


def _service_endpoint_dns(package_name, service_name, endpoint_name):
    cmd = "{package_name} --name={service_name} endpoints {endpoint_name}".format(
        package_name=package_name,
        service_name=service_name,
        endpoint_name=endpoint_name)
    rt, stdout, _ = sdk_cmd.run_raw_cli(cmd)
    assert rt == 0, "Failed to get {endpoint_name} endpoints"
    return json.loads(stdout)["dns"]


def _submit_producer(kafka_broker_dns,
                     common_conf,
                     app_name,
                     driver_role,
                     kafka_topics,
                     words_per_second,
                     spark_cores_max,
                     spark_executor_cores):
    app_args = ["--topics",         kafka_topics,
                "--wordsPerSecond", str(words_per_second),
                "--brokers",        ",".join(kafka_broker_dns),
                "--appName",        PRODUCER_CLASS_NAME]

    app_config = ["--conf",  "spark.cores.max={}".format(spark_cores_max),
                  "--conf",  "spark.executor.cores={}".format(spark_executor_cores),
                  "--class", PRODUCER_CLASS_NAME]

    args = app_config + common_conf

    spark_utils.submit_job(app_url=jar,
                           app_args=" ".join(app_args),
                           app_name=app_name,
                           args=args,
                           driver_role=driver_role,
                           verbose=False)


def _submit_consumer(kafka_broker_dns,
                     cassandra_native_client_dns,
                     common_conf,
                     app_name,
                     driver_role,
                     kafka_topics,
                     batch_size_seconds,
                     spark_cores_max,
                     spark_executor_cores):
    app_args = ["--topics",           kafka_topics,
                "--batchSizeSeconds", str(batch_size_seconds),
                "--brokers",          ",".join(kafka_broker_dns),
                "--appName",          CONSUMER_CLASS_NAME]

    cassandra_hosts = map(lambda x: x.split(':')[0], cassandra_native_client_dns)
    cassandra_port = cassandra_native_client_dns[0].split(':')[1]

    app_config = ["--conf",  "spark.cores.max={}".format(spark_cores_max),
                  "--conf",  "spark.executor.cores={}".format(spark_executor_cores),
                  "--conf",  "spark.cassandra.connection.host={}".format(",".join(cassandra_hosts)),
                  "--conf",  "spark.cassandra.connection.port={}".format(cassandra_port),
                  "--class", CONSUMER_CLASS_NAME]

    args = app_config + common_conf

    spark_utils.submit_job(app_url=jar,
                           app_args=" ".join(app_args),
                           app_name=app_name,
                           args=args,
                           driver_role=driver_role,
                           verbose=False)


if __name__ == "__main__":
    args = docopt(__doc__)

    jar                           = args['--jar']
    kafka_package_name            = args['--kafka-package-name']
    kafka_service_name            = args['--kafka-service-name']
    kafka_num_brokers             = int(args['--kafka-num-brokers'])
    cassandra_package_name        = args['--cassandra-package-name']
    cassandra_service_name        = args['--cassandra-service-name']
    cassandra_num_nodes           = int(args['--cassandra-num-nodes'])
    num_producers                 = int(args['--num-producers'])
    num_consumers_per_producer    = int(args['--num-consumers-per-producer'])
    producer_words_per_second     = int(args['--producer-words-per-second'])
    producer_spark_cores_max      = int(args['--producer-spark-cores-max'])
    producer_spark_executor_cores = int(args['--producer-spark-executor-cores'])
    consumer_batch_size_seconds   = int(args['--consumer-batch-size-seconds'])
    consumer_spark_cores_max      = int(args['--consumer-spark-cores-max'])
    consumer_spark_executor_cores = int(args['--consumer-spark-executor-cores'])

    with open(args["<dispatcher_file>"]) as f:
        dispatchers = f.read().splitlines()

    log.info("Dispatchers: \n{}".format("\n".join(dispatchers)))

    # TODO: make sure Kafka is installed and is running kafka_num_broker tasks.
    # TODO: make sure Cassandra is installed and is running cassandra_num_nodes tasks.

    jar = args["--jar"] if args["--jar"] else DEFAULT_JAR

    kafka_broker_dns = _service_endpoint_dns(kafka_package_name, kafka_service_name, "broker")
    cassandra_native_client_dns = _service_endpoint_dns(cassandra_package_name, cassandra_service_name, "native-client")

    for dispatcher in dispatchers:
        dispatcher_app_name, _, driver_role = dispatcher.split(",")
        # TODO: make sure Kafka topic exists.
        kafka_topics = "topic-{}".format(dispatcher_app_name.replace("/", "__"))

        _submit_producer(
            kafka_broker_dns,
            COMMON_CONF,
            dispatcher_app_name,
            driver_role,
            kafka_topics,
            producer_words_per_second,
            producer_spark_cores_max,
            producer_spark_executor_cores)

        for _ in range(0, num_consumers_per_producer):
            _submit_consumer(
                kafka_broker_dns,
                cassandra_native_client_dns,
                COMMON_CONF,
                dispatcher_app_name,
                driver_role,
                kafka_topics,
                consumer_batch_size_seconds,
                consumer_spark_cores_max,
                consumer_spark_executor_cores)
