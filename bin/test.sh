#!/usr/bin/env bash

# Spins up a DCOS cluster and runs tests against it
#
# ENV vars:
#
#  TEST_RUNNER_DIR - mesos-spark-integration-tests/test-runner/
#  DOCKER_IMAGE - Docker image used to make the DC/OS package
#  COMMONS_TOOLS_DIR - path to dcos-commons/tools, or empty to fetch latest tgz
#
#  CLI Env vars:
#    DCOS_USERNAME - Used for CLI login
#    DCOS_PASSWORD - Used for CLI login
#    STUB_UNIVERSE_URL - path to uploaded universe package
#
#  CCM Env Vars:
#    DCOS_URL (optional) - If given, the tests will run against this
#                          cluster, and not spin up a new one.
#  when DCOS_URL is empty:
#    CCM_AUTH_TOKEN - auth token for CCM interaction
#    CLUSTER_NAME - name to use for new CCM cluster
#    DCOS_CHANNEL (optional) - channel to create the CCM cluster against
#
#  AWS vars used for tests:
#    AWS_ACCESS_KEY_ID
#    AWS_SECRET_ACCESS_KEY
#    S3_BUCKET
#    S3_PREFIX

set +e
set -x
set -o pipefail

BIN_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

check_env() {
    # Check env early, before starting the cluster:
    if [ -z "$TEST_RUNNER_DIR" -o -z "$DOCKER_IMAGE" \
            -o -z "$DCOS_USERNAME" -o -z "$DCOS_PASSWORD" \
            -o -z "$STUB_UNIVERSE_URL" \
            -o -z "$AWS_ACCESS_KEY_ID" -o -z "$AWS_SECRET_ACCESS_KEY" \
            -o -z "$S3_BUCKET" -o -z "$S3_PREFIX" ]; then
        echo "Missing required env. See check in ${BIN_DIR}/test.sh."
        env
        exit 1
    fi
}

fetch_commons_tools() {
    if [ -z "${COMMONS_TOOLS_DIR}" ]; then
        pushd ${BIN_DIR}
        rm -rf dcos-commons-tools/ && curl https://infinity-artifacts.s3.amazonaws.com/dcos-commons-tools.tgz | tar xz
        popd
        COMMONS_TOOLS_DIR=${BIN_DIR}/dcos-commons-tools/
    fi
}

notify_github() {
    ${COMMONS_TOOLS_DIR}/github_update.py $1 test $2
}

start_cluster() {
    if [ -n "${DCOS_URL}" ]; then
        echo "Using existing cluster: $DCOS_URL"
    else
        notify_github pending "Starting Cluster"
        echo "Launching new cluster"

        DCOS_URL=$(${COMMONS_TOOLS_DIR}/launch_ccm_cluster.py | jq .url)
        if [ $? -ne 0 -o "$DCOS_URL" = "http://" ]; then
            notify_github failure "Cluster launch failed"
            exit 1
        fi
    fi
}

configure_cli() {
    notify_github pending "Configuring CLI"

    # EE
    #TOKEN=$(python -c "import requests;js={'uid':'"${DCOS_USERNAME}"', 'password': '"${DCOS_PASSWORD}"'};r=requests.post('"${DCOS_URL}"/acs/api/v1/auth/login',json=js);print(r.json()['token'])")

    # # Open
    # TOKEN=$(python -c "import requests; import sys; js = {'token':'"${DCOS_OAUTH_TOKEN}"'}; r=requests.post('"${DCOS_URL}"/acs/api/v1/auth/login',json=js); sys.stderr.write(str(r.json())); print(r.json()['token'])")

    # dcos config set core.dcos_acs_token "${TOKEN}"

    dcos config set core.dcos_url "${DCOS_URL}"
    ${COMMONS_TOOLS_DIR}/dcos_login.py
    dcos config show
    dcos package repo add --index=0 spark-test "${STUB_UNIVERSE_URL}"
    dcos package repo list
}

install_spark() {
    notify_github pending "Installing Spark"

    # with universe server running, there are no longer enough CPUs to
    # launch spark jobs if we give the dispatcher an entire CPU
    # TODO: remove this?
    echo '{"service": {"cpus": 0.1}}' > /tmp/spark.json

    dcos --log-level=INFO package install spark --options=/tmp/spark.json --yes
    if [ $? -ne 0 ]; then
        notify_github failure "Spark install failed"
        exit 1
    fi

    SECONDS=0
    while [[ $(dcos marathon app list --json | jq '.[] | select(.id=="/spark") | .tasksHealthy') -ne "1" ]]
    do
        sleep 5
        if [ $SECONDS -gt 600 ]; then # 10 mins
            notify_github failure "Spark install timed out"
            exit 1
        fi
    done

    # sleep 30s due to mesos-dns propagation delays to /service/sparkcli/
    sleep 30
}

run_tests() {
    notify_github pending "Running Tests"
    pushd ${TEST_RUNNER_DIR}
    sbt -Dconfig.file=src/main/resources/dcos-application.conf \
        -Daws.access_key=${AWS_ACCESS_KEY_ID} \
        -Daws.secret_key=${AWS_SECRET_ACCESS_KEY} \
        -Daws.s3.bucket=${S3_BUCKET} \
        -Daws.s3.prefix=${S3_PREFIX} \
        "dcos"
    if [ $? -ne 0 ]; then
        notify_github failure "Tests failed"
        exit 1
    fi
    popd
}

check_env
fetch_commons_tools
start_cluster
configure_cli
install_spark
run_tests

notify_github success "Tests Passed"
