#!/usr/bin/env bash

# Builds and uploads:
#   - CLI to S3
#   - Spark docker image to dockerhub
#   - stub universe zip to S3
#
# Manifest config:
#   CLI_VERSION - version label to use for CLI package
#   SPARK_DIST_URI - where fetch spark distribution from
#
# ENV vars:
#   DOCKER_IMAGE - <image>:<version> (or mesosphere/spark-dev:COMMIT)
#   ghprbActualCommit / GIT_COMMIT - COMMIT value to use for DOCKER_IMAGE, if DOCKER_IMAGE isn't specified

set +e

BIN_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
BASEDIR="${BIN_DIR}/.."

configure_docker_image() {
    if [ -z "$DOCKER_IMAGE" ]; then
        # determine image label based on git commit:
        if [ -n "$ghprbActualCommit" ]; then
            # always overrides default GIT_COMMIT:
            export GIT_COMMIT=$ghprbActualCommit
        fi
        if [ -z "$GIT_COMMIT" ]; then
            # Commit not explicitly provided by CI. Fetch directly from Git:
            export GIT_COMMIT="$(git rev-parse HEAD)"
        fi
        if [ -z "$GIT_COMMIT" ]; then
            echo "Unable to determine git commit. Giving up."
            exit 1
        fi
        export DOCKER_IMAGE="mesosphere/spark-dev:$GIT_COMMIT"
    fi
}

fetch_commons_tools() {
    pushd ${BIN_DIR}
    rm -rf dcos-commons-tools/ && curl https://infinity-artifacts.s3.amazonaws.com/dcos-commons-tools.tgz | tar xz
    popd
}

notify_github() {
    ${BIN_DIR}/dcos-commons-tools/github_update.py $1 build $2
}

build_cli() {
    notify_github pending "Building CLI"
    make --directory=$BASEDIR/cli env test packages
    if [ $? -ne 0 ]; then
        notify_github failure "CLI build failed"
        exit 1
    fi
}

build_push_docker() {
    echo "###"
    echo "# Using docker image: $DOCKER_IMAGE"
    echo "###"
    notify_github pending "Building Docker: $DOCKER_IMAGE"
    $BIN_DIR/make-docker.sh
    if [ $? -ne 0 ]; then
        notify_github failure "Docker build failed"
        exit 1
    fi
}

upload_cli_and_stub_universe() {
    # Build/upload package using custom template parameters: TEMPLATE_X_Y_Z => {{x-y-z}}
    TEMPLATE_SPARK_DIST_URI=${SPARK_DIST_URI} \
    TEMPLATE_DOCKER_IMAGE=${DOCKER_IMAGE} \
    TEMPLATE_CLI_VERSION=${CLI_VERSION} \
        ${BIN_DIR}/dcos-commons-tools/ci_upload.py \
            spark \
            ${BASEDIR}/package/ \
            ${BASEDIR}/cli/dist/*.whl
}

# set CLI_VERSION, SPARK_DIST_URI:
source $BASEDIR/manifest.sh
# set DOCKER_IMAGE:
configure_docker_image

fetch_commons_tools

build_cli
build_push_docker
notify_github success "Build succeeded"

upload_cli_and_stub_universe
