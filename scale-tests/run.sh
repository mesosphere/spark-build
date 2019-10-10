#!/usr/bin/env bash

set -eu -o pipefail
export TZ=UTC

function usage () {
  echo 'Usage: ./run.sh \\'
  echo '         <path to test configuration file> \\'
  echo '         <test name> \\'
  echo '         <test S3 bucket> \\'
  echo '         <test S3 folder> \\'
  echo '         <path to cluster SSH private key> \\'
  echo '         <DCOS username> \\'
  echo '         <DCOS password> \\'
  echo '         [<non interactive>] (optional, defaults to "interactive")'
  echo
  echo 'Example: ./run.sh \\'
  echo '           scale-tests/configs/2018-01-01.env \\'
  echo '           scale-tests-2018-01-01 \\'
  echo '           infinity-artifacts \\'
  echo '           scale-tests/2018-01-01 \\'
  echo '           ~/.ssh/dcos \\'
  echo '           john \\'
  echo '           john123 \\'
  echo '           non-interactive \\'
}

################################################################################
# Parse and validate command line and parameter file parameters ################
################################################################################

if [ "${#}" -lt 7 ]; then
  echo -e "run.sh needs at least 7 arguments but was given ${#}\\n"
  usage
  exit 1
fi

readonly REQUIREMENTS='git docker maws tee'

for requirement in ${REQUIREMENTS}; do
  if ! [[ -x $(command -v "${requirement}") ]]; then
    echo "You need to install '${requirement}' to run this script"
    exit 1
  fi
done

readonly TEST_CONFIG="${1:-}"
readonly TEST_NAME="${2:-}"
readonly TEST_S3_BUCKET="${3:-}"
readonly TEST_S3_FOLDER="${4:-}"
readonly CLUSTER_SSH_KEY="${5:-}"
readonly DCOS_USERNAME="${6:-}"
readonly DCOS_PASSWORD="${7:-}"
readonly MODE="${8:-non-interactive}"

for file in "${CLUSTER_SSH_KEY}" "${TEST_CONFIG}"; do
  if ! [[ -s ${file} ]]; then
    echo "File '${file}' doesn't exist or is empty"
    exit 1
  fi
done

if [ "${MODE}" != "interactive" ] && [ "${MODE}" != "non-interactive" ]; then
  echo "MODE must be either 'interactive' or 'non-interactive', is '${MODE}'"
  exit 1
fi

function is_interactive () {
  [ "${MODE}" = "interactive" ]
}

readonly AWS_ACCOUNT='Team 10'
readonly CONTAINER_NAME="${TEST_NAME}-$(basename "${TEST_CONFIG}" .env)"
readonly CONTAINER_SSH_AGENT_EXPORTS=/tmp/ssh-agent-exports
readonly CONTAINER_SSH_KEY=/ssh/key
readonly CONTAINER_FINISHED_SETTING_UP_FILE=/tmp/finished-setting-up
readonly IMAGE_NAME="mesosphere/dcos-commons:${CONTAINER_NAME}"
readonly SCALE_TESTS_DIRECTORY="scale-tests"
readonly TEST_DIRECTORY="${SCALE_TESTS_DIRECTORY}/runs/${CONTAINER_NAME}"
readonly TEST_REPOSITORY_DIRECTORY="${SCALE_TESTS_DIRECTORY}/checkouts/${TEST_NAME}"
readonly TEST_S3_DIRECTORY_URL="s3://${TEST_S3_BUCKET}/${TEST_S3_FOLDER}/"
readonly LOGS_DIRECTORY="${TEST_DIRECTORY}/script_logs"
readonly LOG_FILE="${LOGS_DIRECTORY}/$(date +%Y%m%dT%H%M%SZ)_$(whoami).log"
readonly DCOS_CLI_REFRESH_INTERVAL_SEC=600 # 10 minutes.
readonly GROUP_FILE_NAME="${TEST_REPOSITORY_DIRECTORY}/marathon_group.json"

# shellcheck source=/dev/null
source "${TEST_CONFIG}"

mkdir -p "${TEST_DIRECTORY}"
mkdir -p "${LOGS_DIRECTORY}"

if [ "${SECURITY}" != "permissive" ] && [ "${SECURITY}" != "strict" ]; then
  echo "SECURITY must be either 'permissive' or 'strict', is '${SECURITY}'"
  exit 1
fi

