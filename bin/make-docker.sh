#!/usr/bin/env bash

# Usage:
# ./bin/make-docker.sh <spark-dist-dir> <image>

rm -rf build/docker
mkdir -p build/docker/dist
cp -r "$1/." build/docker/dist
cp -r conf/* build/docker/dist/conf
cp -r docker/* build/docker

pushd build/docker
docker build -t $2 .
popd
