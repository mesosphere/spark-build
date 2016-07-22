#!/bin/bash

export S3_BUCKET=infinity-artifacts
export S3_PREFIX=spark/
export DOCKER_IMAGE=mesosphere/spark-dev:${GIT_COMMIT}
export AWS_ACCESS_KEY_ID=${DEV_AWS_ACCESS_KEY_ID}
export AWS_SECRET_ACCESS_KEY=${DEV_AWS_SECRET_ACCESS_KEY}

source spark-build/bin/jenkins.sh

upload_distribution
spark_test
