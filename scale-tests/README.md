# Spark Scale Tests

## Preparation

### Building and uploading a "tests assembly" JAR

If you want to run a specific JAR you'll need to go through these steps.

1. Generate temporary AWS credentials with [`maws`](https://github.com/mesosphere/maws)

2. Build "tests assembly" JAR

Change the spark-build path as necessary.

```bash
SPARK_BUILD_PATH="${HOME}/mesosphere/spark-build"
cd "${SPARK_BUILD_PATH}"/tests/jobs/scala
sbt assembly
```

This will generate the "tests assembly" JAR at
`${SPARK_BUILD_PATH}/tests/jobs/scala/target/scala-2.11/dcos-spark-scala-tests-assembly-0.2-SNAPSHOT.jar`.

2. Upload "tests assembly" JAR

Change the spark-build path as necessary and fill in the AWS credentials found
in `${HOME}/.aws/credentials`, then run the following command:

```bash
S3_BUCKET=infinity-artifacts
S3_FOLDER=scale-tests
SPARK_BUILD_PATH="${HOME}/mesosphere/spark-build"
JAR_LOCAL_PATH="${SPARK_BUILD_PATH}/tests/jobs/scala/target/scala-2.11/dcos-spark-scala-tests-assembly-0.2-SNAPSHOT.jar"
JAR_NAME="dcos-spark-scala-tests-assembly-$(date +%Y%m%d)-$(git rev-parse --short HEAD).jar"

aws s3 cp --acl public-read \
  "${JAR_LOCAL_PATH}" \
  "s3://${S3_BUCKET}/${S3_FOLDER}/${JAR_NAME}"
```

This will upload the "tests assembly" JAR to S3 and output its public object URL.

## Running Tests

Cluster requirements:
- Enough resources to run the workload given the parameters.
- Package repository containing a version of Spark with quotas. Here are instructions for a permanent one:
```bash
dcos cluster setup ...
dcos package repo add --index=0 spark-quotas https://universe-converter.mesosphere.com/transform?url=https://infinity-artifacts.s3.amazonaws.com/permanent/spark/assets/scale-testing/stub-universe-spark.json
```

### Getting a shell session that's able to run the scripts

```bash
your-machine $ git clone git@github.com:mesosphere/spark-build.git
your-machine $ cd spark-build
your-machine $ docker build -t mesosphere/dcos-commons:${LOGNAME}-spark scale-tests/
your-machine $ SOAK_KEY=</path/to/soak/key>
your-machine $ docker run -it --net=host -v $(pwd):/spark-build -v $SOAK_KEY:/ssh/key:ro mesosphere/dcos-commons:${LOGNAME}-spark
docker-container # dcos cluster setup --insecure --username=<username> --password=<password> <cluster-url>
docker-container # eval "$(ssh-agent)"
docker-container # ssh-add -k /ssh/key
```

### Batch

#### 1. Install Spark dispatchers

*Note*: If the tests are to be run against a strict mode cluster, ensure that the
`SECURITY` environment variable is set accordingly:
```bash
export SECURITY="strict"
```

For the next sections, tweak variables as required.

Run the following command:

```bash
TEST_NAME=spark-test
QUOTA_DRIVERS_CPUS=4
QUOTA_DRIVERS_MEM=8192
QUOTA_EXECUTORS_CPUS=4
QUOTA_EXECUTORS_MEM=8192
NUM_DISPATCHERS=1
DISPATCHER_NAME_PREFIX="${TEST_NAME}"
DISPATCHERS_OUTPUT_FILE="${DISPATCHER_NAME_PREFIX}-dispatchers.out"
DISPATCHERS_JSON_FILE="${DISPATCHERS_OUTPUT_FILE}-dispatchers.json"

./scale-tests/deploy-dispatchers.py \
  --quota-drivers-cpus $QUOTA_DRIVERS_CPUS \
  --quota-drivers-mem $QUOTA_DRIVERS_MEM \
  --quota-executors-cpus $QUOTA_EXECUTORS_CPUS \
  --quota-executors-mem $QUOTA_EXECUTORS_MEM \
  $NUM_DISPATCHERS \
  $DISPATCHER_NAME_PREFIX \
  $DISPATCHERS_OUTPUT_FILE
```

#### 2. Launch batch jobs from the command line

Wait for Spark Dispatchers to install.

Launch batch jobs from the command line:

```bash
SUBMITS_PER_MIN=1

./scale-tests/batch_test.py \
  $DISPATCHERS_JSON_FILE \
  --submits-per-min $SUBMITS_PER_MIN
```

#### 3. Alternatively, deploy a Marathon app which launches batch jobs from within the cluster [optional]

First, upload the DISPATCHERS_JSON_FILE created above somewhere that is accessible from the cluster -
S3, for example.

To upload to S3, run the following *outside* the container:

1. Change into the spark-build path.

2. Run the following command, filling in a value for the S3_BUCKET and setting the DISPATCHERS_JSON_FILE
to the same value as in the container:

```bash
S3_BUCKET=<bucket>
S3_FOLDER=scale-tests
DISPATCHERS_JSON_FILE=<json_file>

aws s3 cp --acl public-read \
  "${DISPATCHERS_JSON_FILE}" \
  "s3://${S3_BUCKET}/${S3_FOLDER}/${DISPATCHERS_JSON_FILE}"
```

Then run the following, filling in values for username, password, and S3 bucket:

```bash
DCOS_USERNAME=<username>
DCOS_PASSWORD=<password>
S3_BUCKET=<bucket>
S3_FOLDER=scale-tests
DISPATCHERS_JSON_FILE_URL="https://${S3_BUCKET}.s3.amazonaws.com/${S3_FOLDER}/${DISPATCHERS_JSON_FILE}"
BATCH_APP_ID="${TEST_NAME}-batch-workload"
SCRIPT_CPUS=2
SCRIPT_MEM=4096
SUBMITS_PER_MIN=1
SECURITY=permissive

./scale-tests/deploy-batch-marathon-app.py \
  --app-id $BATCH_APP_ID \
  --dcos-username $DCOS_USERNAME \
  --dcos-password $DCOS_PASSWORD \
  --security $SECURITY \
  --input-file-uri $DISPATCHERS_JSON_FILE_URL \
  --script-cpus $SCRIPT_CPUS \
  --script-mem $SCRIPT_MEM \
  --script-args "${DISPATCHERS_JSON_FILE} --submits-per-min ${SUBMITS_PER_MIN}"
```

### Streaming

For the next sections, tweak variables as required.

#### 1. Set up infrastructure (Kafka, Zookeeper and Cassandra clusters)

In order to install the infrastructure for the streaming tests, the
`setup_streaming.py` script can be used.

*Note*: If the tests are to be run against a strict mode cluster, ensure that the
`SECURITY` environment variable is set accordingly:
```bash
export SECURITY="strict"
```

For example, the following command:

```bash
TEST_NAME=dispatcher-streaming
SERVICE_NAMES_PREFIX="${TEST_NAME}/"
INFRASTRUCTURE_OUTPUT_FILE="${TEST_NAME}-infrastructure.json"
KAFKA_ZOOKEEPER_CONFIG=scale-tests/configs/kafka-zookeeper-options.json
KAFKA_CLUSTER_COUNT=2
KAFKA_CONFIG=scale-tests/configs/kafka-options.json
CASSANDRA_CLUSTER_COUNT=1
CASSANDRA_CONFIG=scale-tests/configs/cassandra-options.json

./scale-tests/setup_streaming.py $INFRASTRUCTURE_OUTPUT_FILE \
  --service-names-prefix $SERVICE_NAMES_PREFIX \
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

#### 2. Install Spark dispatchers

Depends on:
- `$TEST_NAME` exported in step #1.

Wait for the infrastructure to come online and run the following command:

```bash
QUOTA_DRIVERS_CPUS=8
QUOTA_DRIVERS_MEM=8096
QUOTA_EXECUTORS_CPUS=10
QUOTA_EXECUTORS_MEM=8096
NUM_DISPATCHERS=10
DISPATCHER_NAME_PREFIX="${TEST_NAME}"
DISPATCHERS_OUTPUT_FILE="${DISPATCHER_NAME_PREFIX}-dispatchers.out"
DISPATCHERS_JSON_FILE="${DISPATCHERS_OUTPUT_FILE}-dispatchers.json"

./scale-tests/deploy-dispatchers.py \
  --quota-drivers-cpus $QUOTA_DRIVERS_CPUS \
  --quota-drivers-mem $QUOTA_DRIVERS_MEM \
  --quota-executors-cpus $QUOTA_EXECUTORS_CPUS \
  --quota-executors-mem $QUOTA_EXECUTORS_MEM \
  $NUM_DISPATCHERS \
  $DISPATCHER_NAME_PREFIX \
  $DISPATCHERS_OUTPUT_FILE
```

#### 3. Run scale test script

Depends on:
- `$INFRASTRUCTURE_OUTPUT_FILE` exported in step #1.
- `$DISPATCHER_NAME_PREFIX` exported in step #2.
- `$DISPATCHERS_JSON_FILE` exported in step #2.

If you want to run a different JAR make sure to build, upload it and use its public object URL.

Wait for the dispatchers to come online and run the following command:

```bash
JAR=http://infinity-artifacts.s3.amazonaws.com/scale-tests/dcos-spark-scala-tests-assembly-20180612-5fa9420.jar
SUBMISSIONS_OUTPUT_FILE="${DISPATCHER_NAME_PREFIX}-submissions.out"
NUM_PRODUCERS_PER_KAFKA=1
NUM_CONSUMERS_PER_PRODUCER=1
PRODUCER_NUMBER_OF_WORDS=100000
PRODUCER_WORDS_PER_SECOND=10
PRODUCER_SPARK_CORES_MAX=2
PRODUCER_SPARK_EXECUTOR_CORES=2
CONSUMER_BATCH_SIZE_SECONDS=10
CONSUMER_SPARK_CORES_MAX=1
CONSUMER_SPARK_EXECUTOR_CORES=1

./scale-tests/kafka_cassandra_streaming_test.py \
  $DISPATCHERS_JSON_FILE \
  $INFRASTRUCTURE_OUTPUT_FILE \
  $SUBMISSIONS_OUTPUT_FILE \
  --jar $JAR \
  --num-producers-per-kafka $NUM_PRODUCERS_PER_KAFKA \
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

This generates a file with a list of `dispatcher name`-`submission ID` pairs
that can be used to kill started jobs.

#### 4. Verify scale test correctness

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

#### 5. (Optional) Kill jobs

Depends on:
- `$SUBMISSIONS_OUTPUT_FILE` exported in step #4.

```bash
./scale-tests/kill-jobs.sh $SUBMISSIONS_OUTPUT_FILE
```

#### 6. (Optional) Tear down Spark dispatchers

Depends on:
- `$DISPATCHER_OUTPUT_FILE` exported in step #2.

Also, make sure you `export DCOS_SSH_USER=core` if you run a coreos-based cluster.

```bash
SPARK_PRINCIPAL=spark-principal

./scale-tests/uninstall-dispatchers.sh $DISPATCHERS_OUTPUT_FILE $SPARK_PRINCIPAL
```

#### 7. (Optional) Tear down infrastructure (Kafka, Zookeeper and Cassandra clusters)

The services can be uninstalled manually as with any other DC/OS services, but running:

```bash
export PYTHONPATH=../testing:../spark-testing

./setup_streaming.py $INFRASTRUCTURE_OUTPUT_FILE --cleanup
```

will remove the services defined in the `$INFRASTRUCTURE_OUTPUT_FILE` JSON file
generated by the set up step (#1).


## Additional information

### Metrics Agent

The metrics agent may need to be updated to provide additional tags and performance improvements.

First determine the number of agents in the cluster:
```bash
echo "Updating metrics in the cluster..."
agent_count=`dcos node | grep agent | wc -l`
echo "There are $agent_count agents to update metrics on"
```

Set the source for the metrics agent.
```bash
DCOS_METRICS_REPLACEMENT="https://infinity-artifacts.s3.amazonaws.com/dcos-metrics"
```

The following command generates a Marathon app that can be used to replace the `dcos-metrics` agent on each host. Note the use of
the `agent_count` and `DCOS_METRICS_REPLACEMENT` environment variables. A backup of the current metrics agent is made before overwriting it with the downloaded executable.

```bash
cat <<EOF > updater.json
{
  "id": "/metrics-updater",
  "backoffFactor": 1.15,
  "backoffSeconds": 1,
  "cmd": "echo \"backing up metrics agent\"\ncp --backup=numbered /opt/mesosphere/bin/dcos-metrics /opt/mesosphere/bin/dcos-metrics.backup\n\necho \"stopping metrics agent\"\nsystemctl stop dcos-metrics-agent\n\necho \"copying metrics binary into place\"\nchmod +x dcos-metrics\ncp dcos-metrics /opt/mesosphere/bin/dcos-metrics\n\necho \"restarting metrics agent\"\nsystemctl start dcos-metrics-agent\n\necho \"update complete. sleepy.\"\n\nsleep 126000",
  "acceptedResourceRoles": [
    "*",
    "slave_public"
  ],
  "constraints": [
    [
      "hostname",
      "UNIQUE"
    ]
  ],
  "container": {
    "type": "MESOS",
    "volumes": []
  },
  "cpus": 0.1,
  "disk": 0,
  "fetch": [
    {
      "uri": "${DCOS_METRICS_REPLACEMENT}",
      "extract": true,
      "executable": false,
      "cache": false
    }
  ],
  "instances": ${agent_count},
  "maxLaunchDelaySeconds": 3600,
  "mem": 128,
  "gpus": 0,
  "networks": [
    {
      "mode": "host"
    }
  ],
  "portDefinitions": [],
  "requirePorts": false,
  "upgradeStrategy": {
    "maximumOverCapacity": 1,
    "minimumHealthCapacity": 1
  },
  "killSelection": "YOUNGEST_FIRST",
  "unreachableStrategy": {
    "inactiveAfterSeconds": 0,
    "expungeAfterSeconds": 0
  },
  "healthChecks": []
}
EOF
```
We then deploy this as a marathon app:
```bash
echo "Removing previous updater"
dcos marathon app remove /metrics-updater
echo "Installing updater"
dcos marathon app add updater.json
```

Once the deployment has been completed, the app can be removed.
```bash
dcos marathon app remove /metrics-updater
```
(Note that this means that the replacement metrics agent will not be installed if a node has to be rebuilt for some reason)

### Prometheus

#### (optional) Updating dcos-metrics

On order (1.10.4 clusters), dcos-metrics needs to be updated on the agents.

The following script can be exectued to ensure that this is updated on each of the agents.
See the script here: https://gist.github.com/benclarkwood/60a3289ecc86de76852aed596beb1837#file-metrics-sh-L8

####  Add a universe stub

The `beta-prometheus` package is not available in the Universe. Add the following stub:
```bash
dcos package repo remove prometheus-aws
dcos package repo add --index=0 prometheus-aws https://universe-converter.mesosphere.com/transform?url=https://infinity-artifacts.s3.amazonaws.com/permanent/prometheus/assets/scale-testing-beta/stub-universe-prometheus.json
```

#### Configure and install

First create a `prometheus-options.json` file with the following settings:
```json
{
  "grafana": {
    "cpus": 2,
    "mem": 4096,
    "public": false,
    "ui_port": 3000
  },
  "prometheus": {
    "cpus": 2,
    "dcos_metrics_node_port": 61091,
    "interval": 30,
    "mem": 8192,
    "mesos_exporter_port": 9105,
    "scrape_node_dcos_metrics": true,
    "timeout": 25,
    "volume": {
      "size": 25000,
      "type": "ROOT"
    }
  },
  "service": {
    "log_level": "INFO",
    "name": "prometheus",
    "service_account": "",
    "service_account_secret": "",
    "user": "root"
  }
}
```

Then install the package with the following command:
```bash
dcos package install beta-prometheus --options=prometheus-options.json --yes
```

#### Connecting

In order to connect to Prometheus or Grafana (also part of the `beta-prometheus` package), the DC/OS Tunnel CLI can be used (assuming a valid SSH key has been added to your SSH agent):
```bash
dcos package install --yes tunnel-cli
dcos tunnel socks --user=centos --port=8080 --verbose
```
(note the use of the `centos` user on Centos-based clusters)

This sets up a SOCKS proxy listening on `localhost:8080` through which private instances in the cluster can be accessed. Please consult your browser's documentation in order to configure it accordingly.

#### Get the endpoints

In order to determine what address is to be used for the Grafana and Prometheus user interfaces, the `dcos beta-prometheus` CLI can be used as follows:

For Grafana the following command:
```bash
dcos beta-prometheus --name=prometheus endpoints grafana
```
generates output resembling
```json
{
  "address": ["172.31.10.58:3000"],
  "dns": ["grafana-0-server.prometheus.autoip.dcos.thisdcos.directory:3000"]
}
```
and for Prometheus
```bash
dcos beta-prometheus --name=prometheus endpoints prometheus
```
generates
```json
{
  "address": ["172.31.4.247:9090"],
  "dns": ["prometheus-0-server.prometheus.autoip.dcos.thisdcos.directory:9090"],
  "vip": "prometheus.prometheus.l4lb.thisdcos.directory:9090"
}
```
where these addresses can be used in the proxy-configured browser.
