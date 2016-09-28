#!/bin/bash

set -e -x -o pipefail

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
SPARK_BUILD_DIR=${DIR}/..

function run() {
    source bin/jenkins.sh
    install_cli
    docker_login
    make dist && export $(cat spark_dist_uri.properties)
    make universe && export $(cat "${WORKSPACE}/stub-universe.properties")
    make test
}

pushd "${SPARK_BUILD_DIR}"
run
popd
