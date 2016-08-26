#!/bin/bash

set -ex
set -o pipefail

function make_distribution {
    # ./build/sbt assembly
    pushd spark

    if [[ -n "${SPARK_DIST_URI}" ]]; then
        wget "${SPARK_DIST_URI}"
    else
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
    fi

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

    # update manifest.sh with new spark dist:
    SPARK_DIST=$(ls ../spark/spark*.tgz)
    sed -i "s,export SPARK_DIST_URI=.*,export SPARK_DIST_URI=http://${S3_BUCKET}.s3.amazonaws.com/${S3_PREFIX}$(basename ${SPARK_DIST}),g" manifest.sh

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
    # in CI environments, ci_test.py creates a 'stub-universe.properties' file
    # grab the STUB_UNIVERSE_URL from the file for use by test.sh:
    export $(cat $WORKSPACE/stub-universe.properties)
    # run tests against build artifacts:
    CLUSTER_NAME=spark-package-${BUILD_NUMBER} \
                TEST_RUNNER_DIR=$(pwd)/../mesos-spark-integration-tests/test-runner/ \
                DCOS_CHANNEL=testing/master \
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
