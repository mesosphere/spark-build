#!/usr/bin/env bash

# Builds spark, docker image, and package from manifest.json
# Spins up a DCOS cluster and runs tests against it
#
# ENV vars:
#
#  TEST_RUNNER_DIR - mesos-spark-integration-tests/test-runner/
#
#  CLUSTER_NAME - name to use for CCM cluster#
#  DCOS_URL (optional) - If given, the tests will run against this
#                        cluster, and not spin up a new one.
#  DCOS_OAUTH_TOKEN
#
#  AWS vars used for tests:
#  AWS_ACCESS_KEY_ID
#  AWS_SECRET_ACCESS_KEY
#  S3_BUCKET
#  S3_PREFIX

set -x -e
set -o pipefail


build_universe() {
    ./bin/make-package.py
    (cd build && tar czf package.tgz package)
    ./bin/make-universe.sh
}

start_cluster() {
    if [ -z "${DCOS_URL}" ]; then
        DCOS_URL=http://$(./bin/launch-cluster.sh)
    fi
    TOKEN=$(python -c "import requests;js={'token':'"${DCOS_OAUTH_TOKEN}"'};r=requests.post('"${DCOS_URL}"/acs/api/v1/auth/login',json=js);print(r.json()['token'])")
    dcos config set core.dcos_acs_token ${TOKEN}
}

configure_cli() {
    aws s3 cp ./build/spark-universe.zip "s3://${S3_BUCKET}/${S3_PREFIX}spark-universe-${TEAMCITY_BUILD_ID}" --acl public-read

    dcos config set core.dcos_url "${DCOS_URL}"
    dcos package repo add --index=0 spark-test "http://${S3_BUCKET}.s3.amazonaws.com/${S3_PREFIX}spark-universe.zip"
}

install_spark() {
    dcos --log-level=INFO package install spark --yes

    while [ $(dcos marathon app list --json | jq ".[] | .tasksHealthy") -ne "1" ]
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

build_universe;
start_cluster;
configure_cli;
install_spark;
run_tests;
