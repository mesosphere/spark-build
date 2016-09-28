#!/bin/bash

set -e -x -o pipefail

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
SPARK_BUILD_DIR=${DIR}/..

source spark-build/bin/jenkins.sh

pushd "${SPARK_BUILD_DIR}"
install_cli
docker_login
make universe
cp ../stub-universe.properties ../build.properties
VERSION=${GIT_BRANCH#origin/tags/}
echo "RELEASE_VERSION=${VERSION}" >> ../build.properties
echo "RELEASE_DOCKER_IMAGE=mesosphere/spark:${VERSION}" >> ../build.properties
popd
