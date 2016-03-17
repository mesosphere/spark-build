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
#
#  AWS vars used for tests:
#  TEST_AWS_ACCESS_KEY_ID
#  TEST_AWS_SECRET_ACCESS_KEY
#  TEST_S3_BUCKET
#  TEST_S3_PREFIX

set -x -e
set -o pipefail

# FULL_DOCKER_IMAGE=${DOCKER_IMAGE}:${VERSION}

# build_docker() {
#     mkdir -p build/spark
#     tar xvf ${SPARK_DIST} -C build/spark
#     ./bin/make-docker.sh build/spark/spark*/ ${FULL_DOCKER_IMAGE}
#     docker push ${FULL_DOCKER_IMAGE}
# }

build_universe() {
    # create universe
    # jq --arg version ${VERSION} \
    #    --arg uri ${SPARK_URI} \
    #    --arg image ${FULL_DOCKER_IMAGE} \
    #    '{python_package, "version": $version, "spark_uri": $uri, "docker_image": $image}' \
    #    manifest.json > manifest.json.tmp
    # mv manifest.json.tmp manifest.json
    ./bin/make-package.py
    (cd build && tar czf package.tgz package)
    ./bin/make-universe.sh
}

start_cluster() {
    if [ -z "${DCOS_URL}" ]; then
        DCOS_URL=http://$(./bin/launch-cluster.sh)
    fi
}

configure_cli() {
    AWS_ACCESS_KEY_ID="${TEST_AWS_ACCESS_KEY_ID}" \
         AWS_SECRET_ACCESS_KEY="${TEST_AWS_SECRET_ACCESS_KEY}" \
         aws s3 cp ./build/spark-universe.zip "s3://${TEST_S3_BUCKET}/${TEST_S3_PREFIX}" --acl public-read

    dcos config set core.dcos_url "${DCOS_URL}"
    dcos package repo remove Universe
    dcos package repo add spark-test "http://${TEST_S3_BUCKET}.s3.amazonaws.com/${TEST_S3_PREFIX}spark-universe.zip"
    # dcos config set package.sources "[\"file://$(pwd)/build/spark-universe\"]"
    # dcos package update
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
        -Daws.access_key=${TEST_AWS_ACCESS_KEY_ID} \
        -Daws.secret_key=${TEST_AWS_SECRET_ACCESS_KEY} \
        -Daws.s3.bucket=${TEST_S3_BUCKET} \
        -Daws.s3.prefix=${TEST_S3_PREFIX} \
        "dcos"
    popd
}

# build_docker;
build_universe;
start_cluster;
configure_cli;
install_spark;
run_tests;
