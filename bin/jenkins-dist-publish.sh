#!/bin/bash

# Env Vars:
#   GIT_BRANCH (assumed to have prefix "refs/tags/custom-")

set -e -x -o pipefail

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
SPARK_BUILD_DIR=${DIR}/..

function run() {
    # test
    source bin/jenkins.sh
    install_cli
    docker_login
    DIST_NAME="spark-${GIT_COMMIT}" make dist && export $(cat spark_dist_uri.properties)
    make universe && export $(cat "${WORKSPACE}/stub-universe.properties")
    make test

    # publish
    rename_dist
    AWS_ACCESS_KEY_ID=${PROD_AWS_ACCESS_KEY_ID} \
                     AWS_SECRET_ACCESS_KEY=${PROD_AWS_SECRET_ACCESS_KEY} \
                     S3_BUCKET=${PROD_S3_BUCKET} \
                     S3_PREFIX=${PROD_S3_PREFIX} \
                     upload_to_s3
}

pushd "${SPARK_BUILD_DIR}"
run
popd
