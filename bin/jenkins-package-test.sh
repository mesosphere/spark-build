#!/bin/bash

set -e -x -o pipefail

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
SPARK_BUILD_DIR=${DIR}/..

function run() {
    source bin/jenkins.sh
    docker_login
    make universe
    export $(cat "${WORKSPACE}/stub-universe.properties")
    make test
}

pushd "${SPARK_BUILD_DIR}"
run
popd