for boolean_option in SHOULD_INSTALL_INFRASTRUCTURE \
                        SHOULD_INSTALL_NON_GPU_DISPATCHERS \
                        SHOULD_INSTALL_GPU_DISPATCHERS \
                        SHOULD_RUN_FINITE_STREAMING_JOBS \
                        SHOULD_RUN_INFINITE_STREAMING_JOBS \
                        SHOULD_RUN_BATCH_JOBS \
                        SHOULD_RUN_GPU_BATCH_JOBS \
                        SHOULD_UNINSTALL_INFRASTRUCTURE_AT_THE_END; do
  if [ "${!boolean_option}" != "true" ] && [ "${!boolean_option}" != "false" ]; then
    echo "${boolean_option} must be either 'true' or 'false', is '${!boolean_option}'"
    exit 1
  fi
done

function log {
  local -r message="${*:-}"
  echo "$(date "+%Y-%m-%d %H:%M:%S") | ${message}" 2>&1 | tee -a "${LOG_FILE}"
}

function container_exec () {
  local -r command="${*:-}"
  log "${command}"
  docker exec "${CONTAINER_NAME}" \
    bash -l -c "${command}" 2>&1 | tee -a "${LOG_FILE}"
}

declare -x AWS_PROFILE
eval "$(maws li "${AWS_ACCOUNT}")"

################################################################################
# Calculate a few things and present a pre-test report #########################
################################################################################

readonly SPARK_TOTAL_DISPATCHERS=$((SPARK_NON_GPU_DISPATCHERS + SPARK_GPU_DISPATCHERS))
readonly STREAMING_FINITE_PRODUCERS=$((KAFKA_CLUSTER_COUNT * STREAMING_FINITE_PRODUCERS_PER_KAFKA))
readonly STREAMING_FINITE_CONSUMERS=$((STREAMING_FINITE_PRODUCERS * STREAMING_FINITE_CONSUMERS_PER_PRODUCER))
readonly STREAMING_FINITE_JOBS=$((STREAMING_FINITE_PRODUCERS + STREAMING_FINITE_CONSUMERS))
readonly STREAMING_INFINITE_PRODUCERS=$((KAFKA_CLUSTER_COUNT * STREAMING_INFINITE_PRODUCERS_PER_KAFKA))
readonly STREAMING_INFINITE_CONSUMERS=$((STREAMING_INFINITE_PRODUCERS * STREAMING_INFINITE_CONSUMERS_PER_PRODUCER))
readonly STREAMING_INFINITE_JOBS=$((STREAMING_INFINITE_PRODUCERS + STREAMING_INFINITE_CONSUMERS))
readonly STREAMING_JOBS=$((STREAMING_FINITE_JOBS + STREAMING_INFINITE_JOBS))

readonly SPARK_NON_GPU_TOTAL_QUOTA_DRIVERS_CPUS=$((SPARK_NON_GPU_DISPATCHERS * SPARK_NON_GPU_QUOTA_DRIVERS_CPUS))
readonly SPARK_NON_GPU_TOTAL_QUOTA_DRIVERS_MEM=$((SPARK_NON_GPU_DISPATCHERS * SPARK_NON_GPU_QUOTA_DRIVERS_MEM))
readonly SPARK_NON_GPU_TOTAL_QUOTA_EXECUTORS_CPUS=$((SPARK_NON_GPU_DISPATCHERS * SPARK_NON_GPU_QUOTA_EXECUTORS_CPUS))
readonly SPARK_NON_GPU_TOTAL_QUOTA_EXECUTORS_MEM=$((SPARK_NON_GPU_DISPATCHERS * SPARK_NON_GPU_QUOTA_EXECUTORS_MEM))

readonly SPARK_GPU_TOTAL_QUOTA_DRIVERS_CPUS=$((SPARK_GPU_DISPATCHERS * SPARK_GPU_QUOTA_DRIVERS_CPUS))
readonly SPARK_GPU_TOTAL_QUOTA_DRIVERS_MEM=$((SPARK_GPU_DISPATCHERS * SPARK_GPU_QUOTA_DRIVERS_MEM))
readonly SPARK_GPU_TOTAL_QUOTA_DRIVERS_GPUS=$((SPARK_GPU_DISPATCHERS * SPARK_GPU_QUOTA_DRIVERS_GPUS))
readonly SPARK_GPU_TOTAL_QUOTA_EXECUTORS_CPUS=$((SPARK_GPU_DISPATCHERS * SPARK_GPU_QUOTA_EXECUTORS_CPUS))
readonly SPARK_GPU_TOTAL_QUOTA_EXECUTORS_MEM=$((SPARK_GPU_DISPATCHERS * SPARK_GPU_QUOTA_EXECUTORS_MEM))
readonly SPARK_GPU_TOTAL_QUOTA_EXECUTORS_GPUS=$((SPARK_GPU_DISPATCHERS * SPARK_GPU_QUOTA_EXECUTORS_GPUS))

