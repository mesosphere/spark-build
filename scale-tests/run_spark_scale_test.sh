#!/bin/bash

## Set variables
for ARG in "$@"
do
  KEY=$(echo $ARG | cut -f1 -d=)
  VAL=$(echo $ARG | cut -f2 -d=)

  case "$KEY" in
    SSH_KEY)                                SSH_KEY=${VALUE} ;;
    CASSANDRA_CONFIG)                       CASSANDRA_CONFIG=${VALUE} ;;
    CLUSTER_USERNAME)                       CLUSTER_USERNAM=${VALUE} ;;
    CLUSTER_PASSWORD)                       CLUSTER_PASSWORD=${VALUE} ;;
    CLUSTER_URL)                            CLUSTER_URL=${VALUE} ;;
    KAFKA_CONFIG)                           KAFKA_CONFIG=${VALUE} ;;
    KAFKA_ZK_CONFIG)                        KAFAKA_ZK_CONFIG=${VALUE} ;;
    NUM_DISPATCHERS)                        NUM_DISPATCHERS=${VALUE} ;;
    NUM_CASSANDRA_CLUSTERS)                 NUM_CASSANDRA_CLUSTERS=${VALUE} ;;
    NUM_FINITE_DISPATCHERS)                 NUM_FINITE_DISPATCHERS=${VALUE} ;;
    NUM_KAFKA_CLUSTERS)                     NUM_KAFKA_CLUSTERS=${VALUE} ;;
    NUM_GPU_DISPATCHERS)                    NUM_GPU_DISPATCHERS=${VALUE} ;;
    NUM_PRODUCER_WORDS)                     NUM_PRODUCER_WORDS=${VALUE} ;;
    NUM_PRODUCER_WORDS_PER_SECOND)          NUM_PRODUCER_WORDS_PER_SECOND=${VALUE} ;;
    NUM_PRODUCERS_PER_FINITE_KAFKA)         NUM_PRODUCERS_PER_KAFKA=${VALUE} ;;
    NUM_CONSUMERS_PER_FINITE_PRODUCER)      NUM_CONSUMERS_PER_PRODUCER=${VALUE} ;;
    NUM_PRODUCERS_PER_INFINITE_KAFKA)       NUM_PRODUCERS_PER_KAFKA=${VALUE} ;;
    NUM_CONSUMERS_PER_INFINITE_PRODUCER)    NUM_CONSUMERS_PER_PRODUCER=${VALUE} ;;
    QUOTA_DRIVERS_CPUS)                     QUOTA_DRIVERS_CPUS=${VALUE} ;;
    QUOTA_DRIVERS_MEM)                      QUOTA_DRIVERS_MEM=${VALUE} ;;
    QUOTA_EXECUTORS_CPUS)                   QUOTA_EXECUTORS_CPUS=${VALUE} ;;
    QUOTA_EXECUTORS_MEM)                    QUOTA_EXECUTORS_MEM=${VALUE} ;;
    QUOTA_EXECUTORS_GPUS)                   QUOTA_EXECUTORS_GPUS=${VALUE} ;;
    TEST_NAME)                              TEST_NAME=${VALUE} ;;
    TEST_S3_BUCKET)                         TEST_S3_BUCKET=${VALUE} ;;
    TEST_S3_FOLDER)                         TEST_S3_FOLDER=${VALUE} ;;
    SECURITY)                               SECURITY=${VALUE} ;;

  esac

done

if [ -z $SECURITY ]
then
  echo "Need to set SECURITY either to 'strict' or 'permissive'"
  exit 1
fi


## Get a stable shell 
git clone git@github.com:mesosphere/spark-build.git
cd spark-build
docker build -t mesosphere/dcos-commons:${LOGNAME}-spark scale-tests/


## Script to be executed inside the shell
###### cat > /tmp/spark_scale_script.sh << EOF
## Setup cluster

dcos cluster setup --insecure --username=${CLUSTER_USERNAME} --password=${CLUSTER_PASSWORD} ${CLUSTER_URL}
eval "$(ssh-agent)"
ssh-add -k /ssh/key

## Add Spark stub
dcos package repo add --index=0 spark-aws https://universe-converter.mesosphere.com/transform?url=https://infinity-artifacts.s3.amazonaws.com/permanent/spark/assets/scale-testing/stub-universe-spark.json

## Deploy dispatchers
./scale-tests/deploy-dispatchers.py \
  --quota-drivers-cpus $QUOTA_DRIVERS_CPUS \
  --quota-drivers-mem $QUOTA_DRIVERS_MEM \
  --quota-executors-cpus $QUOTA_EXECUTORS_CPUS \
  --quota-executors-mem $QUOTA_EXECUTORS_MEM \
  $NUM_DISPATCHERS $TEST_NAME ${TEST_NAME}-${NUM_DISPATCHERS}

