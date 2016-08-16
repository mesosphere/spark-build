#!/usr/bin/env bash

# Spins up a DCOS cluster and runs tests against it
#
# ENV vars:
#
#  TEST_RUNNER_DIR - mesos-spark-integration-tests/test-runner/
#  DOCKER_IMAGE - Docker image used to make the DC/OS package
#
#  # CLI Env vars:
#  DCOS_USERNAME - Used for CLI login
#  DCOS_PASSWORD - Used for CLI login
#  STUB_UNIVERSE_URL - path to uploaded universe package
#
#  # CCM Env Vars:
#  DCOS_URL (optional) - If given, the tests will run against this
#                        cluster, and not spin up a new one.
#  when DCOS_URL is empty:
#    CCM_AUTH_TOKEN - auth token for CCM interaction
#    CLUSTER_NAME - name to use for new CCM cluster
#    DCOS_CHANNEL (optional) - channel to create the CCM cluster against
#
#  # AWS vars used for tests:
#  AWS_ACCESS_KEY_ID
#  AWS_SECRET_ACCESS_KEY
#  S3_BUCKET
#  S3_PREFIX

set -x -e
set -o pipefail

BIN_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"


start_cluster() {
    if [ -n "${DCOS_URL}" ]; then
        echo "Using existing cluster: $DCOS_URL"
    else
        echo "Launching new cluster"
        DCOS_URL=http://$(./launch-cluster.sh)
    fi
}

configure_cli() {
    TOKEN=$(python -c "import requests;js={'uid':'"${DCOS_USERNAME}"', 'password': '"${DCOS_PASSWORD}"'};r=requests.post('"${DCOS_URL}"/acs/api/v1/auth/login',json=js,verify=False);print(r.json()['token'])")
    dcos config set core.dcos_acs_token "${TOKEN}"
    dcos config set core.dcos_url "${DCOS_URL}"
    dcos config show
    dcos package repo add --index=0 spark-test "${STUB_UNIVERSE_URL}"
    dcos package repo list
}

install_spark() {
    # with universe server running, there are no longer enough CPUs to
    # launch spark jobs if we give the dispatcher an entire CPU
    # TODO: remove this?
    echo '{"service": {"cpus": 0.1}}' > /tmp/spark.json

    dcos --log-level=INFO package install spark --options=/tmp/spark.json --yes

    while [[ $(dcos marathon app list --json | jq '.[] | select(.id=="/spark") | .tasksHealthy') -ne "1" ]]
    do
        sleep 5
    done

    # sleep 30s due to mesos-dns propagation delays to /service/sparkcli/
    sleep 30
}

run_tests() {
    pushd ${TEST_RUNNER_DIR}
    sbt -Dconfig.file=src/main/resources/dcos-application.conf \
        -Daws.access_key=${AWS_ACCESS_KEY_ID} \
        -Daws.secret_key=${AWS_SECRET_ACCESS_KEY} \
        -Daws.s3.bucket=${S3_BUCKET} \
        -Daws.s3.prefix=${S3_PREFIX} \
        "dcos"
    popd
}

# Grab dcos-commons build/release tools:
cd ${BIN_DIR}
rm -rf dcos-commons-tools/ && curl https://infinity-artifacts.s3.amazonaws.com/dcos-commons-tools.tgz | tar xz
_notify_github() {
    ./dcos-commons-tools/github_update.py $1 test $2
}

_notify_github pending "Starting Cluster"
start_cluster;
_notify_github pending "Configuring CLI"
configure_cli;
_notify_github pending "Installing Spark"
install_spark;
_notify_github pending "Running Tests"
run_tests;
_notify_github success "Tests Passed"
