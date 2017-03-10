#!/usr/bin/env bash

# Builds and pushes a Spark docker image
#
# ENV vars:
#   DOCKER_IMAGE - <image>:<version>
#   SPARK_DIST_URI (default: manifest.json "spark_uri" value) - e.g. http://<domain>/spark-1.2.3.tgz

set -x -e -o pipefail

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
SPARK_BUILD_DIR="${DIR}/.."

function fetch_spark() {
    rm -rf build/dist
    mkdir -p build/dist
    curl -o "build/dist/${DIST_TGZ}" "${SPARK_DIST_URI}"
    tar xvf "build/dist/${DIST_TGZ}" -C build/dist
}

function create_docker_context {
    fetch_spark

    rm -rf build/docker
    mkdir -p build/docker/dist
    cp -r "build/dist/${DIST}/." build/docker/dist
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

if [ -z "${SPARK_DIST_URI}" ]; then
    SPARK_DIST_URI=$(jq -r ".default_spark_dist.uri" manifest.json)
fi

DIST_TGZ=$(basename "${SPARK_DIST_URI}")
DIST="${DIST_TGZ%.*}"

pushd "${SPARK_BUILD_DIR}"
create_docker_context
build_docker
push_docker
popd
