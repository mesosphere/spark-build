#!/bin/bash

# Env Vars:
#   GIT_BRANCH (assumed to have prefix "refs/tags/custom-")

set -e -x -o pipefail

# $1: profile (e.g. "hadoop-2.7")
function does_profile_exist() {
    (cd "${SPARK_DIR}" && ./build/mvn help:all-profiles | grep "$1")
}

# uploads build/spark/spark-*.tgz to S3 or saves locally
function store_distributions {
    if [ -n "${DIST_DESTINATION_DIR}" ]; # If set, save a copy locally instead
      then cp "${DIST_DIR}/${SPARK_DIST}" "$DIST_DESTINATION_DIR";
      else aws s3 cp --acl public-read "${DIST_DIR}/${SPARK_DIST}" "${S3_URL}";
    fi
}

function set_versions {
    SCALA_VERSIONS=( "2.11" "2.12" )
    HADOOP_VERSIONS=( "2.7" "2.9" )
}

# rename build/dist/spark-*.tgz to build/dist/spark-<TAG>-bin-scala-<SCALA VERSION>-hadoop-<HADOOP VERSION>.tgz
# e.g.: spark-2.4.3-bin-scala-2.12-hadoop-2.9.tgz
# globals: $SPARK_VERSION
function rename_dist {
    SPARK_DIST_DIR="spark-${SPARK_VERSION}-bin-scala-${SCALA_VERSION}-hadoop-${HADOOP_VERSION}"
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
    set_versions
    for SCALA_VERSION in "${SCALA_VERSIONS[@]}"
    do
        if does_profile_exist "scala-${SCALA_VERSION}"; then
            for HADOOP_VERSION in "${HADOOP_VERSIONS[@]}"
            do
                if does_profile_exist "hadoop-${HADOOP_VERSION}"; then
                    publish_dist "${SCALA_VERSION}" "${HADOOP_VERSION}"
                fi
            done
        fi
    done
}

# $1: scala version  (e.g. "2.11")
# $2: hadoop version (e.g. "2.6")
function publish_dist() {
    SPARK_DIR=${SPARK_DIR} \
        make prod-dist -e SCALA_VERSION="$1" HADOOP_VERSION="$2"
    rename_dist
    AWS_ACCESS_KEY_ID=${PROD_AWS_ACCESS_KEY_ID} \
        AWS_SECRET_ACCESS_KEY=${PROD_AWS_SECRET_ACCESS_KEY} \
        S3_URL="s3://${PROD_S3_BUCKET}/${PROD_S3_PREFIX}/" \
    store_distributions
    make clean-dist
}

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
SPARK_DIR="${DIR}/../../spark"
SPARK_BUILD_DIR="${DIR}/.."
DIST_DIR="${SPARK_BUILD_DIR}/build/dist"
SPARK_VERSION=${SPARK_VERSION:-${GIT_BRANCH#origin/tags/custom-}} # e.g. "2.2.1"

pushd "${SPARK_BUILD_DIR}"
publish_dists
popd