## Deploy GPU dispatchers

## There is a bug in the script that auto-fails if a dispatcher already exists so
## we uninstall the first n dispatchers to update them for GPU ones
for ((idx=0; i<${NUM_GPU_DISPATCHERS}; i++))
do
  dcos package uninstall spark --app-id=/${TEST_NAME}spark-0${idx} --yes
done

./scale-tests/deploy-dispatchers.py \
  --quota-drivers-cpus $QUOTA_DRIVERS_CPUS \
  --quota-drivers-mem $QUOTA_DRIVERS_MEM \
  --quota-executors-cpus $QUOTA_EXECUTORS_CPUS \
  --quota-executors-mem $QUOTA_EXECUTORS_MEM \
  --quota-executors-gpus $QUOTA_EXECUTORS_GPUS \
  $NUM_GPU_DISPATCHERS $TEST_NAME ${TEST_NAME}-${NUM_GPU_DISPATCHERS}

DISPATCHERS_JSON_FILE="${TEST_NAME}-${NUM_DISPATCHERS}-dispatchers.json"

## Upload dispatchers file to S3
aws s3 cp --acl public-read \
  "${DISPATCHERS_JSON_FILE}" \
  "s3://${TEST_S3_BUCKET}/${TEST_S3_FOLDER}/${DISPATCHERS_JSON_FILE}"

## Deploy streaming infrastructure
SERVICE_NAMES_PREFIX="${TEST_NAME}"
INFRASTRUCTURE_JSON_FILE="${TEST_NAME}-infrastructure.json"
KAFKA_ZK_CONFIG=${KAFKA_ZK_CONFIG:-scale-tests/configs/kafka-zookeeper-options.json}
KAFKA_CONFIG=${KAFKA_CONFIG:-scale-tests/configs/kafka-options.json}
CASSANDRA_CONFIG=s${CASSANDRA_CONFIG:-cale-tests/configs/cassandra-options.json}

./scale-tests/setup_streaming.py $INFRASTRUCTURE_JSON_FILE \
  --service-names-prefix $SERVICE_NAMES_PREFIX \
  --kafka-zookeeper-config $KAFKA_ZK_CONFIG \
  --kafka-cluster-count $NUM_KAFKA_CLUSTERS \
  --kafka-config $KAFKA_CONFIG \
  --cassandra-cluster-count $NUM_CASSANDRA_CLUSTERS \
  --cassandra-config $CASSANDRA_CONFIG


## Upload infrastructure file to S3
aws s3 cp --acl public-read \
  "${INFRASTRUVTURE_JSON_FILE}" \
  "s3://${TEST_S3_BUCKET}/${TEST_S3_FOLDER}/${INFRASTRUCTURE_JSON_FILE}"

## Prepare dispatcher list files
NUM_INFINITE_DISPATCHERS="$(expr "${NUM_DISPATCHERS}" - "${NUM_FINITE_DISPATCHERS}")"
DISPATCHERS_FINITE_JSON_FILE="${TEST_NAME}-finite-dispatchers.json"
DISPATCHERS_INFINITE_JSON_FILE="${TEST_NAME}-infinite-dispatchers.json"

## Create 'finite' and 'infinite' dispatcher files
cat "${DISPATCHERS_JSON_FILE}" | jq -r ".spark=.spark[0:${NUM_FINITE_DISPATCHERS}]" > "${DISPATCHERS_FINITE_JSON_FILE}"
cat "${DISPATCHERS_JSON_FILE}" | jq -r ".spark=.spark[${NUM_FINITE_DISPATCHERS}:]" > "${DISPATCHERS_INFINITE_JSON_FILE}"

