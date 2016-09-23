#!/bin/bash

set -e -x -o pipefail

# export S3_BUCKET=infinity-artifacts
# export S3_PREFIX=spark/
# export DOCKER_IMAGE=mesosphere/spark-dev:${GIT_COMMIT}
# export AWS_ACCESS_KEY_ID=${DEV_AWS_ACCESS_KEY_ID}
# export AWS_SECRET_ACCESS_KEY=${DEV_AWS_SECRET_ACCESS_KEY}

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
SPARK_BUILD_DIR=${DIR}/..

pushd "${SPARK_BUILD_DIR}"

source bin/jenkins.sh

install_cli
make dist && export $(cat spark_dist_uri.properties)
make universe && export $(cat $stub-universe.properties)
make test

popd
