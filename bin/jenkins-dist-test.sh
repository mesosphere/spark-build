#!/bin/bash

export S3_BUCKET=spark-build
export S3_PREFIX=
export AWS_ACCESS_KEY_ID=${DEV_AWS_ACCESS_KEY_ID}
export AWS_SECRET_ACCESS_KEY=${DEV_SECRET_ACCESS_KEY}
export DOCKER_IMAGE=mesosphere/spark-dev:${GIT_COMMIT}

source spark-build/bin/jenkins.sh

upload_distribution
spark_test
