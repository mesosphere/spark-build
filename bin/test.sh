#!/usr/bin/env bash

# Builds spark, docker image, and package from manifest.json
# Spins up a DCOS cluster and runs tests against it
#
# ENV vars:
#
#  SPARK_DIST - spark-1.6.0-bin-hadoop2.4.tgz
#  DCOS_TESTS_DIR - dcos-tests/
#  TEST_RUNNER_DIR - mesos-spark-integration-tests/test-runner/
#
#  VERSION - spark-<VERSION>.tgz to upload to s3, and package.json version
#  SPARK_URI - marathon.json spark uri
#  DOCKER_IMAGE - marathon.json docker image (w/o the tag)
#  CLUSTER_NAME - name to use for CCM cluster#
#  DCOS_URL (optional) - If given, the tests will run against this
#                        cluster, and not spin up a new one.
#
#  AWS vars used for spark upload:
#  AWS_REGION
#  AWS_ACCESS_KEY_ID
#  AWS_SECRET_ACCESS_KEY
#  S3_BUCKET
#  S3_PREFIX
#
#  AWS vars used for tests:
#  TEST_AWS_ACCESS_KEY_ID
#  TEST_AWS_SECRET_ACCESS_KEY
#  TEST_S3_BUCKET
#  TEST_S3_PREFIX

set -x -e
set -o pipefail

FULL_DOCKER_IMAGE=${DOCKER_IMAGE}:${VERSION}

build_spark() {
    pushd ${SPARK_DIR}
    ./make-distribution.sh -Phadoop-2.4
    cp -r dist spark-$VERSION
    tar czf spark-${VERSION}.tgz spark-${VERSION}
    aws s3 --region=${AWS_REGION} cp \
           --acl public-read \
           spark-${VERSION}.tgz s3://${S3_BUCKET}/${S3_PREFIX}spark-${VERSION}.tgz
    popd
}

build_docker() {
    tar xvf ${SPARK_DIST} -C build
    ./bin/make-docker.sh build/spark-${VERSION}/ ${FULL_DOCKER_IMAGE}
    docker push ${FULL_DOCKER_IMAGE}
}

build_universe() {
    # create universe
    # jq --arg version ${VERSION} \
    #    --arg uri ${SPARK_URI} \
    #    --arg image ${FULL_DOCKER_IMAGE} \
    #    '{python_package, "version": $version, "spark_uri": $uri, "docker_image": $image}' \
    #    manifest.json > manifest.json.tmp
    #mv manifest.json.tmp manifest.json
    ./bin/make-package.py
    ./bin/make-universe.sh
}

start_cluster() {
    if [ -z "${DCOS_URL}" ]; then
        DCOS_URL=http://$(./bin/launch-cluster.sh)
    fi
}

configure_cli() {
    dcos config set core.dcos_url ${DCOS_URL}
    dcos config set package.sources "[\"file://$(pwd)/build/spark-universe\"]"
    dcos package update
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
        "dcos ${DCOS_URL}"
    popd
}

# build_spark;
build_docker;
build_universe;
start_cluster;
configure_cli;
install_spark;
run_tests;
