#!/usr/bin/env bash

# Prevent jenkins from immediately killing the script when a step fails, allowing us to notify github:
set +e

BIN_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
BASEDIR="${BIN_DIR}/.."
cd $BIN_DIR

# Env config:
source $BASEDIR/manifest.sh
if [ -n "$ghprbActualCommit" ]; then
    # always overrides default GIT_COMMIT:
    GIT_COMMIT=$ghprbActualCommit
fi
if [ -z "$GIT_COMMIT" ]; then
    # Commit not explicitly provided by CI. Fetch directly from Git:
    GIT_COMMIT="$(git rev-parse HEAD)"
fi
if [ -z "$GIT_COMMIT" ]; then
    echo "Unable to determine git commit. Giving up."
    exit 1
fi
if [ -z "$DOCKER_IMAGE" ]; then
    export DOCKER_IMAGE="mesosphere/spark-dev:$GIT_COMMIT"
fi

# Grab dcos-commons build/release tools:
rm -rf dcos-commons-tools/ && curl https://infinity-artifacts.s3.amazonaws.com/dcos-commons-tools.tgz | tar xz

# GitHub notifier config
_notify_github() {
    ${BIN_DIR}/dcos-commons-tools/github_update.py $1 build $2
}

# Build CLI (creates .whl package referenced below):

_notify_github pending "Building CLI"
make --directory=$BASEDIR/cli env test packages
if [ $? -ne 0 ]; then
    _notify_github failure "CLI build failed"
    exit 1
fi

# Build/push Docker image:
_notify_github pending "Building Docker"
echo "###"
echo "# Using docker image: $DOCKER_IMAGE"
echo "###"
./make-docker.sh
if [ $? -ne 0 ]; then
  _notify_github failure "Docker build failed"
  exit 1
fi

# Build/upload package using custom template parameters: TEMPLATE_X_Y_Z => {{x-y-z}}
TEMPLATE_SPARK_DIST_URI=${SPARK_DIST_URI} \
TEMPLATE_DOCKER_IMAGE=${DOCKER_IMAGE} \
TEMPLATE_CLI_VERSION=${CLI_VERSION} \
${BIN_DIR}/dcos-commons-tools/ci_upload.py \
    spark \
    ${BASEDIR}/package/ \
    ${BASEDIR}/cli/dist/*.whl
