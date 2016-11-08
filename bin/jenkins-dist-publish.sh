#!/bin/bash

# Env Vars:
#   GIT_BRANCH (assumed to have prefix "refs/tags/custom-")

set -e -x -o pipefail

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
SPARK_DIR="${DIR}/../../spark"
SPARK_BUILD_DIR=${DIR}/..

function run_tests() {
    # test
    source bin/jenkins.sh
    install_cli
    docker_login
    make dist && export $(cat spark_dist_uri.properties)
    make universe && export $(cat "${WORKSPACE}/stub-universe.properties")
    make test

}

function publish() {
    HADOOP_VERSIONS=( "2.4" "2.6" "2.7" )
    for HADOOP_VERSION in "${HADOOP_VERSIONS[@]}"
    do
        pushd "${SPARK_DIR}"
        ./build/mvn help:all-profiles | grep "hadoop-${HADOOP_VERSION}"
        PROFILE_EXISTS=$?
        popd

        if [ ${PROFILE_EXISTS} -eq 0 ]; then
            HADOOP_VERSION=${HADOOP_VERSION} make dist
            rename_dist
            AWS_ACCESS_KEY_ID=${PROD_AWS_ACCESS_KEY_ID} \
                             AWS_SECRET_ACCESS_KEY=${PROD_AWS_SECRET_ACCESS_KEY} \
                             S3_BUCKET=${PROD_S3_BUCKET} \
                             S3_PREFIX=${PROD_S3_PREFIX} \
                             upload_to_s3
        fi
        popd
    done
}

pushd "${SPARK_BUILD_DIR}"
run_tests
publish
popd
