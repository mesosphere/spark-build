#!/bin/bash

export S3_BUCKET=spark-build
export S3_PREFIX=
export DOCKER_IMAGE=mesosphere/spark:${GIT_BRANCH#refs/tags/}

source spark-build/bin/jenkins.sh

spark_test
