#!/usr/bin/env bash

# creates build/spark-universe, build/spark-universe.zip

set -x -e

rm -rf build/spark-universe*

# make spark package
./bin/make-package.py

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

zip -r build/spark-universe.zip build/spark-universe
