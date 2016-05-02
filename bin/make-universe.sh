#!/usr/bin/env bash

# creates
# - build/spark-universe
# - build/spark-universe.zip

set -x -e

rm -rf build/spark-universe*

# make spark package
# TODO(mgummelt): remove this after some time
# ./bin/make-package.py

# download universe
wget -O build/spark-universe.zip https://github.com/mesosphere/universe/archive/version-2.x.zip
unzip -d build build/spark-universe.zip
mv build/universe-version-2.x build/spark-universe
rm build/spark-universe.zip

# make new universe
SPARK_DIR=build/spark-universe/repo/packages/S/spark
rm -rf ${SPARK_DIR}/*
cp -r build/package ${SPARK_DIR}/0

pushd build/spark-universe
./scripts/build.sh
popd

if [ -x "$(command -v zip)" ]; then
    (cd build && zip -r spark-universe.zip spark-universe)
else
    # TODO: remove the docker wrapper once `zip` is available on TC
    docker run -v $(pwd)/build/:/build/ ubuntu:latest sh -c "apt-get update && apt-get install -y zip && cd /build/ && zip -r spark-universe.zip spark-universe"
fi
