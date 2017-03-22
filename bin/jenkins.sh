#!/bin/bash

set -e -x
set -o pipefail

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
SPARK_DIR="${DIR}/../../spark"
SPARK_BUILD_DIR="${DIR}/../../spark-build"

function default_hadoop_version {
    jq -r ".default_spark_dist.hadoop_version" "${SPARK_BUILD_DIR}/manifest.json"
}

function default_spark_dist {
    jq -r ".default_spark_dist.uri" "${SPARK_BUILD_DIR}/manifest.json"
}

function make_distribution {
    local HADOOP_VERSION=${HADOOP_VERSION:-$(default_hadoop_version)}
    pushd "${SPARK_DIR}"

    rm -rf spark-*.tgz

    if [[ -n "${SPARK_DIST_URI}" ]]; then
        wget "${SPARK_DIST_URI}"
    elif [[ -n "${DEV}" ]]; then
        make_dev_distribution
    else
        make_prod_distribution
    fi

    popd
}

# Adapted from spark/dev/make-distribution.sh.
#
# Some python/R code from make-distribution.sh has not been included,
# so this distribution may not work with python/R.
function make_dev_distribution {
    pushd "${SPARK_DIR}"
    rm -rf spark-*.tgz
    ./build/sbt -Pmesos "-Phadoop-${HADOOP_VERSION}" -Phive -Phive-thriftserver package

    # jars
    rm -rf /tmp/spark-SNAPSHOT*
    mkdir -p /tmp/spark-SNAPSHOT/jars
    cp -r "${SPARK_DIR}"/assembly/target/scala*/jars/* /tmp/spark-SNAPSHOT/jars

    # examples/jars
    mkdir -p /tmp/spark-SNAPSHOT/examples/jars
    cp -r "${SPARK_DIR}"/examples/target/scala*/jars/* /tmp/spark-SNAPSHOT/examples/jars
    # Deduplicate jars that have already been packaged as part of the main Spark dependencies.
    for f in /tmp/spark-SNAPSHOT/examples/jars/*; do
        name=$(basename "$f")
        if [ -f "/tmp/spark-SNAPSHOT/jars/$name" ]; then
            rm "/tmp/spark-SNAPSHOT/examples/jars/$name"
        fi
    done

    # data
    cp -r "${SPARK_DIR}/data" /tmp/spark-SNAPSHOT/

    # conf
    mkdir -p /tmp/spark-SNAPSHOT/conf
    cp "${SPARK_DIR}"/conf/* /tmp/spark-SNAPSHOT/conf
    cp -r "${SPARK_DIR}/bin" /tmp/spark-SNAPSHOT
    cp -r "${SPARK_DIR}/sbin" /tmp/spark-SNAPSHOT
    cp -r "${SPARK_DIR}/python" /tmp/spark-SNAPSHOT

    (cd /tmp && tar czf spark-SNAPSHOT.tgz spark-SNAPSHOT)
    cp /tmp/spark-SNAPSHOT.tgz "${SPARK_DIR}"
    popd
}

function make_prod_distribution {
    if [ -f make-distribution.sh ]; then
        # Spark <2.0
        ./make-distribution.sh --tgz "-Phadoop-${HADOOP_VERSION}" -Phive -Phive-thriftserver -DskipTests
    else
        # Spark >=2.0
        if does_profile_exist "mesos"; then
            MESOS_PROFILE="-Pmesos"
        else
            MESOS_PROFILE=""
        fi
        ./dev/make-distribution.sh --tgz "${MESOS_PROFILE}" "-Phadoop-${HADOOP_VERSION}" -Psparkr -Phive -Phive-thriftserver -DskipTests
    fi
}

# rename spark/spark-*.tgz to spark/spark-<TAG>.tgz
# globals: $SPARK_VERSION
function rename_dist {
    SPARK_DIST_DIR="spark-${SPARK_VERSION}-bin-${HADOOP_VERSION}"
    SPARK_DIST="${SPARK_DIST_DIR}.tgz"

    pushd "${SPARK_DIR}"
    tar xvf spark-*.tgz
    rm spark-*.tgz
    mv spark-* "${SPARK_DIST_DIR}"
    tar czf "${SPARK_DIST}" "${SPARK_DIST_DIR}"
    rm -rf "${SPARK_DIST_DIR}"
    popd
}

# uploads spark/spark-*.tgz to S3
function upload_to_s3 {
    aws s3 cp --acl public-read "${SPARK_DIR}/${SPARK_DIST}" "${S3_URL}"
}

# $1: hadoop version (e.g. "2.6")
function docker_version() {
    echo "${SPARK_BUILD_VERSION}-hadoop-$1"
}

function install_cli {
    curl -O https://downloads.mesosphere.io/dcos-cli/install.sh
    rm -rf dcos-cli/
    mkdir dcos-cli
    bash install.sh dcos-cli http://change.me --add-path no
    source dcos-cli/bin/env-setup

    # hack because the installer forces an old CLI version
    pip install -U dcoscli

    # needed in `make test`
    pip3 install jsonschema
}

function docker_login {
    docker login --email=docker@mesosphere.io --username="${DOCKER_USERNAME}" --password="${DOCKER_PASSWORD}"
}

function set_hadoop_versions {
    HADOOP_VERSIONS=( "2.4" "2.6" "2.7" )
}

function build_and_test() {
    make dist
    SPARK_DIST=$(cd ${SPARK_DIR} && ls spark-*.tgz)
    S3_URL="s3://${S3_BUCKET}/${S3_PREFIX}/spark/${GIT_COMMIT}/" upload_to_s3

    SPARK_DIST_URI="http://${S3_BUCKET}.s3.amazonaws.com/${S3_PREFIX}/spark/${GIT_COMMIT}/${SPARK_DIST}" make --directory=dispatcher universe

    export $(cat "${WORKSPACE}/stub-universe.properties")
    make test
}

# $1: profile (e.g. "hadoop-2.6")
function does_profile_exist() {
    (cd "${SPARK_DIR}" && ./build/mvn help:all-profiles | grep "$1")
}
