#!/usr/bin/env bash

# 1. builds a docker image
# 2. pushes the docker image
# 3. makes a package
#
# ENV vars:
#   DOCKER_IMAGE - <image>:<version> to build
#   PACKAGE_VERSION (optional) - e.g. 1.6.1

set -x -e


build_docker() {
    mkdir -p build/spark

    SPARK_URI=$(cat manifest.json | jq .spark_uri)
    SPARK_URI="${SPARK_URI%\"}"
    SPARK_URI="${SPARK_URI#\"}"

    pushd build
    wget "${SPARK_URI}"
    tar xvf spark*.tgz -C spark
    popd

    ./bin/make-docker.sh build/spark/spark* ${DOCKER_IMAGE}
    docker push ${DOCKER_IMAGE}
}

build_docker
./bin/make-package.py