readonly SPARK_NON_GPU_QUOTA_CPUS=$((SPARK_NON_GPU_TOTAL_QUOTA_DRIVERS_CPUS + SPARK_NON_GPU_TOTAL_QUOTA_EXECUTORS_CPUS))
readonly SPARK_NON_GPU_QUOTA_MEM=$((SPARK_NON_GPU_TOTAL_QUOTA_DRIVERS_MEM + SPARK_NON_GPU_TOTAL_QUOTA_EXECUTORS_MEM))
readonly SPARK_GPU_QUOTA_CPUS=$((SPARK_GPU_TOTAL_QUOTA_DRIVERS_CPUS + SPARK_GPU_TOTAL_QUOTA_EXECUTORS_CPUS))
readonly SPARK_GPU_QUOTA_MEM=$((SPARK_GPU_TOTAL_QUOTA_DRIVERS_MEM + SPARK_GPU_TOTAL_QUOTA_EXECUTORS_MEM))

readonly TOTAL_QUOTA_CPUS=$((SPARK_NON_GPU_QUOTA_CPUS +
                             SPARK_GPU_QUOTA_CPUS +
                             ZOOKEEPER_CPUS +
                             KAFKA_CPUS +
                             CASSANDRA_CPUS +
                             DSENGINE_CPUS))
readonly TOTAL_QUOTA_MEM=$((SPARK_NON_GPU_QUOTA_MEM +
                             SPARK_GPU_QUOTA_MEM +
                             ZOOKEEPER_MEM +
                             KAFKA_MEM +
                             CASSANDRA_MEM +
                             DSENGINE_MEM))
readonly TOTAL_QUOTA_GPUS=$((SPARK_GPU_TOTAL_QUOTA_DRIVERS_GPUS +
                             SPARK_GPU_TOTAL_QUOTA_EXECUTORS_GPUS +
                             DSENGINE_GPUS))

echo
echo    "Test '${TEST_NAME}' parameters:"
echo
echo    "CLUSTER_URL '${CLUSTER_URL}'"
echo
echo    "KAFKA_CLUSTER_COUNT: ${KAFKA_CLUSTER_COUNT}"
echo    "CASSANDRA_CLUSTER_COUNT: ${CASSANDRA_CLUSTER_COUNT}"
echo    "SPARK_TOTAL_DISPATCHERS: ${SPARK_TOTAL_DISPATCHERS} (non-GPU: ${SPARK_NON_GPU_DISPATCHERS}, GPU: ${SPARK_GPU_DISPATCHERS})"
echo
echo    "SPARK_NON_GPU_DISPATCHERS: ${SPARK_NON_GPU_DISPATCHERS}"
echo    " Quota cpus/mem:"
echo -n "   Each:"
echo -n " driver ${SPARK_NON_GPU_QUOTA_DRIVERS_CPUS}/${SPARK_NON_GPU_QUOTA_DRIVERS_MEM},"
echo    " executor ${SPARK_NON_GPU_QUOTA_EXECUTORS_CPUS}/${SPARK_NON_GPU_QUOTA_EXECUTORS_MEM}"
echo -n "   Total:"
echo -n " driver ${SPARK_NON_GPU_TOTAL_QUOTA_DRIVERS_CPUS}/${SPARK_NON_GPU_TOTAL_QUOTA_DRIVERS_MEM},"
echo    " executor ${SPARK_NON_GPU_TOTAL_QUOTA_EXECUTORS_CPUS}/${SPARK_NON_GPU_TOTAL_QUOTA_EXECUTORS_MEM}"
echo
echo    "SPARK_GPU_DISPATCHERS: ${SPARK_GPU_DISPATCHERS}"
echo    " Quota cpus/mem/gpus:"
echo -n "   Each:"
echo -n " driver ${SPARK_GPU_QUOTA_DRIVERS_CPUS:-0}/${SPARK_GPU_QUOTA_DRIVERS_MEM:-0}/${SPARK_GPU_QUOTA_DRIVERS_GPUS:-0},"
echo    " executor ${SPARK_GPU_QUOTA_EXECUTORS_CPUS:-0}/${SPARK_GPU_QUOTA_EXECUTORS_MEM:-0}/${SPARK_GPU_QUOTA_EXECUTORS_GPUS:-0}"
echo -n "   Total:"
echo -n " driver ${SPARK_GPU_TOTAL_QUOTA_DRIVERS_CPUS:-0}/${SPARK_GPU_TOTAL_QUOTA_DRIVERS_MEM:-0}/${SPARK_GPU_TOTAL_QUOTA_DRIVERS_GPUS:-0},"
echo    " executor ${SPARK_GPU_TOTAL_QUOTA_EXECUTORS_CPUS:-0}/${SPARK_GPU_TOTAL_QUOTA_EXECUTORS_MEM:-0}/${SPARK_GPU_TOTAL_QUOTA_EXECUTORS_GPUS:-0}"
echo
echo    "STREAMING_JOBS:         ${STREAMING_JOBS} (finite: ${STREAMING_FINITE_JOBS}, infinite: ${STREAMING_INFINITE_JOBS})"
echo    "BATCH_MAX_NON_GPU_JOBS: ${BATCH_MAX_NON_GPU_JOBS}"
echo    "BATCH_SUBMITS_PER_MIN:  ${BATCH_SUBMITS_PER_MIN}"
echo    "GPU_SUBMITS_PER_MIN:    ${GPU_SUBMITS_PER_MIN}"
echo
echo "Total CPU quota: ${TOTAL_QUOTA_CPUS}"
echo "Total MEM quota: ${TOTAL_QUOTA_MEM}"
echo "Total GPU quota: ${TOTAL_QUOTA_GPUS}"
echo