## Deploy streaming jobs
### Deploy failing jobs
KAFKA_JAR=${KAFKA_JAR:-http://infinity-artifacts.s3.amazonaws.com/scale-tests/dcos-spark-scala-tests-assembly-20180523-c450832.jar}
SUBMISSIONS_FINITE_OUTPUT_FILE="${TEST_NAME}-finite-submissions.out"
SUBMISSIONS_INFINITE_OUTPUT_FILE="${TEST_NAME}-infinite-submissions.out"
PRODUCER_SPARK_CORES_MAX=2
PRODUCER_SPARK_EXECUTOR_CORES=2
CONSUMER_BATCH_SIZE_SECONDS=10
CONSUMER_SPARK_CORES_MAX=1
CONSUMER_SPARK_EXECUTOR_CORES=1

./scale-tests/kafka_cassandra_streaming_test.py \
  $DISPATCHERS_FINITE_JSON_FILE \
  $INFRASTRUCTURE_JSON_FILE \
  $SUBMISSIONS_FINITE_OUTPUT_FILE \
  --jar $KAFKA_JAR \
  --num-producers-per-kafka $NUM_PRODUCERS_PER_FINITE_KAFKA \
  --num-consumers-per-producer $NUM_CONSUMERS_PER_FINITE_PRODUCER \
  --producer-number-of-words $NUM_PRODUCER_WORDS \
  --producer-words-per-second $NUM_PRODUCER_WORDS_PER_SECOND \
  --producer-spark-cores-max $PRODUCER_SPARK_CORES_MAX \
  --producer-spark-executor-cores $PRODUCER_SPARK_EXECUTOR_CORES \
  --producer-must-fail \
  --consumer-must-fail \
  --consumer-write-to-cassandra \
  --consumer-batch-size-seconds $CONSUMER_BATCH_SIZE_SECONDS \
  --consumer-spark-cores-max $CONSUMER_SPARK_CORES_MAX \
  --consumer-spark-executor-cores $CONSUMER_SPARK_EXECUTOR_CORES

### Deploy finite jobs
./scale-tests/kafka_cassandra_streaming_test.py \
  $DISPATCHERS_FINITE_JSON_FILE \
  $INFRASTRUCTURE_JSON_FILE \
  $SUBMISSIONS_FINITE_JSON_FILE \
  --jar $KAFKA_JAR \
  --num-producers-per-kafka $NUM_PRODUCERS_PER_FINITE_KAFKA \
  --num-consumers-per-producer $NUM_CONSUMERS_PER_FINITE_PRODUCER \
  --producer-number-of-words $NUM_PRODUCER_WORDS \
  --producer-words-per-second $NUM_PRODUCER_WORDS_PER_SECOND \
  --producer-spark-cores-max $PRODUCER_SPARK_CORES_MAX \
  --producer-spark-executor-cores $PRODUCER_SPARK_EXECUTOR_CORES \
  --consumer-write-to-cassandra \
  --consumer-batch-size-seconds $CONSUMER_BATCH_SIZE_SECONDS \
  --consumer-spark-cores-max $CONSUMER_SPARK_CORES_MAX \
  --consumer-spark-executor-cores $CONSUMER_SPARK_EXECUTOR_CORES
    
### Deploy infinite jobs
INFINITE_PRODUCER_NUMBER_OF_WORDS=0

./scale-tests/kafka_cassandra_streaming_test.py \
  $DISPATCHERS_INFINITE_JSON_FILE \
  $INFRASTRUCTURE_JSON_FILE \
  $SUBMISSIONS_FINITE_JSON_FILE \
  --jar $KAFKA_JAR \
  --num-producers-per-kafka $NUM_PRODUCERS_PER_INFINITE_KAFKA \
  --num-consumers-per-producer $NUM_CONSUMERS_PER_INFINITE_PRODUCER \
  --producer-number-of-words $INFINITE_PRODUCER_NUMBER_OF_WORDS \
  --producer-words-per-second $NUM_PRODUCER_WORDS_PER_SECOND \
  --producer-spark-cores-max $PRODUCER_SPARK_CORES_MAX \
  --producer-spark-executor-cores $PRODUCER_SPARK_EXECUTOR_CORES \
  --consumer-batch-size-seconds $CONSUMER_BATCH_SIZE_SECONDS \
  --consumer-spark-cores-max $CONSUMER_SPARK_CORES_MAX \
  --consumer-spark-executor-cores $CONSUMER_SPARK_EXECUTOR_CORES

## Deploy GPU jobs
git checkout st-gpu-strict
nohup ./scale-tests/batch_test.py $DISPATCHERS_JSON_FILE \
    --docker-image "samvantran/spark-dcos-gpu:minpatch-nv390-cuda9-cudnn7115-tf15" \
    --max-num-dispatchers 2 \
    --submits-per-min 10 \
    --spark-cores-max 4 \
    --spark-mesos-executor-gpus 4 \
    --spark-mesos-max-gpus 4 \
    --no-supervise &

git checkout master

## Deploy batch jobs via marathon app
./scale-tests/batch_test.py ${DISPATCHERS_JSON_FILE} --submits-per-min 4

# The following is commented out due to a bug in the marathon app
# Also, I'm not sure how to upload files to s3 in here 
#
#cd scale-tests/
# ./deploy-marathon-service.sh spark-batch-workload.json.template \
#   $CLUSTER_USERNAME \
#   $CLUSTER_PASSWORD \
#   "https://${TEST_S3_BUCKET}.s3.amazonaws.com/${TEST_S3_FOLDER}/${DISPATCHER_JSON_FILE}" \
#   6 13000 "${DISPATCHER_JSON_FILE} --submits-per-min 4"
# cd ..

###### EOF

## Run script inside stable container
docker exec --net=host \
  -v $(pwd):/spark-build \
  -v $SSH_KEY:/ssh/key:ro \
  -v ~/.aws./credentials:~/.aws/credentials \
  mesosphere/dcos-commons:${LOGNAME}-spark /tmp/spark_scale_script.sh
