#!/usr/bin/env bash

# 1. builds a docker image from the provided spark distribution
# 2. pushes the docker image
# 3. writes out a manifest file
#
# ENV vars:
#   SPARK_URI - URI of the Spark image to build
#   DOCKER_IMAGE - <image>:<version> to build

set -x -e


build_docker() {
    mkdir -p build/spark
    pushd build
    wget "${SPARK_URI}"
    tar xvf spark*.tgz -C spark
    popd
    ./bin/make-docker.sh build/spark/spark* ${DOCKER_IMAGE}
    docker push ${DOCKER_IMAGE}
}

build_manifest() {
    jq --arg spark_uri ${SPARK_URI} \
       --arg docker_image ${DOCKER_IMAGE} \
       '{python_package, version, "spark_uri": $spark_uri, "docker_image": $docker_image}' \
       manifest.json > manifest.json.tmp
    mv manifest.json.tmp manifest.json
}

build_docker
build_manifest
