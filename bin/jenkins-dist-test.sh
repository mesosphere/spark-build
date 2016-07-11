#!/bin/bash

export S3_BUCKET=infinity-artifacts
export S3_PREFIX=spark/
export DOCKER_IMAGE=mesosphere/spark-dev:${GIT_COMMIT}

source spark-build/bin/jenkins.sh

upload_distribution
spark_test
