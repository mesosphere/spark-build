#!/bin/bash

export S3_BUCKET=downloads.mesosphere.io
export S3_PREFIX=spark/assets/

source spark-build/bin/jenkins.sh

rename_dist
upload_to_s3
