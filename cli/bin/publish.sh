#!/bin/bash

# env vars
#   PLATFORM (e.g. linux-x86-64)

set -ex -o pipefail

export VERSION="${GIT_BRANCH#refs/tags/}"
export S3_URL="s3://downloads.mesosphere.io/spark/assets/cli/${VERSION}/${PLATFORM}/dcos-spark"

echo -e "version = '${VERSION}'\n" > dcos_spark/version.py
make clean binary
aws s3 cp dist/dcos-spark "${S3_URL}"
