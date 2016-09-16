#!/bin/bash

export VERSION=${ghprbActualCommit}
if [ -z "$VERSION" ]; then
    export VERSION=${GIT_COMMIT}
fi

export DOCKER_IMAGE=mesosphere/spark-dev:${VERSION}

export S3_BUCKET=infinity-artifacts
export S3_PREFIX=autodelete7d/spark/${VERSION}
# fill in any missing DEV_* AWS envvars required by test.sh:
if [ -z "$DEV_S3_BUCKET" ]; then
    export DEV_S3_BUCKET=$S3_BUCKET
fi
if [ -z "$DEV_S3_PREFIX" ]; then
    export DEV_S3_PREFIX=$S3_PREFIX
fi
if [ -z "$DEV_AWS_ACCESS_KEY_ID" ]; then
    export DEV_AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY_ID
fi
if [ -z "$DEV_AWS_SECRET_ACCESS_KEY" ]; then
    export DEV_AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY
fi

source spark-build/bin/jenkins.sh

spark_test
