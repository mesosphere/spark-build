#!/bin/bash

set -ex
set -o pipefail

function make_distribution {
    # ./build/sbt assembly
    pushd spark

    if [ -f make-distribution.sh ]; then
        ./make-distribution.sh -Phadoop-2.4 -DskipTests
    else
        ./dev/make-distribution.sh -Phadoop-2.4 -DskipTests
    fi

    # tmp
    #wget http://spark-build.s3.amazonaws.com/spark-0738bc281ea93f09c541e47d61b98fe7babc74e0.tgz
    #tar xvf spark-0738bc281ea93f09c541e47d61b98fe7babc74e0.tgz
    #rm spark-0738bc281ea93f09c541e47d61b98fe7babc74e0.tgz
    #mv spark-0738bc281ea93f09c541e47d61b98fe7babc74e0 dist

    local DIST="spark-${GIT_COMMIT}"
    mv dist ${DIST}
    tar czf ${DIST}.tgz ${DIST}

    popd
}

# rename spark/spark-<SHA1>.tgz to spark/spark-<TAG>.tgz
function rename_dist {
    pushd spark

    local VERSION=${GIT_BRANCH#refs/tags/private-}

    # rename to spark-<tag>
    tar xvf spark-*.tgz
    rm spark-*.tgz
    mv spark-* spark-${VERSION}
    tar czf spark-${VERSION}.tgz spark-${VERSION}

    popd
}

function upload_to_s3 {
    pushd spark

    aws s3 cp \
        --acl public-read \
        spark-*.tgz \
        "s3://${S3_BUCKET}/${S3_PREFIX}"

    popd
}

function update_manifest {
    pushd spark-build

    # update manifest.json
    SPARK_DIST=$(ls ../spark/spark*.tgz)
    SPARK_URI="http://${S3_BUCKET}.s3.amazonaws.com/${S3_PREFIX}$(basename ${SPARK_DIST})"
    cat manifest.json | jq ".spark_uri=\"${SPARK_URI}\"" > manifest.json.tmp
    mv manifest.json.tmp manifest.json

    popd
}

function install_cli {
    curl -O https://downloads.mesosphere.io/dcos-cli/install.sh
    mkdir cli
    bash install.sh cli http://change.me --add-path no
    source cli/bin/env-setup

    # hack because the installer forces an old CLI version
    pip install -U dcoscli
}

function docker_login {
    docker login --username="${DOCKER_USERNAME}" --password="${DOCKER_PASSWORD}"
}

function spark_test {
    install_cli

    pushd spark-build
    docker_login
    make docker
    CLUSTER_NAME=spark-package-${BUILD_NUMBER} \
                TEST_RUNNER_DIR=$(pwd)/../mesos-spark-integration-tests/test-runner/ \
                DCOS_CHANNEL=testing/continuous \
                DCOS_USERNAME=bootstrapuser \
                DCOS_PASSWORD=deleteme \
                make test
    popd
}

function upload_distribution {
    make_distribution
    upload_to_s3
    update_manifest
}
