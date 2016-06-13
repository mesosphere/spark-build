#!/usr/bin/env bash

set -e -o pipefail

# ENV vars:
#   DOCKER_IMAGE - <image>:<version>
#   SPARK_DIST_URI (default: manifest.json "spark_uri" value) - e.g. http://<domain>/spark-1.2.3.tgz

if [ -z "${SPARK_DIST_URI}" ]; then
    SPARK_URI=$(cat manifest.json | jq .spark_uri)
    SPARK_URI="${SPARK_URI%\"}"
    SPARK_URI="${SPARK_URI#\"}"
    SPARK_DIST_URI=${SPARK_URI}
fi

DIST_TGZ=$(basename "${SPARK_DIST_URI}")
DIST="${DIST_TGZ%.*}"

# fetch spark
mkdir -p build/dist
[ -f "build/dist/${DIST_TGZ}" ] || curl -o "build/dist/${DIST_TGZ}" "${SPARK_DIST_URI}"
tar xvf build/dist/spark*.tgz -C build/dist

# create docker context
rm -rf build/docker
mkdir -p build/docker/dist
cp -r "build/dist/${DIST}/." build/docker/dist
cp -r conf/* build/docker/dist/conf
cp -r docker/* build/docker

# build docker
(cd build/docker && docker build -t "${DOCKER_IMAGE}" .)

# push docker
docker push "${DOCKER_IMAGE}"
