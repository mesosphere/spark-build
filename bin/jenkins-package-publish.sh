#!/bin/bash

export VERSION=${GIT_BRANCH#refs/tags/}
export S3_BUCKET=downloads.mesosphere.io
export S3_PREFIX=spark/assets/
export DEV_S3_BUCKET=infinity-artifacts
export DEV_S3_PREFIX=autodelete7d/spark/
export DOCKER_IMAGE=mesosphere/spark:${VERSION}

source spark-build/bin/jenkins.sh

spark_test
