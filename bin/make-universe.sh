#!/usr/bin/env bash

# creates /tmp/spark-universe.zip

set -x -e

rm -rf build/spark-universe*

# make spark package
./bin/make-package.py

# download universe
wget -O build/spark-universe.zip https://github.com/mesosphere/universe/archive/version-1.x.zip
unzip -d build/spark-universe build/spark-universe.zip
rm build/spark-universe.zip

# make new universe
SPARK_DIR=build/spark-universe/universe-version-1.x/repo/packages/S/spark
rm -rf ${SPARK_DIR}/*
mkdir ${SPARK_DIR}/0
cp -r build/package ${SPARK_DIR}/0
