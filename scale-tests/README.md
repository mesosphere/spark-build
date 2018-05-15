# Spark Scale Tests

## Batch
[To be filled in]

## Streaming

Tweak variables as required.

### 1. Set up infrastructure (Kafka, Zookeeper and Cassandra clusters)

In order to install the infrastructure for the streaming tests, the
`setup_streaming.py` script can be used.

For example, the following command:

```bash
PYTHONPATH=../testing:../spark-testing

INFRASTRUCTURE_OUTPUT_FILE=service-options.json
KAFKA_ZOOKEEPER_CONFIG=configs/kafka-zookeeper-options.json
KAFKA_CLUSTER_COUNT=1
KAFKA_CONFIG=configs/kafka-options.json
CASSANDRA_CLUSTER_COUNT=1
CASSANDRA_CONFIG=configs/cassandra-options.json

./setup_streaming.py $INFRASTRUCTURE_OUTPUT_FILE \
  --kafka-zookeeper-config $KAFKA_ZOOKEEPER_CONFIG \
  --kafka-cluster-count $KAFKA_CLUSTER_COUNT \
  --kafka-config $KAFKA_CONFIG \
  --cassandra-cluster-count $CASSANDRA_CLUSTER_COUNT \
  --cassandra-config $CASSANDRA_CONFIG
```

installs:
* 1 Confluent ZooKeeper ensemble with the specified options
* 1 Confluent Kafka ensemble with the `kafka.kafka_zookeeper_uri` set up for the Confluent ZooKeeper ensemble and specified options
* 1 Cassandra cluster with the specified options

The specifications (package names and service names) for the installed services
are written to the specified output file: `$INFRASTRUCTURE_OUTPUT_FILE`.

Check the `setup_streaming.py` script for more customization options.

*TODO*: maybe make the installed service names have `$DISPATCHER_NAME_PREFIX` as a
prefix so all related tasks are grouped visually. Right now this installs
services as e.g. `cassandra-00`, but it would be cool if it was something like
`$DISPATCHER_NAME_PREFIX-cassandra-00`, e.g. `dispatcher-streaming-cassandra-00`.

### 2. Install Spark dispatchers

```bash
PYTHONPATH=../testing:../spark-testing

QUOTA_DISPATCHER_CPUS=8
QUOTA_DISPATCHER_MEM=8096
QUOTA_DRIVER_CPUS=10
QUOTA_DRIVER_MEM=8096
NUM_DISPATCHERS=1
DISPATCHER_NAME_PREFIX=dispatcher-streaming
DISPATCHERS_OUTPUT_FILE="${DISPATCHER_NAME_PREFIX}-dispatchers.out"

python3 deploy-dispatchers.py \
  --quota-dispatcher-cpus $QUOTA_DISPATCHER_CPUS \
  --quota-dispatcher-mem $QUOTA_DISPATCHER_MEM \
  --quota-driver-cpus $QUOTA_DRIVER_CPUS \
  --quota-driver-mem $QUOTA_DRIVER_MEM \
  $NUM_DISPATCHERS \
  $DISPATCHER_NAME_PREFIX \
  $DISPATCHERS_OUTPUT_FILE
```

### 3. Run scale test script

Depends on:
- `$INFRASTRUCTURE_OUTPUT_FILE` exported in step #1.
- `$DISPATCHER_NAME_PREFIX` exported in step #2.
- `$DISPATCHER_OUTPUT_FILE` exported in step #2.

Wait for the dispatchers to come online and run the following command:

