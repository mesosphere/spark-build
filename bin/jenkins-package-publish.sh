#!/bin/bash

export VERSION=${GIT_BRANCH#refs/tags/}
export S3_BUCKET=infinity-artifacts
export S3_PREFIX=spark/
export DOCKER_IMAGE=mesosphere/spark:${VERSION}

source spark-build/bin/jenkins.sh

spark_test