echo "Existing S3 artifacts for ${TEST_NAME}:"
container_exec \
  aws s3 ls --recursive "${TEST_S3_DIRECTORY_URL}" || true

echo
read -p "Proceed? [y/N]: " ANSWER
case "${ANSWER}" in
  [Yy]* ) ;;
  * )     log 'Exiting...' && exit 0;;
esac

################################################################################
# Set a few more parameters ####################################################
################################################################################

if is_interactive; then
  for boolean_option in SHOULD_INSTALL_INFRASTRUCTURE \
                          SHOULD_INSTALL_NON_GPU_DISPATCHERS \
                          SHOULD_INSTALL_GPU_DISPATCHERS \
                          SHOULD_RUN_FINITE_STREAMING_JOBS \
                          SHOULD_RUN_INFINITE_STREAMING_JOBS \
                          SHOULD_RUN_BATCH_JOBS \
                          SHOULD_RUN_GPU_BATCH_JOBS \
                          SHOULD_UNINSTALL_INFRASTRUCTURE_AT_THE_END; do
    echo
    read -p "${boolean_option}? [y/N]: " ANSWER
    case "${ANSWER}" in
      [Yy]* ) eval "${boolean_option}"=true;;
      * )     eval "${boolean_option}"=false;;
    esac
  done
fi

################################################################################
# Create Docker container for test if it doesn't exist yet #####################
################################################################################

set +e
docker inspect -f '{{.State.Running}}' "${CONTAINER_NAME}" > /dev/null 2>&1
readonly container_running=$?

docker exec -it "${CONTAINER_NAME}" test -f "${CONTAINER_FINISHED_SETTING_UP_FILE}"
readonly container_finished_setting_up=$?
set -e

if [ ${container_running} -ne 0 ] || [ ${container_finished_setting_up} -ne 0 ]; then
  log "Building Docker image for ${TEST_NAME}"

  log "Cleaning up possibly pre-existing containers"
  docker kill "${CONTAINER_NAME}" > /dev/null 2>&1 || true
  docker rm -f "${CONTAINER_NAME}" > /dev/null 2>&1 || true

  rm -rf "${TEST_REPOSITORY_DIRECTORY}"
  git clone git@github.com:mesosphere/spark-build.git "${TEST_REPOSITORY_DIRECTORY}" | tee -a "${LOG_FILE}"

  docker build -t "${IMAGE_NAME}" "${TEST_REPOSITORY_DIRECTORY}/scale-tests" | tee -a "${LOG_FILE}"

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
    bash | tee -a "${LOG_FILE}"

  # This circumvents a warning shown due to container_exec running with a login bash shell.
  docker exec "${CONTAINER_NAME}" \
    bash -c 'sed -i "/mesg/d" ~/.profile' | tee -a "${LOG_FILE}"

  docker exec "${CONTAINER_NAME}" \
    bash -c "ssh-agent | grep -v echo > ${CONTAINER_SSH_AGENT_EXPORTS}" | tee -a "${LOG_FILE}"

  docker exec "${CONTAINER_NAME}" \
    bash -c "echo source ${CONTAINER_SSH_AGENT_EXPORTS} >> ~/.profile" | tee -a "${LOG_FILE}"

  container_exec \
    ssh-add -k "${CONTAINER_SSH_KEY}"

  container_exec \
    curl https://downloads.dcos.io/binaries/cli/linux/x86-64/dcos-1.13/dcos -o dcos

  container_exec \
    chmod +x ./dcos

  container_exec \
    mv dcos /usr/local/bin

  container_exec \
    which dcos

  container_exec \
    dcos

  container_exec \
    dcos cluster setup \
      --insecure \
      --username="${DCOS_USERNAME}" \
      --password="${DCOS_PASSWORD}" \
      "${CLUSTER_URL}"

  # This will refresh the DC/OS CLI authentication periodically in the background.
  docker exec -d "${CONTAINER_NAME}" \
    bash -c "while sleep ${DCOS_CLI_REFRESH_INTERVAL_SEC}; do
      date
      echo 'Refreshing DC/OS CLI authentication (interval: ${DCOS_CLI_REFRESH_INTERVAL_SEC}s)'
      dcos auth login --username=${DCOS_USERNAME} --password=${DCOS_PASSWORD}
      echo
    done | tee -a /tmp/dcos-auth-login-refresh.log" | tee -a "${LOG_FILE}"

  container_exec \
    dcos package install --yes dcos-enterprise-cli

  container_exec \
    touch "${CONTAINER_FINISHED_SETTING_UP_FILE}"
