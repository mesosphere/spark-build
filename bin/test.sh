#!/usr/bin/env bash

# Spins up a DCOS cluster and runs tests against it

set -e
set -x
set -o pipefail

BIN_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

check_env() {
    # Check env early, before starting the cluster:
    if [ -z "$AWS_ACCESS_KEY_ID" \
            -o -z "$AWS_SECRET_ACCESS_KEY" \
            -o -z "$S3_BUCKET" \
            -o -z "$S3_PREFIX" \
            -o -z "$TEST_JAR_PATH" ]; then
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
        STDOUT=$(${COMMONS_TOOLS_DIR}/launch_ccm_cluster.py)
        DCOS_URL=$(echo "${STDOUT}" | jq .url)
        if [ $? -ne 0 -o "$DCOS_URL" = "http://" ]; then
            notify_github failure "Cluster launch failed"
            exit 1
        fi
    fi
}

configure_cli() {
    notify_github pending "Configuring CLI"
    dcos config set core.dcos_url "${DCOS_URL}"
    dcos config set core.ssl_verify false
    ${COMMONS_TOOLS_DIR}/dcos_login.py
    dcos config show
    if [ -n "${STUB_UNIVERSE_URL}" ]; then
        dcos package repo add --index=0 spark-test "${STUB_UNIVERSE_URL}"
    fi
}

install_spark() {
    notify_github pending "Installing Spark"

    if [ "$SECURITY" = "strict" ]; then
        # custom configuration to enable auth stuff:
        ${COMMONS_TOOLS_DIR}/setup_permissions.sh nobody "*" # spark's default service.role
        echo '{ "service": { "user": "nobody", "principal": "service-acct", "secret_name": "secret" } }' > /tmp/spark.json
        dcos --log-level=INFO package install spark --options=/tmp/spark.json --yes
    else
        dcos --log-level=INFO package install spark --yes
    fi

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

    pushd tests
    if [[ ! -d env ]]; then
        virtualenv -p python3 env
    fi
    source env/bin/activate
    pip install -r requirements.txt
    py.test test.py
    if [ $? -ne 0 ]; then
        notify_github failure "Tests failed"
        exit 1
    fi
    popd
}

check_env
fetch_commons_tools
start_cluster
# TODO: Migrate the following three commands to dcos-commons-tools/run-tests.py
configure_cli
install_spark
run_tests

notify_github success "Tests Passed"
