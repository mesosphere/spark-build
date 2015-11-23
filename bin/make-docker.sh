#!/usr/bin/env bash

# Usage:
# ./bin/make-docker.sh <spark-dist-dir> <image>

rm -rf build/docker
mkdir -p build/docker
cp -r $1* build/docker
cp docker/* build/docker

pushd build/docker
docker build -t $2 .
popd
