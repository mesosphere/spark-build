#!/usr/bin/env bash

# Builds and uploads:
#   - CLI to S3
#   - Spark docker image to dockerhub
#   - stub universe zip to S3
#
# Manifest config:
#   cli_version - version label to use for CLI package
#   spark_uri - where fetch spark distribution from (or SPARK_DIST_URI if provided)
#
# ENV vars:
#   COMMONS_TOOLS_DIR - path to dcos-commons/tools/, or empty to fetch latest release tgz
#   DOCKER_IMAGE - "<image>:<version>", falls back to mesosphere/spark-dev:COMMIT)
#   ghprbActualCommit / GIT_COMMIT - COMMIT value to use for DOCKER_IMAGE, if DOCKER_IMAGE isn't specified

set -e -x -o pipefail

BIN_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
BASEDIR="${BIN_DIR}/.."

configure_env() {
    if [ -z "${SPARK_DIST_URI}" ]; then
        SPARK_DIST_URI=$(cat $BASEDIR/manifest.json | jq .spark_uri)
        SPARK_DIST_URI="${SPARK_DIST_URI%\"}"
        SPARK_DIST_URI="${SPARK_DIST_URI#\"}"
        echo "Using Spark dist URI: $SPARK_DIST_URI"
    fi

    if [ -z "${CLI_VERSION}" ]; then
        CLI_VERSION=$(cat $BASEDIR/manifest.json | jq .cli_version)
        CLI_VERSION="${CLI_VERSION%\"}"
        CLI_VERSION="${CLI_VERSION#\"}"
        echo "Using CLI Version: $CLI_VERSION"
    fi

    if [ -z "$DOCKER_IMAGE" ]; then
        # determine image label based on git commit:
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
        DOCKER_IMAGE="mesosphere/spark-dev:$GIT_COMMIT"
        echo "Using Docker image: $DOCKER_IMAGE"
    fi
}

fetch_commons_tools() {
    if [ -z "${COMMONS_TOOLS_DIR}" ]; then
        pushd ${BIN_DIR}
        rm -rf dcos-commons-tools/ && curl https://infinity-artifacts.s3.amazonaws.com/dcos-commons-tools.tgz | tar xz
        popd
        export COMMONS_TOOLS_DIR=${BIN_DIR}/dcos-commons-tools/
    fi
}

notify_github() {
    ${COMMONS_TOOLS_DIR}/github_update.py $1 build $2
}

build_cli() {
    notify_github pending "Building CLI"
    CLI_VERSION=$CLI_VERSION make --directory=$BASEDIR/cli env test packages
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
    TEMPLATE_PACKAGE_VERSION=${VERSION} \
    ARTIFACT_DIR="https://downloads.mesosphere.com/spark/assets" \
    S3_URL="s3://${S3_BUCKET}/${S3_PREFIX}" \
        ${COMMONS_TOOLS_DIR}/ci_upload.py \
            spark \
            ${BASEDIR}/package/ \
            ${BASEDIR}/cli/dist/*.whl
}

# set CLI_VERSION, SPARK_URI, and DOCKER_IMAGE:
configure_env

fetch_commons_tools

build_cli
build_push_docker
notify_github success "Build succeeded"

upload_cli_and_stub_universe
