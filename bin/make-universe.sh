#!/usr/bin/env bash

# creates build/spark-universe, build/spark-universe.zip

set -x -e

rm -rf build/spark-universe*

# make spark package
./bin/make-package.py

# download universe
git clone -b version-2.x https://github.com/mesosphere/universe.git build/spark-universe

# make new universe
SPARK_DIR=build/spark-universe/repo/packages/S/spark
rm -rf ${SPARK_DIR}/*
cp -r build/package ${SPARK_DIR}/0

pushd build/spark-universe
./scripts/build.sh
git checkout -b ${GITHUB_USER:-${USER}}
git add *
git commit -m "test build"
popd
