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

setup_permissions() {
    if [ "$SECURITY" = "strict" ]; then
        # custom configuration to enable auth stuff:
        ${COMMONS_TOOLS_DIR}/setup_permissions.sh nobody "*" # spark's default service.role
    fi
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
setup_permissions
run_tests

notify_github success "Tests Passed"
