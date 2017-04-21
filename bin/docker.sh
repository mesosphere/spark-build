#!/usr/bin/env bash

# Builds and pushes a Spark docker image.
#
# ENV vars:
#   DOCKER_IMAGE - <image>:<version>
#   SPARK_DIST_URI (default: manifest.json "spark_uri" value) - e.g. http://<domain>/spark-1.2.3.tgz

set -x -e -o pipefail

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
SPARK_BUILD_DIR="${DIR}/.."

function create_docker_context {
    tar xvf build/dist/spark-*.tgz -C build/dist

    rm -rf build/docker
    mkdir -p build/docker/dist
    cp -r build/dist/spark-*/. build/docker/dist
    cp -r conf/* build/docker/dist/conf
    cp -r docker/* build/docker
}

function build_docker {
    # build docker
    (cd build/docker && docker build -t "${DOCKER_IMAGE}" .)
}

function push_docker {
    # push docker
    docker push "${DOCKER_IMAGE}"
}

[[ -n "${DOCKER_IMAGE}" ]] || (echo "DOCKER_IMAGE is a required env var." 1>&2; exit 1)

pushd "${SPARK_BUILD_DIR}"
create_docker_context
build_docker
push_docker
popd