fi

################################################################################
# Create package repository stubs if they're not there #########################
################################################################################

readonly dcos_package_repo_uris="$(container_exec bash -c "dcos package repo list --json | jq -r '.repositories[].uri'")"

for package_repo_envvar in ZOOKEEPER_PACKAGE_REPO \
                             KAFKA_PACKAGE_REPO \
                             CASSANDRA_PACKAGE_REPO \
                             SPARK_PACKAGE_REPO \
                             DSENGINE_PACKAGE_REPO; do
  # Skip envvar if its value is empty.
  if [ -z "${!package_repo_envvar}" ]; then
    break;
  fi

  # Add package repository stub if it's not already there.
  if ! grep -qx "${!package_repo_envvar}" <<< "${dcos_package_repo_uris}"; then
    # ZOOKEEPER_PACKAGE_REPO => zookeeper.
    package_repo_name="$(awk '{s = tolower($0); sub(/_package_repo$/, "", s); print(s)}' <<< "${package_repo_envvar}")"
    container_exec \
      dcos package repo add --index=0 "${package_repo_name}" "${!package_repo_envvar}" || true
  fi
done

################################################################################
# Create Marathon group if it doesn't exist ####################################
################################################################################

if ! grep -qx "/${GROUP_NAME}" <<< "$(container_exec bash -c "dcos marathon group list --json | jq -r '.[].id'")"; then
  cat <<-EOF > "${GROUP_FILE_NAME}"
		{
		  "id": "${GROUP_NAME}",
		  "enforceRole": true
		}
	EOF

  container_exec \
    dcos marathon group add "${GROUP_FILE_NAME}"
fi

################################################################################
# Create quota if it doesn't already exist #####################################
################################################################################

if ! grep -qx "${GROUP_NAME}" <<< "$(container_exec bash -c "dcos quota list --json | jq -r '.[].role'")"; then
  container_exec \
    dcos quota create "${GROUP_FILE_NAME}" \
      --cpu "${TOTAL_QUOTA_CPUS}" \
      --mem "${TOTAL_QUOTA_MEM}" \
      --gpu "${TOTAL_QUOTA_GPUS}"
fi

################################################################################
# Install infrastructure #######################################################
################################################################################

if [ "${SHOULD_INSTALL_INFRASTRUCTURE}" = true ]; then
  log 'Installing infrastructure'
  start_time=$(date +%s)
  container_exec \
    ./scale-tests/setup_streaming.py "${TEST_DIRECTORY}/${INFRASTRUCTURE_OUTPUT_FILE}" \
      --service-names-prefix "${SERVICE_NAMES_PREFIX}" \
      --kafka-zookeeper-config "${ZOOKEEPER_CONFIG}" \
      --kafka-cluster-count "${KAFKA_CLUSTER_COUNT}" \
      --kafka-config "${KAFKA_CONFIG}" \
      --cassandra-cluster-count "${CASSANDRA_CLUSTER_COUNT}" \
      --cassandra-config "${CASSANDRA_CONFIG}"
  end_time=$(date +%s)
  runtime=$((end_time - start_time))
  log "Installed infrastructure in ${runtime} seconds"

  log 'Uploading infrastructure file to S3'
  container_exec \
    aws s3 cp --acl public-read \
      "${TEST_DIRECTORY}/${INFRASTRUCTURE_OUTPUT_FILE}" \
      "${TEST_S3_DIRECTORY_URL}"
else
  log 'Skipping infrastructure installation'
fi

################################################################################
# Install non-GPU Spark dispatchers ############################################
################################################################################

