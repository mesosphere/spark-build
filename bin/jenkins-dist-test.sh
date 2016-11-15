#!/bin/bash

set -e -x -o pipefail

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
SPARK_BUILD_DIR="${DIR}/.."
SPARK_DIR="${DIR}/../../spark"

function run() {
    source bin/jenkins.sh
    install_cli
    docker_login
    build_and_test
}

pushd "${SPARK_BUILD_DIR}"
run
popd
