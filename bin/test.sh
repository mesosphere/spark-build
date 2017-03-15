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
            -o -z "$TEST_JAR_PATH" \
            -o -z "$COMMONS_DIR"]; then
       echo "Missing required env. See check in ${BIN_DIR}/test.sh."
       echo "Environment:"
       env
       exit 1
    fi
}

start_cluster() {
    if [ -n "${DCOS_URL}" ]; then
        echo "Using existing cluster: $DCOS_URL"
    else
        echo "Launching new cluster"
        CCM_JSON=$(CCM_AGENTS=5 ${COMMONS_DIR}/tools/launch_ccm_cluster.py)
        DCOS_URL=$(echo "${CCM_JSON}" | jq .url)
        if [ $? -ne 0 -o "$DCOS_URL" = "http://" ]; then
            exit 1
        fi
    fi
}

configure_cli() {
    dcos config set core.dcos_url "${DCOS_URL}"
    dcos config set core.ssl_verify false
    ${COMMONS_DIR}/tools/dcos_login.py
    dcos config show
    if [ -n "${STUB_UNIVERSE_URL}" ]; then
        dcos package repo add --index=0 spark-test "${STUB_UNIVERSE_URL}"
    fi
}

initialize_service_account() {
    if [ "$SECURITY" = "strict" ]; then
        ${COMMONS_DIR}/tools/create_service_account.sh --strict
        ${COMMONS_DIR}/tools/setup_permissions.sh root "*"
        ${COMMONS_DIR}/tools/setup_permissions.sh root hdfs-role
    fi
}

build_scala_test_jar() {
    (cd tests/jobs/scala && sbt assembly)
}

run_tests() {
    pushd tests
    if [[ ! -d venv ]]; then
        virtualenv -p python3 venv
    fi
    source venv/bin/activate
    pip install -r requirements.txt
    SCALA_TEST_JAR_PATH=$(pwd)/jobs/scala/target/scala-2.11/dcos-spark-scala-tests-assembly-0.1-SNAPSHOT.jar \
                       py.test -s test.py
    popd
}

check_env
start_cluster
# TODO: Migrate the following three commands to dcos-commons-tools/run-tests.py
configure_cli
initialize_service_account
build_scala_test_jar
run_tests