if [ "${SHOULD_INSTALL_NON_GPU_DISPATCHERS}" = true ]; then
  log 'Installing non-GPU dispatchers'
  start_time=$(date +%s)
  container_exec \
    ./scale-tests/deploy-dispatchers.py \
      --group-role "${GROUP_NAME}" \
      --options-json "${SPARK_CONFIG}" \
      --create-quotas false \
      "${SPARK_NON_GPU_DISPATCHERS}" \
      "${SERVICE_NAMES_PREFIX}" \
      "${TEST_DIRECTORY}/${SPARK_NON_GPU_DISPATCHERS_OUTPUT_FILE}"
  end_time=$(date +%s)
  runtime=$((end_time - start_time))
  log "Installed non-GPU dispatchers in ${runtime} seconds"

  log 'Uploading non-GPU dispatcher list to S3'
  container_exec \
    aws s3 cp --acl public-read \
      "${TEST_DIRECTORY}/${SPARK_NON_GPU_DISPATCHERS_OUTPUT_FILE}" \
      "${TEST_S3_DIRECTORY_URL}"

  log 'Uploading non-GPU JSON dispatcher list to S3'
  container_exec \
    aws s3 cp --acl public-read \
      "${TEST_DIRECTORY}/${SPARK_NON_GPU_DISPATCHERS_JSON_OUTPUT_FILE}" \
      "${TEST_S3_DIRECTORY_URL}"
else
  log 'Skipping non-GPU dispatchers installation'
fi

################################################################################
# Install GPU Spark dispatchers ################################################
################################################################################

if [ "${SHOULD_INSTALL_GPU_DISPATCHERS}" = true ]; then
  log 'Installing GPU dispatchers'
  start_time=$(date +%s)
  container_exec \
    ./scale-tests/deploy-dispatchers.py \
      --group-role "${GROUP_NAME}" \
      --options-json "${SPARK_CONFIG}" \
      --create-quotas false \
      "${SPARK_GPU_DISPATCHERS}" \
      "${SERVICE_NAMES_PREFIX}gpu-" \
      "${TEST_DIRECTORY}/${SPARK_GPU_DISPATCHERS_OUTPUT_FILE}"
  end_time=$(date +%s)
  runtime=$((end_time - start_time))
  log "Installed GPU dispatchers in ${runtime} seconds"

  if [ "${SPARK_GPU_REMOVE_EXECUTORS_ROLES_QUOTAS}" = true ]; then
    log 'Removing GPU executors roles quotas'
    last_gpu_index=$((SPARK_GPU_DISPATCHERS - 1))
    for i in $(seq 0 ${last_gpu_index}); do
      container_exec \
        dcos spark quota remove "${TEST_NAME}__gpu-spark-0${i}-executors-role"
    done
  fi

  log 'Uploading GPU dispatcher list to S3'
  container_exec \
    aws s3 cp --acl public-read \
      "${TEST_DIRECTORY}/${SPARK_GPU_DISPATCHERS_OUTPUT_FILE}" \
      "${TEST_S3_DIRECTORY_URL}"

  log 'Uploading GPU JSON dispatcher list to S3'
  container_exec \
    aws s3 cp --acl public-read \
      "${TEST_DIRECTORY}/${SPARK_GPU_DISPATCHERS_JSON_OUTPUT_FILE}" \
      "${TEST_S3_DIRECTORY_URL}"
else
  log 'Skipping GPU dispatchers installation'
fi

################################################################################
# Upload merged (non-GPU + GPU) Spark dispatcher list file #####################
################################################################################

if [[ -s ${TEST_DIRECTORY}/${SPARK_NON_GPU_DISPATCHERS_JSON_OUTPUT_FILE} && -s ${TEST_DIRECTORY}/${SPARK_GPU_DISPATCHERS_JSON_OUTPUT_FILE} ]]; then
  log 'Merging non-GPU and GPU dispatcher list files'
  container_exec "\
    jq -s \
      '{spark: (.[0].spark + .[1].spark)}' \
      ${TEST_DIRECTORY}/${SPARK_NON_GPU_DISPATCHERS_JSON_OUTPUT_FILE} \
      ${TEST_DIRECTORY}/${SPARK_GPU_DISPATCHERS_JSON_OUTPUT_FILE} \
      > ${TEST_DIRECTORY}/${DISPATCHERS_JSON_OUTPUT_FILE} \
  "

  log 'Uploading merged dispatcher list file'
  container_exec \
    aws s3 cp --acl public-read \
      "${TEST_DIRECTORY}/${DISPATCHERS_JSON_OUTPUT_FILE}" \
      "${TEST_S3_DIRECTORY_URL}"
else
  log 'Skipping merging of non-GPU and GPU dispatcher list files'
