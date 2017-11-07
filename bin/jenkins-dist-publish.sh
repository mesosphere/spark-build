#!/bin/bash

# Env Vars:
#   GIT_BRANCH (assumed to have prefix "refs/tags/custom-")

set -e -x -o pipefail

# $1: profile (e.g. "hadoop-2.6")
function does_profile_exist() {
    (cd "${SPARK_DIR}" && ./build/mvn help:all-profiles | grep "$1")
}

# uploads build/spark/spark-*.tgz to S3
function upload_to_s3 {
    aws s3 cp --acl public-read "${SPARK_DIST_DIR}/${SPARK_DIST}" "${S3_URL}"
}

function set_hadoop_versions {
    HADOOP_VERSIONS=( "2.4" "2.6" "2.7" )
}

# rename build/dist/spark-*.tgz to build/dist/spark-<TAG>.tgz
# globals: $SPARK_VERSION
function rename_dist {
    SPARK_DIST_DIR="spark-${SPARK_VERSION}-bin-${HADOOP_VERSION}"
    SPARK_DIST="${SPARK_DIST_DIR}.tgz"

    mkdir -p "${SPARK_DIST_DIR}"

    pushd "${DIST_DIR}"
    tar xvf spark-*.tgz
    rm spark-*.tgz
    mv spark-* "${SPARK_DIST_DIR}"
    tar czf "${SPARK_DIST}" "${SPARK_DIST_DIR}"
    rm -rf "${SPARK_DIST_DIR}"
    popd
}


function publish_dists() {
    set_hadoop_versions
    for HADOOP_VERSION in "${HADOOP_VERSIONS[@]}"
    do
        if does_profile_exist "hadoop-${HADOOP_VERSION}"; then
            publish_dist "${HADOOP_VERSION}"
        fi
    done
}

# $1: hadoop version (e.g. "2.6")
function publish_dist() {
    make prod-dist -e HADOOP_VERSION=$1
    rename_dist
    AWS_ACCESS_KEY_ID=${PROD_AWS_ACCESS_KEY_ID} \
                     AWS_SECRET_ACCESS_KEY=${PROD_AWS_SECRET_ACCESS_KEY} \
                     S3_URL="s3://${PROD_S3_BUCKET}/${PROD_S3_PREFIX}/" \
                     upload_to_s3
    make clean-dist
}

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
SPARK_DIR="${DIR}/../spark"
SPARK_BUILD_DIR="${DIR}/.."
DIST_DIR="${DIR}/../build/dist"
SPARK_VERSION=${GIT_BRANCH#origin/tags/custom-} # e.g. "2.0.2"

pushd "${SPARK_BUILD_DIR}"
publish_dists
popd