```bash
PYTHONPATH=../testing:../spark-testing

JAR=http://infinity-artifacts.s3.amazonaws.com/autodelete7d/evan-dcos-spark-scala-tests-assembly-0.2-SNAPSHOT.jar
KAFKA_PACKAGE_NAME=confluent-kafka    # TODO: get from infrastructure output file.
KAFKA_SERVICE_NAME=confluent-kafka-00 # TODO: get from infrastructure output file.
KAFKA_NUM_BROKERS=3                   # TODO: get from running service through infrastructure output file.
CASSANDRA_PACKAGE_NAME=cassandra      # TODO: get from infrastructure output file.
CASSANDRA_SERVICE_NAME=cassandra-00   # TODO: get from infrastructure output file.
CASSANDRA_NUM_NODES=3                 # TODO: get from running service through infrastructure output file.
NUM_PRODUCERS_PER_DISPATCHER=1
NUM_CONSUMERS_PER_PRODUCER=1
PRODUCER_WORDS_PER_SECOND=10
PRODUCER_SPARK_CORES_MAX=2
PRODUCER_SPARK_EXECUTOR_CORES=2
CONSUMER_BATCH_SIZE_SECONDS=10
CONSUMER_SPARK_CORES_MAX=1
CONSUMER_SPARK_EXECUTOR_CORES=1

python3 kafka_cassandra_streaming_test.py $DISPATCHERS_OUTPUT_FILE \
  --jar $JAR \
  --kafka-package-name $KAFKA_PACKAGE_NAME \
  --kafka-service-name $KAFKA_SERVICE_NAME \
  --kafka-num-brokers $KAFKA_NUM_BROKERS \
  --cassandra-package-name $CASSANDRA_PACKAGE_NAME \
  --cassandra-service-name $CASSANDRA_SERVICE_NAME \
  --cassandra-num-nodes $CASSANDRA_NUM_NODES \
  --num-producers $NUM_PRODUCERS_PER_DISPATCHER \
  --num-consumers-per-producer $NUM_CONSUMERS_PER_PRODUCER \
  --producer-words-per-second $PRODUCER_WORDS_PER_SECOND \
  --producer-spark-cores-max $PRODUCER_SPARK_CORES_MAX \
  --producer-spark-executor-cores $PRODUCER_SPARK_EXECUTOR_CORES \
  --consumer-batch-size-seconds $CONSUMER_BATCH_SIZE_SECONDS \
  --consumer-spark-cores-max $CONSUMER_SPARK_CORES_MAX \
  --consumer-spark-executor-cores $CONSUMER_SPARK_EXECUTOR_CORES
```

### 4. Verify scale test correctness

*This is currently being done manually. Going forward it might make sense to add
correctness checking to the scale test scripts themselves.*

A finite scale test (i.e. run with a `--number-of-words` different than zero) is
successful when the total number of words published to Kafka is the same as the
sum of word count records written to Cassandra.

For example, if we published the following `9` words to Kafka:

```
the
quick
brown
fox
jumps
over
the
lazy
dog
```

Cassandra would have to contain the following records for the test to be
considered successful:

*TODO*: handle installed Cassandra service name in URL.

```
dcos task exec -it node-0-server bash -c 'PATH=$MESOS_SANDBOX/python-dist/bin:$PATH && CQLSH=$(ls -d ./apache-cassandra-*/bin/cqlsh) && $CQLSH node-0-server.cassandra-00.autoip.dcos.thisdcos.directory 9042 -e "select * from kafka_cassandra_stream.records"'
```

```
word  | ts                       | count
------+--------------------------+-------
the   | 2018-01-01 00:00:00+0000 |     2
quick | 2018-01-01 00:00:00+0000 |     1
brown | 2018-01-01 00:00:00+0000 |     1
fox   | 2018-01-01 00:00:00+0000 |     1
jumps | 2018-01-01 00:00:00+0000 |     1
over  | 2018-01-01 00:00:00+0000 |     1
lazy  | 2018-01-01 00:00:00+0000 |     1
dog   | 2018-01-01 00:00:00+0000 |     1
```

### 5. (Optional) Tear down Spark dispatchers

Depends on:
- `$DISPATCHER_OUTPUT_FILE` exported in step #2.

```bash
SPARK_PRINCIPAL=spark-principal

./uninstall-dispatchers.sh $DISPATCHERS_OUTPUT_FILE $SPARK_PRINCIPAL
```

### 6. (Optional) Tear down infrastructure (Kafka, Zookeeper and Cassandra clusters)

The services can be uninstalled manually as with any other DC/OS services, but running:

```bash
PYTHONPATH=../testing:../spark-testing

./setup_streaming.py $INFRASTRUCTURE_OUTPUT_FILE --cleanup
```

will remove the services defined in the `$INFRASTRUCTURE_OUTPUT_FILE` JSON file
generated by the set up step (#1).
