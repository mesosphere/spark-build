#!/bin/bash

# Env Vars:
#   GIT_BRANCH (assumed to have prefix "refs/tags/custom-")

set -e -x -o pipefail


function publish_dists() {
    set_hadoop_versions
    for HADOOP_VERSION in "${HADOOP_VERSIONS[@]}"
    do
        if does_hadoop_profile_exist "${HADOOP_VERSION}"; then
            publish_dist "${HADOOP_VERSION}"
            # publish_docker "${HADOOP_VERSION}"
        fi
    done
}

# $1: hadoop version (e.g. "2.6")
function does_hadoop_profile_exist() {
    (cd "${SPARK_DIR}" && ./build/mvn help:all-profiles | grep "hadoop-$1")
}

# $1: hadoop version (e.g. "2.6")
function publish_dist() {
    HADOOP_VERSION=$1 make dist
    rename_dist
    AWS_ACCESS_KEY_ID=${PROD_AWS_ACCESS_KEY_ID} \
                     AWS_SECRET_ACCESS_KEY=${PROD_AWS_SECRET_ACCESS_KEY} \
                     S3_URL="s3://${PROD_S3_BUCKET}/${PROD_S3_PREFIX}/" \
                     upload_to_s3
}

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
SPARK_DIR="${DIR}/../../spark"
SPARK_BUILD_DIR="${DIR}/../../spark-build"
SPARK_VERSION=${GIT_BRANCH#origin/tags/custom-} # e.g. "2.0.2"
source "${DIR}/jenkins.sh"

pushd "${SPARK_BUILD_DIR}"
install_cli
docker_login
# build_and_test
publish_dists
popd