fi

################################################################################
# Run finite streaming jobs ####################################################
################################################################################

if [ "${SHOULD_RUN_FINITE_STREAMING_JOBS}" = true ]; then
  log 'Starting finite jobs. Consumers write to Cassandra'
  start_time=$(date +%s)
  container_exec \
    ./scale-tests/kafka_cassandra_streaming_test.py \
      "${TEST_DIRECTORY}/${SPARK_NON_GPU_DISPATCHERS_JSON_OUTPUT_FILE}" \
      "${TEST_DIRECTORY}/${INFRASTRUCTURE_OUTPUT_FILE}" \
      "${TEST_DIRECTORY}/${STREAMING_FINITE_SUBMISSIONS_OUTPUT_FILE}" \
      --spark-executor-docker-image \""${SPARK_EXECUTOR_DOCKER_IMAGE}"\" \
      --jar "${TEST_ASSEMBLY_JAR_URL}" \
      --num-producers-per-kafka "${STREAMING_FINITE_PRODUCERS_PER_KAFKA}" \
      --num-consumers-per-producer "${STREAMING_FINITE_CONSUMERS_PER_PRODUCER}" \
      --producer-number-of-words "${STREAMING_FINITE_PRODUCER_NUMBER_OF_WORDS}" \
      --producer-words-per-second "${STREAMING_FINITE_PRODUCER_WORDS_PER_SECOND}" \
      --producer-spark-cores-max "${STREAMING_FINITE_PRODUCER_SPARK_CORES_MAX}" \
      --producer-spark-executor-cores "${STREAMING_FINITE_PRODUCER_SPARK_EXECUTOR_CORES}" \
      --consumer-write-to-cassandra \
      --consumer-batch-size-seconds "${STREAMING_FINITE_CONSUMER_BATCH_SIZE_SECONDS}" \
      --consumer-spark-cores-max "${STREAMING_FINITE_CONSUMER_SPARK_CORES_MAX}" \
      --consumer-spark-executor-cores "${STREAMING_FINITE_CONSUMER_SPARK_EXECUTOR_CORES}"
  end_time=$(date +%s)
  runtime=$((end_time - start_time))
  log "Started finite jobs in ${runtime} seconds"

  log 'Uploading finite jobs submissions file'
  container_exec \
    aws s3 cp --acl public-read \
      "${TEST_DIRECTORY}/${STREAMING_FINITE_SUBMISSIONS_OUTPUT_FILE}" \
      "${TEST_S3_DIRECTORY_URL}"
else
  log 'Skipping running of finite streaming jobs'
fi

################################################################################
# Run infinite streaming jobs ##################################################
################################################################################

if [ "${SHOULD_RUN_INFINITE_STREAMING_JOBS}" = true ]; then
  log 'Starting infinite jobs. Consumers do not write to Cassandra'
  start_time=$(date +%s)
  container_exec \
    ./scale-tests/kafka_cassandra_streaming_test.py \
      "${TEST_DIRECTORY}/${SPARK_NON_GPU_DISPATCHERS_JSON_OUTPUT_FILE}" \
      "${TEST_DIRECTORY}/${INFRASTRUCTURE_OUTPUT_FILE}" \
      "${TEST_DIRECTORY}/${STREAMING_INFINITE_SUBMISSIONS_OUTPUT_FILE}" \
      --spark-executor-docker-image \""${SPARK_EXECUTOR_DOCKER_IMAGE}"\" \
      --jar "${TEST_ASSEMBLY_JAR_URL}" \
      --num-producers-per-kafka "${STREAMING_INFINITE_PRODUCERS_PER_KAFKA}" \
      --num-consumers-per-producer "${STREAMING_INFINITE_CONSUMERS_PER_PRODUCER}" \
      --producer-number-of-words 0 \
      --producer-words-per-second "${STREAMING_INFINITE_PRODUCER_WORDS_PER_SECOND}" \
      --producer-spark-cores-max "${STREAMING_INFINITE_PRODUCER_SPARK_CORES_MAX}" \
      --producer-spark-executor-cores "${STREAMING_INFINITE_PRODUCER_SPARK_EXECUTOR_CORES}" \
      --consumer-batch-size-seconds "${STREAMING_INFINITE_CONSUMER_BATCH_SIZE_SECONDS}" \
      --consumer-spark-cores-max "${STREAMING_INFINITE_CONSUMER_SPARK_CORES_MAX}" \
      --consumer-spark-executor-cores "${STREAMING_INFINITE_CONSUMER_SPARK_EXECUTOR_CORES}"
  end_time=$(date +%s)
  runtime=$((end_time - start_time))
  log "Started infinite jobs in ${runtime} seconds"

  log 'Uploading infinite jobs submissions file'
  container_exec \
    aws s3 cp --acl public-read \
      "${TEST_DIRECTORY}/${STREAMING_INFINITE_SUBMISSIONS_OUTPUT_FILE}" \
      "${TEST_S3_DIRECTORY_URL}"
