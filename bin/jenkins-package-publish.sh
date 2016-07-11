#!/bin/bash

export S3_BUCKET=infinity-artifacts
export S3_PREFIX=spark/
export DOCKER_IMAGE=mesosphere/spark:${GIT_BRANCH#refs/tags/}

source spark-build/bin/jenkins.sh

spark_test
