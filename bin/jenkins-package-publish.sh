#!/bin/bash

set -e -x -o pipefail

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
SPARK_BUILD_DIR=${DIR}/..

source spark-build/bin/jenkins.sh

pushd "${SPARK_BUILD_DIR}"
make universe
cp ../stub_universe.properties ../build.propertes
echo "RELEASE_VERSION=${GIT_BRANCH#refs/tags/}" >> ../build.properties
popd