else
  log 'Skipping running of infinite streaming jobs'
fi

################################################################################
# Run non-GPU batch jobs #######################################################
################################################################################

if [ "${SHOULD_RUN_BATCH_JOBS}" = true ]; then
  log 'Starting batch jobs'
  start_time=$(date +%s)
  container_exec \
    ./scale-tests/deploy-batch-marathon-app.py \
      --app-id "${BATCH_APP_ID}" \
      --dcos-username "${DCOS_USERNAME}" \
      --dcos-password "${DCOS_PASSWORD}" \
      --security "${SECURITY}" \
      --input-file-uri "${SPARK_NON_GPU_DISPATCHERS_JSON_OUTPUT_FILE_URL}" \
      --script-cpus "${BATCH_SCRIPT_CPUS}" \
      --script-mem "${BATCH_SCRIPT_MEM}" \
      --spark-build-branch "${BATCH_SPARK_BUILD_BRANCH}" \
      --script-args "\"\
        ${SPARK_NON_GPU_DISPATCHERS_JSON_OUTPUT_FILE} \
        --submits-per-min ${BATCH_SUBMITS_PER_MIN} \
        --group-role ${GROUP_ROLE} \
      \""
  end_time=$(date +%s)
  runtime=$((end_time - start_time))
  log "Started batch jobs in ${runtime} seconds"
else
  log 'Skipping running of batch jobs'
fi

################################################################################
# Run GPU batch jobs ###########################################################
################################################################################

if [ "${SHOULD_RUN_GPU_BATCH_JOBS}" = true ]; then
  log 'Starting GPU batch jobs'
  start_time=$(date +%s)
  container_exec \
    ./scale-tests/deploy-batch-marathon-app.py \
      --app-id "${GPU_APP_ID}" \
      --dcos-username "${DCOS_USERNAME}" \
      --dcos-password "${DCOS_PASSWORD}" \
      --security "${SECURITY}" \
      --input-file-uri "${SPARK_GPU_DISPATCHERS_JSON_OUTPUT_FILE_URL}" \
      --script-cpus "${GPU_SCRIPT_CPUS}" \
      --script-mem "${GPU_SCRIPT_MEM}" \
      --spark-build-branch "${GPU_SPARK_BUILD_BRANCH}" \
      --script-args "\"\
        ${SPARK_GPU_DISPATCHERS_JSON_OUTPUT_FILE} \
        --submits-per-min ${GPU_SUBMITS_PER_MIN} \
        --docker-image ${GPU_DOCKER_IMAGE} \
        --group-role ${GROUP_ROLE} \
        --max-num-dispatchers ${GPU_MAX_DISPATCHERS} \
        --spark-cores-max ${GPU_SPARK_CORES_MAX} \
        --spark-mesos-executor-gpus ${GPU_SPARK_MESOS_EXECUTOR_GPUS} \
        --spark-mesos-max-gpus ${GPU_SPARK_MESOS_MAX_GPUS} \
      \""
  end_time=$(date +%s)
  runtime=$((end_time - start_time))
  log "Started GPU batch jobs in ${runtime} seconds"
else
  log 'Skipping running of GPU batch jobs'
fi

################################################################################
# Uninstall infrastructure #####################################################
################################################################################

if [ "${SHOULD_UNINSTALL_INFRASTRUCTURE_AT_THE_END}" = true ]; then
  log 'Uninstalling infrastructure'
  start_time=$(date +%s)
  container_exec \
    ./scale-tests/setup_streaming.py "${TEST_DIRECTORY}/${INFRASTRUCTURE_OUTPUT_FILE}" --cleanup
  end_time=$(date +%s)
  runtime=$((end_time - start_time))
  log "Uninstalled infrastructure in ${runtime} seconds"
else
  log 'Skipping uninstalling of infrastructure'
fi

################################################################################
################################################################################
################################################################################

log 'Uploading log file to S3'
container_exec \
  aws s3 cp --acl public-read \
    "${LOG_FILE}" \
    "${TEST_S3_DIRECTORY_URL}script_logs/"

log 'Listing S3 artifacts'
container_exec \
  aws s3 ls --recursive "${TEST_S3_DIRECTORY_URL}"

log "Test output files can also be found under ${TEST_DIRECTORY}"
ls "${TEST_DIRECTORY}"
