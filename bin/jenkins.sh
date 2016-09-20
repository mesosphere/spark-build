#!/bin/bash

set -ex
set -o pipefail

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
SPARK_DIR="${DIR}/../../spark"
SPARK_BUILD_DIR="${DIR}/.."

export TEST_JAR_PATH=$(pwd)/mesos-spark-integration-tests-assembly-0.1.0.jar
export COMMONS_TOOLS_DIR=$(pwd)/dcos-commons/tools/
export CCM_TEMPLATE=single-master.cloudformation.json

function make_distribution {
    pushd "${SPARK_DIR}"

    if [[ -n "${SPARK_DIST_URI}" ]]; then
        wget "${SPARK_DIST_URI}"
    else
        if [ -f make-distribution.sh ]; then
            ./make-distribution.sh -Phadoop-2.4 -DskipTests
        else
            ./dev/make-distribution.sh -Pmesos -Phadoop-2.6 -DskipTests
        fi

        local DIST="spark-${GIT_COMMIT}"
        mv dist ${DIST}
        tar czf ${DIST}.tgz ${DIST}
    fi

    popd
}

# rename spark/spark-<SHA1>.tgz to spark/spark-<TAG>.tgz
function rename_dist {
    pushd "${SPARK_DIR}"

    local VERSION=${GIT_BRANCH#refs/tags/private-}

    # rename to spark-<tag>
    tar xvf spark-*.tgz
    rm spark-*.tgz
    mv spark-* spark-${VERSION}
    tar czf spark-${VERSION}.tgz spark-${VERSION}

    popd
}

function upload_to_s3 {
    pushd "${SPARK_DIR}"

    aws --debug s3 cp \
        --acl public-read \
        spark-*.tgz \
        "s3://${S3_BUCKET}/${S3_PREFIX}"

    popd
}

function update_manifest {
    pushd "${SPARK_BUILD_DIR}"

    # update manifest.json with new spark dist:
    SPARK_DIST=$(ls ../spark/spark*.tgz)
    SPARK_URI="http://${S3_BUCKET}.s3.amazonaws.com/${S3_PREFIX}$(basename ${SPARK_DIST})"
    cat manifest.json | jq ".spark_uri=\"${SPARK_URI}\"" > manifest.json.tmp
    mv manifest.json.tmp manifest.json

    popd
}

function install_cli {
    curl -O https://downloads.mesosphere.io/dcos-cli/install.sh
    rm -rf cli/
    mkdir cli
    bash install.sh cli http://change.me --add-path no
    source cli/bin/env-setup

    # hack because the installer forces an old CLI version
    pip install -U dcoscli

    # needed in `make test`
    pip3 install jsonschema
}

function docker_login {
    docker login --email=docker@mesosphere.io --username="${DOCKER_USERNAME}" --password="${DOCKER_PASSWORD}"
}

function spark_test {
    install_cli

    pushd spark-build
    docker_login
    # build/upload artifacts: docker + cli + stub universe:
    make build
    # in CI environments, ci_upload.py creates a 'stub-universe.properties' file
    # grab the STUB_UNIVERSE_URL from the file for use by test.sh:
    export $(cat $WORKSPACE/stub-universe.properties)
    # run tests against build artifacts:
    CLUSTER_NAME=spark-package-${BUILD_NUMBER} \
                TEST_DIR=$(pwd)/../mesos-spark-integration-tests/ \
                S3_BUCKET=${DEV_S3_BUCKET} \
                S3_PREFIX=${DEV_S3_PREFIX} \
                make test
    popd
}

function upload_distribution {
    make_distribution
    upload_to_s3
    update_manifest
}
