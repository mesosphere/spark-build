#!/usr/bin/env bash
#
# Requirements:
# - git
# - docker
# - maws

# TODO: checkout the master branch (in a temporary directory?) and build the
# docker image used below.
# git clone git@github.com:mesosphere/spark-build.git
# cd spark-build
# docker build -t "mesosphere/dcos-commons:${LOGNAME}-spark" scale-tests/

eval "$(maws li "${AWS_ACCOUNT}")"

docker run \
  --rm \
  -it \
  -d \
  --name="${CONTAINER_NAME}" \
  --net=host \
  -v "$(pwd):/spark-build" \
  -v "${CLUSTER_SSH_KEY}:${CONTAINER_SSH_KEY}:ro" \
  -v "${HOME}/.aws/credentials:/root/.aws/credentials:ro" \
  -e AWS_PROFILE="${AWS_PROFILE}" \
  -e SECURITY="${SECURITY}" \
  "${IMAGE_NAME}" \
  bash

docker exec "${CONTAINER_NAME}" bash -c "ssh-agent | grep -v echo > ${CONTAINER_SSH_AGENT_EXPORTS}"

function container_exec () {
  # TODO: remove this echo.
  echo "\
    . ${CONTAINER_SSH_AGENT_EXPORTS}
    ssh-add -k ${CONTAINER_SSH_KEY} > /dev/null 2>&1
    set -x
    ${*}
  "
  # TODO: maybe remove the set -x?
  docker exec "${CONTAINER_NAME}" bash -c "\
    . ${CONTAINER_SSH_AGENT_EXPORTS}
    ssh-add -k ${CONTAINER_SSH_KEY} > /dev/null 2>&1
    set -x
    ${*}
  "
}

container_exec \
  dcos cluster setup \
    --insecure \
    --username="${CLUSTER_USERNAME}" \
    --password="${CLUSTER_PASSWORD}" \
    "${CLUSTER_URL}"

container_exec \
  dcos package install --yes dcos-enterprise-cli

container_exec \
  dcos package repo add --index=0 spark-aws "${CLUSTER_SPARK_PACKAGE_REPO}"

# Install infrastructure.
container_exec \
  ./scale-tests/setup_streaming.py "${INFRASTRUCTURE_OUTPUT_FILE}" \
    --service-names-prefix "${SERVICE_NAMES_PREFIX}" \
    --kafka-zookeeper-config "${KAFKA_ZOOKEEPER_CONFIG}" \
    --kafka-cluster-count "${KAFKA_CLUSTER_COUNT}" \
    --kafka-config "${KAFKA_CONFIG}" \
    --cassandra-cluster-count "${CASSANDRA_CLUSTER_COUNT}" \
    --cassandra-config "${CASSANDRA_CONFIG}"

# Upload infrastructure file to S3.
container_exec \
  aws s3 cp --acl public-read \
    "${INFRASTRUCTURE_OUTPUT_FILE}" \
    "s3://${TEST_S3_BUCKET}/${TEST_S3_FOLDER}/"

# Install non-GPU dispatchers.
container_exec \
  ./scale-tests/deploy-dispatchers.py \
    --quota-drivers-cpus "${NON_GPU_QUOTA_DRIVERS_CPUS}" \
    --quota-drivers-mem "${NON_GPU_QUOTA_DRIVERS_MEM}" \
    --quota-executors-cpus "${NON_GPU_QUOTA_EXECUTORS_CPUS}" \
    --quota-executors-mem "${NON_GPU_QUOTA_EXECUTORS_MEM}" \
    "${NON_GPU_NUM_DISPATCHERS}" \
    "${SERVICE_NAMES_PREFIX}" \
    "${NON_GPU_DISPATCHERS_OUTPUT_FILE}"

# Upload non-GPU dispatcher list to S3.
container_exec \
  aws s3 cp --acl public-read \
    "${NON_GPU_DISPATCHERS_OUTPUT_FILE}" \
    "s3://${TEST_S3_BUCKET}/${TEST_S3_FOLDER}/"

# Upload non-GPU JSON dispatcher list to S3.
container_exec \
  aws s3 cp --acl public-read \
    "${NON_GPU_DISPATCHERS_JSON_OUTPUT_FILE}" \
    "s3://${TEST_S3_BUCKET}/${TEST_S3_FOLDER}/"

