#!/bin/bash

set -e -x -o pipefail

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
SPARK_BUILD_DIR=${DIR}/..

source spark-build/bin/jenkins.sh

pushd "${SPARK_BUILD_DIR}"
install_cli
docker_login
make universe
cp ../stub_universe.properties ../build.propertes
VERSION=${GIT_BRANCH#refs/tags/}
echo "RELEASE_VERSION=${VERSION}" >> ../build.properties
echo "DOCKER_IMAGE=mesosphere/spark:${VERSION}" >> ../build.properties
popd
