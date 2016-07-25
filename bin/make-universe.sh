#!/usr/bin/env bash

# 1) publishes universe docker image at DOCKER_IMAGE:DOCKER_TAG
# 2) creates universe app at ./build/spark-universe/docker/server/target/marathon.json

set -x -e

rm -rf build/spark-universe*

# download universe
UNIVERSE_BRANCH=version-3.x
wget -O build/spark-universe.zip "https://github.com/mesosphere/universe/archive/${UNIVERSE_BRANCH}.zip"
unzip -d build build/spark-universe.zip
mv "build/universe-${UNIVERSE_BRANCH}" build/spark-universe
rm build/spark-universe.zip

# make new universe
SPARK_DIR=build/spark-universe/repo/packages/S/spark
rm -rf "${SPARK_DIR}"/*
cp -r build/package "${SPARK_DIR}/0"

# build universe docker image
pushd build/spark-universe
./scripts/build.sh
DOCKER_TAG=spark-$(openssl rand -hex 8)
DOCKER_TAG="${DOCKER_TAG}" ./docker/server/build.bash
DOCKER_TAG="${DOCKER_TAG}" ./docker/server/build.bash publish
popd
