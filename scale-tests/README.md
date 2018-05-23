# Spark Scale Tests

## Batch
[To be filled in]

## Streaming

Cluster requirements:
- Enough resources to run the workload given the parameters.
- Package repository containing a version of Spark with quotas.

### 0. Getting a shell session that's able to run the scripts

```bash
your-machine $ git clone git@github.com:mesosphere/spark-build.git
your-machine $ cd spark-build
your-machine $ docker run -it --net=host -v (pwd):/spark-build -v </path/to/soak/key>:/ssh/key mesosphere/spark-build:latest
docker-container # cd /spark-build
docker-container # pip3 install -r tests/requirements.txt
docker-container # export PYTHONPATH=$(pwd)/testing:$(pwd)/spark-testing
docker-container # dcos cluster setup --insecure --username=<username> --password=<password> <cluster-url>
docker-container # eval "$(ssh-agent)"
docker-container # ssh-add -k /ssh/key
```

For the next sections, tweak variables as required.

### 1. Set up infrastructure (Kafka, Zookeeper and Cassandra clusters)

In order to install the infrastructure for the streaming tests, the
`setup_streaming.py` script can be used.

For example, the following command:

```bash
TEST_NAME=dispatcher-streaming
INFRASTRUCTURE_OUTPUT_FILE="${TEST_NAME}-infrastructure.json"
KAFKA_ZOOKEEPER_CONFIG=scale-tests/configs/kafka-zookeeper-options.json
KAFKA_CLUSTER_COUNT=1
KAFKA_CONFIG=scale-tests/configs/kafka-options.json
CASSANDRA_CLUSTER_COUNT=1
CASSANDRA_CONFIG=scale-tests/configs/cassandra-options.json

./scale-tests/setup_streaming.py $INFRASTRUCTURE_OUTPUT_FILE \
  --kafka-zookeeper-config $KAFKA_ZOOKEEPER_CONFIG \
  --kafka-cluster-count $KAFKA_CLUSTER_COUNT \
  --kafka-config $KAFKA_CONFIG \
  --cassandra-cluster-count $CASSANDRA_CLUSTER_COUNT \
  --cassandra-config $CASSANDRA_CONFIG
```

installs:
* 1 Confluent ZooKeeper ensemble with the specified options
* 1 Confluent Kafka ensemble with the `kafka.kafka_zookeeper_uri` set up for the
  Confluent ZooKeeper ensemble and specified options
* 1 Cassandra cluster with the specified options

The specifications (package names and service names) for the installed services
are written to the specified output file: `$INFRASTRUCTURE_OUTPUT_FILE`.

Check the `setup_streaming.py` script for more customization options.

*TODO*: maybe make the installed service names have `$TEST_NAME` as a prefix so
all related tasks are grouped visually. Right now this installs services as e.g.
`cassandra-00`, but it would be cool if it was `$TEST_NAME/cassandra-00`, e.g.
`dispatcher-streaming/cassandra-00`.

### 2. Install Spark dispatchers

Depends on:
- `$TEST_NAME` exported in step #1.

Wait for the infrastructure to come online and run the following command:

```bash
QUOTA_DISPATCHER_CPUS=8
QUOTA_DISPATCHER_MEM=8096
QUOTA_DRIVER_CPUS=10
QUOTA_DRIVER_MEM=8096
NUM_DISPATCHERS=10
DISPATCHER_NAME_PREFIX="${TEST_NAME}"
DISPATCHERS_OUTPUT_FILE="${DISPATCHER_NAME_PREFIX}-dispatchers.out"

./scale-tests/deploy-dispatchers.py \
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
JAR=http://infinity-artifacts.s3.amazonaws.com/autodelete7d/dcos-spark-scala-tests-assembly-kafka-cassandra-streaming-20180517.jar
NUM_PRODUCERS_PER_DISPATCHER=1
NUM_CONSUMERS_PER_PRODUCER=1
PRODUCER_NUMBER_OF_WORDS=100000
PRODUCER_WORDS_PER_SECOND=10
PRODUCER_SPARK_CORES_MAX=2
PRODUCER_SPARK_EXECUTOR_CORES=2
CONSUMER_BATCH_SIZE_SECONDS=10
CONSUMER_SPARK_CORES_MAX=1
CONSUMER_SPARK_EXECUTOR_CORES=1

./scale-tests/kafka_cassandra_streaming_test.py \
  $DISPATCHERS_OUTPUT_FILE \
  $INFRASTRUCTURE_OUTPUT_FILE \
  --jar $JAR \
  --num-producers-per-dispatcher $NUM_PRODUCERS_PER_DISPATCHER \
  --num-consumers-per-producer $NUM_CONSUMERS_PER_PRODUCER \
  --producer-number-of-words $PRODUCER_NUMBER_OF_WORDS \
  --producer-words-per-second $PRODUCER_WORDS_PER_SECOND \
  --producer-spark-cores-max $PRODUCER_SPARK_CORES_MAX \
  --producer-spark-executor-cores $PRODUCER_SPARK_EXECUTOR_CORES \
  --consumer-write-to-cassandra \
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
dcos task exec -it node-0-server bash -c 'CQLSH=$(ls -d ./apache-cassandra-*/bin/cqlsh) && $CQLSH node-0-server.cassandra-00.autoip.dcos.thisdcos.directory 9042 -e "describe tables"'
```

```
dcos task exec -it node-0-server bash -c 'CQLSH=$(ls -d ./apache-cassandra-*/bin/cqlsh) && $CQLSH node-0-server.cassandra-00.autoip.dcos.thisdcos.directory 9042 -e "select count(*) from dispatcher_mixed_0_0.table_0"'
```

```
dcos task exec -it node-0-server bash -c 'CQLSH=$(ls -d ./apache-cassandra-*/bin/cqlsh) && $CQLSH node-0-server.cassandra-00.autoip.dcos.thisdcos.directory 9042 -e "select * from dispatcher_mixed_0_0.table_0 limit 10"'
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

Also, make sure you `export DCOS_SSH_USER=core` if you run a coreos-based cluster.

```bash
SPARK_PRINCIPAL=spark-principal

./scale-tests/uninstall-dispatchers.sh $DISPATCHERS_OUTPUT_FILE $SPARK_PRINCIPAL
```

### 6. (Optional) Tear down infrastructure (Kafka, Zookeeper and Cassandra clusters)

The services can be uninstalled manually as with any other DC/OS services, but running:

```bash
export PYTHONPATH=../testing:../spark-testing

./setup_streaming.py $INFRASTRUCTURE_OUTPUT_FILE --cleanup
```

will remove the services defined in the `$INFRASTRUCTURE_OUTPUT_FILE` JSON file
generated by the set up step (#1).
