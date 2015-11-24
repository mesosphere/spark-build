#!/usr/bin/env bash

# Builds spark, docker image, and package from conf/manifest.json
# Spins up a DCOS cluster and runs tests against it
#
# ENV vars:
#
#  SPARK_DIR - spark/
#  DCOS_TESTS_DIR - dcos-tests/
#  TEST_RUNNER_DIR - mesos-spark-integration-tests/test-runner/
#
#  VERSION - spark-<VERSION>.tgz to upload to s3, and package.json version
#  SPARK_URI - marathon.json spark uri
#  DOCKER_IMAGE - marathon.json docker image (w/o the tag)
#  CLUSTER_NAME - name to use for CCM cluster
#
#  aws vars used for spark upload:
#  AWS_REGION
#  AWS_ACCESS_KEY_ID
#  AWS_SECRET_ACCESS_KEY
#  S3_BUCKET
#  S3_PREFIX
#
#  aws vars used for tests:
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
    ./bin/make-docker.sh ${SPARK_DIR}spark-${VERSION}/ ${FULL_DOCKER_IMAGE}
    docker push ${FULL_DOCKER_IMAGE}
}

build_universe() {
    # create universe
    jq --arg version ${VERSION} \
       --arg uri ${SPARK_URI} \
       --arg image ${FULL_DOCKER_IMAGE} \
       '{python_package, "version": $version, "spark_uri": $uri, "docker_image": $image}' \
       conf/manifest.json > conf/manifest.json.tmp
    mv conf/manifest.json.tmp conf/manifest.json
    ./bin/make-package.py
    ./bin/make-universe.sh
}

start_cluster() {
    #TEST_MASTER_URI=http://$(./bin/launch-cluster.sh)
    TEST_MASTER_URI=http://spark-bui-elasticl-mplpvcnv4opi-17080008.us-west-2.elb.amazonaws.com
}

configure_cli() {
    dcos config set core.dcos_url ${TEST_MASTER_URI}
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
    cp src/main/resources/dcos-application.conf src/main/resources/application.conf
    AWS_ACCESS_KEY=${TEST_AWS_ACCESS_KEY_ID} AWS_SECRET_KEY=${TEST_AWS_SECRET_ACCESS_KEY} AWS_BUCKET=${TEST_S3_BUCKET} AWS_PREFIX=${TEST_S3_PREFIX} \
                  sbt "dcos ${TEST_MASTER_URI}"
    popd
}


#build_spark;
build_docker;
build_universe;
start_cluster;
configure_cli;
install_spark;
run_tests;
