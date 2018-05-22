#!/usr/bin/env python3

"""streaming_test.py

Usage:
    streaming_test.py <dispatcher_file> [options]

Arguments:
    dispatcher_file             file path to dispatchers list

Options:
    --desired-runtime <n>        desired time for consumers to run (in minutes) [default: 10]
    --port-retries <n>           max number of retries for Spark to bind to a port [default: 16]
    --jar <url>                  url path to hosted jar
    --kafka-package-name <name>  name of Kafka package [default: kafka]
    --kafka-service-name <name>  name of Kafka service [default: kafka]
    --kerberos-flag <bool>       is Kerberos enabled? [default: false]
    --num-consumers <n>          number of consumers to create for each producer [default: 1]
"""


import logging
import json

import sdk_cmd
import spark_utils

from docopt import docopt

log = logging.getLogger(__name__)
PRODUCER_NUM_WORDS_PER_MIN = 480


def main(dispatchers, jar_url, kafka_pkg_name, kafka_svc_name, num_consumers, desired_runtime, kerberos_flag,
         port_retries):

    def _kafka_broker_dns():
        cmd = "{package_name} --name={service_name} endpoints broker".format(
            package_name=kafka_pkg_name,
            service_name=kafka_svc_name)
        rt, stdout, _ = sdk_cmd.run_raw_cli(cmd)
        assert rt == 0, "Failed to get broker endpoints"
        return ",".join(json.loads(stdout)["dns"])

    def _submit_producer(broker_dns, common_conf, topic, spark_app_name, driver_role):
        big_file = "file:///mnt/mesos/sandbox/big.txt"

        producer_args = " ".join([broker_dns, big_file, topic, kerberos_flag])

        producer_config = ["--conf", "spark.cores.max=2",
                           "--conf", "spark.executor.cores=2",
                           "--class", "KafkaFeeder"] + common_conf

        spark_utils.submit_job(app_url=jar_url,
                               app_args=producer_args,
                               app_name=spark_app_name,
                               args=producer_config,
                               driver_role=driver_role,
                               verbose=False)

    def _submit_consumer(broker_dns, common_conf, topic, spark_app_name, driver_role, num_words):
        consumer_args = " ".join([broker_dns, topic, num_words, kerberos_flag])

        consumer_config = ["--conf", "spark.cores.max=4",
                           "--class", "KafkaConsumer"] + common_conf

        spark_utils.submit_job(app_url=jar_url,
                               app_args=consumer_args,
                               app_name=spark_app_name,
                               args=consumer_config,
                               driver_role=driver_role,
                               verbose=False)

    common_conf = [
        "--supervise",
        "--conf", "spark.mesos.containerizer=mesos",
        "--conf", "spark.mesos.driver.failoverTimeout=30",
        "--conf", "spark.mesos.uris=http://norvig.com/big.txt",
        "--conf", "spark.port.maxRetries={}".format(port_retries),
        "--conf", "spark.scheduler.maxRegisteredResourcesWaitingTime=2400s",
        "--conf", "spark.scheduler.minRegisteredResourcesRatio=1.0"
    ]

    broker_dns = _kafka_broker_dns()
    num_words_to_read = int(desired_runtime * PRODUCER_NUM_WORDS_PER_MIN)

    for dispatcher in dispatchers:
        spark_app_name, _, driver_role = dispatcher.split(",")
        topic = "topic-{}".format(spark_app_name)

        _submit_producer(broker_dns, common_conf, topic, spark_app_name, driver_role)

        for _ in range(0, num_consumers):
            _submit_consumer(broker_dns, common_conf, topic, spark_app_name, driver_role, str(num_words_to_read))


if __name__ == "__main__":
    args = docopt(__doc__)

    with open(args["<dispatcher_file>"]) as f:
        dispatchers = f.read().splitlines()
    log.info("dispatchers: {}".format(dispatchers))

    log.info("Installing kafka CLI...")
    kafka_pkg_name = args["--kafka-package-name"]
    sdk_cmd.run_raw_cli("package install {} --yes --cli".format(kafka_pkg_name))

    jar_url = args["--jar"] if args["--jar"] else "https://s3-us-west-2.amazonaws.com/infinity-artifacts/soak/spark/dcos-spark-scala-tests-assembly-0.2-SNAPSHOT.jar"

    main(dispatchers=dispatchers,
         jar_url=jar_url,
         kafka_pkg_name=kafka_pkg_name,
         kafka_svc_name=args["--kafka-service-name"],
         num_consumers=int(args["--num-consumers"]),
         desired_runtime=int(args["--desired-runtime"]),
         kerberos_flag=args["--kerberos-flag"],
         port_retries=args["--port-retries"])
