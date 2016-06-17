#!/bin/bash

export S3_BUCKET=downloads.mesosphere.io
export S3_PREFIX=spark/assets/
export AWS_ACCESS_KEY_ID=${PROD_AWS_ACCESS_KEY_ID}
export AWS_SECRET_ACCESS_KEY=${PROD_SECRET_ACCESS_KEY}

source spark-build/bin/jenkins.sh

rename_dist
upload_to_s3