# Install GPU dispatchers.
container_exec \
  ./scale-tests/deploy-dispatchers.py \
    --quota-drivers-cpus "${GPU_QUOTA_DRIVERS_CPUS}" \
    --quota-drivers-mem "${GPU_QUOTA_DRIVERS_MEM}" \
    --quota-executors-cpus "${GPU_QUOTA_EXECUTORS_CPUS}" \
    --quota-executors-mem "${GPU_QUOTA_EXECUTORS_MEM}" \
    --quota-executors-gpus "${GPU_QUOTA_EXECUTORS_GPUS}" \
    "${GPU_NUM_DISPATCHERS}" \
    "${SERVICE_NAMES_PREFIX}gpu-" \
    "${GPU_DISPATCHERS_OUTPUT_FILE}"

# Upload GPU dispatcher list to S3.
container_exec \
  aws s3 cp --acl public-read \
    "${GPU_DISPATCHERS_OUTPUT_FILE}" \
    "s3://${TEST_S3_BUCKET}/${TEST_S3_FOLDER}/"

# Upload non-GPU JSON dispatcher list to S3.
container_exec \
  aws s3 cp --acl public-read \
    "${GPU_DISPATCHERS_JSON_OUTPUT_FILE}" \
    "s3://${TEST_S3_BUCKET}/${TEST_S3_FOLDER}/"

# Merge non-GPU and GPU dispatcher list files.
container_exec "\
  jq -s \
    '{spark: (.[0].spark + .[1].spark)}' \
    ${NON_GPU_DISPATCHERS_JSON_OUTPUT_FILE} \
    ${GPU_DISPATCHERS_JSON_OUTPUT_FILE} \
    > ${DISPATCHERS_JSON_OUTPUT_FILE} \
"

# Upload merged dispatcher list file.
container_exec \
  aws s3 cp --acl public-read \
    "${DISPATCHERS_JSON_OUTPUT_FILE}" \
    "s3://${TEST_S3_BUCKET}/${TEST_S3_FOLDER}/"

# Deploy failing jobs.
container_exec \
  ./scale-tests/kafka_cassandra_streaming_test.py \
    "${DISPATCHERS_JSON_OUTPUT_FILE}" \
    "${INFRASTRUCTURE_OUTPUT_FILE}" \
    "${FAILING_SUBMISSIONS_OUTPUT_FILE}" \
    --jar "${TEST_ASSEMBLY_JAR_URL}" \
    --num-producers-per-kafka "${FAILING_NUM_PRODUCERS_PER_KAFKA}" \
    --num-consumers-per-producer "${FAILING_NUM_CONSUMERS_PER_PRODUCER}" \
    --producer-must-fail \
    --producer-number-of-words "${FAILING_PRODUCER_NUMBER_OF_WORDS}" \
    --producer-words-per-second "${FAILING_PRODUCER_WORDS_PER_SECOND}" \
    --producer-spark-cores-max "${FAILING_PRODUCER_SPARK_CORES_MAX}" \
    --producer-spark-executor-cores "${FAILING_PRODUCER_SPARK_EXECUTOR_CORES}" \
    --consumer-must-fail \
    --consumer-write-to-cassandra \
    --consumer-batch-size-seconds "${FAILING_CONSUMER_BATCH_SIZE_SECONDS}" \
    --consumer-spark-cores-max "${FAILING_CONSUMER_SPARK_CORES_MAX}" \
    --consumer-spark-executor-cores "${FAILING_CONSUMER_SPARK_EXECUTOR_CORES}"

# Upload failing jobs submissions file.
container_exec \
  aws s3 cp --acl public-read \
    "${FAILING_SUBMISSIONS_OUTPUT_FILE}" \
    "s3://${TEST_S3_BUCKET}/${TEST_S3_FOLDER}/"

# Deploy finite jobs. Consumers write to Cassandra.
container_exec \
  ./scale-tests/kafka_cassandra_streaming_test.py \
    "${DISPATCHERS_JSON_OUTPUT_FILE}" \
    "${INFRASTRUCTURE_OUTPUT_FILE}" \
    "${FINITE_SUBMISSIONS_OUTPUT_FILE}" \
    --jar "${TEST_ASSEMBLY_JAR_URL}" \
    --num-producers-per-kafka "${FINITE_NUM_PRODUCERS_PER_KAFKA}" \
    --num-consumers-per-producer "${FINITE_NUM_CONSUMERS_PER_PRODUCER}" \
    --producer-number-of-words "${FINITE_PRODUCER_NUMBER_OF_WORDS}" \
    --producer-words-per-second "${FINITE_PRODUCER_WORDS_PER_SECOND}" \
    --producer-spark-cores-max "${FINITE_PRODUCER_SPARK_CORES_MAX}" \
    --producer-spark-executor-cores "${FINITE_PRODUCER_SPARK_EXECUTOR_CORES}" \
    --consumer-write-to-cassandra \
    --consumer-batch-size-seconds "${FINITE_CONSUMER_BATCH_SIZE_SECONDS}" \
    --consumer-spark-cores-max "${FINITE_CONSUMER_SPARK_CORES_MAX}" \
    --consumer-spark-executor-cores "${FINITE_CONSUMER_SPARK_EXECUTOR_CORES}"

# Upload finite jobs submissions file.
container_exec \
  aws s3 cp --acl public-read \
    "${FINITE_SUBMISSIONS_OUTPUT_FILE}" \
    "s3://${TEST_S3_BUCKET}/${TEST_S3_FOLDER}/"

# Deploy infinite jobs. Consumers don't write to Cassandra.
container_exec \
  ./scale-tests/kafka_cassandra_streaming_test.py \
    "${DISPATCHERS_JSON_OUTPUT_FILE}" \
    "${INFRASTRUCTURE_OUTPUT_FILE}" \
    "${INFINITE_SUBMISSIONS_OUTPUT_FILE}" \
    --jar "${TEST_ASSEMBLY_JAR_URL}" \
    --num-producers-per-kafka "${INFINITE_NUM_PRODUCERS_PER_KAFKA}" \
    --num-consumers-per-producer "${INFINITE_NUM_CONSUMERS_PER_PRODUCER}" \
    --producer-number-of-words "${INFINITE_PRODUCER_NUMBER_OF_WORDS}" \
    --producer-words-per-second "${INFINITE_PRODUCER_WORDS_PER_SECOND}" \
    --producer-spark-cores-max "${INFINITE_PRODUCER_SPARK_CORES_MAX}" \
    --producer-spark-executor-cores "${INFINITE_PRODUCER_SPARK_EXECUTOR_CORES}" \
    --consumer-batch-size-seconds "${INFINITE_CONSUMER_BATCH_SIZE_SECONDS}" \
    --consumer-spark-cores-max "${INFINITE_CONSUMER_SPARK_CORES_MAX}" \
    --consumer-spark-executor-cores "${INFINITE_CONSUMER_SPARK_EXECUTOR_CORES}"

# Upload infinite jobs submissions file.
container_exec \
  aws s3 cp --acl public-read \
    "${INFINITE_SUBMISSIONS_OUTPUT_FILE}" \
    "s3://${TEST_S3_BUCKET}/${TEST_S3_FOLDER}/"

# Deploy batch jobs.
container_exec \
  ./scale-tests/deploy-batch-marathon-app.py \
    --app-id "${BATCH_APP_ID}" \
    --dcos-username "${CLUSTER_USERNAME}" \
    --dcos-password "${CLUSTER_PASSWORD}" \
    --security "${SECURITY}" \
    --input-file-uri "${DISPATCHERS_JSON_OUTPUT_FILE_URL}" \
    --script-cpus "${BATCH_SCRIPT_CPUS}" \
    --script-mem "${BATCH_SCRIPT_MEM}" \
    --script-args "\
      ${DISPATCHERS_JSON_OUTPUT_FILE} \
      --submits-per-min ${BATCH_SUBMITS_PER_MIN} \
    "\
    --spark-build-branch "${BATCH_SPARK_BUILD_BRANCH}"

# Deploy batch GPU jobs.
container_exec \
  ./scale-tests/deploy-batch-marathon-app.py \
    --app-id "${GPU_APP_ID}" \
    --dcos-username "${CLUSTER_USERNAME}" \
    --dcos-password "${CLUSTER_PASSWORD}" \
    --security "${SECURITY}" \
    --input-file-uri "${GPU_DISPATCHERS_JSON_OUTPUT_FILE_URL}" \
    --script-cpus "${GPU_SCRIPT_CPUS}" \
    --script-mem "${GPU_SCRIPT_MEM}" \
    --script-args "\
      ${GPU_DISPATCHERS_JSON_OUTPUT_FILE} \
      --submits-per-min ${GPU_SUBMITS_PER_MIN} \
      --docker-image ${GPU_DOCKER_IMAGE} \
      --max-num-dispatchers ${GPU_MAX_NUM_DISPATCHERS} \
      --spark-cores-max ${GPU_SPARK_CORES_MAX} \
      --spark-mesos-executor-gpus ${GPU_SPARK_MESOS_EXECUTOR_GPUS} \
      --spark-mesos-max-gpus ${GPU_SPARK_MESOS_MAX_GPUS} \
      --no-supervise \
    "\
    --spark-build-branch "${GPU_SPARK_BUILD_BRANCH}"

# List S3 artifacts.
container_exec \
  aws s3 ls "s3://${TEST_S3_BUCKET}/${TEST_S3_FOLDER}/"
