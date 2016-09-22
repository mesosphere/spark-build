#!/bin/bash
#
# Builds spark, and creates a properties file spark_dist_uri.properties
# containing the URL of the distribution.
#
# Env vars:
#   S3_BUCKET
#   S3_PREFIX
#   AWS_ACCESS_KEY_ID
#   AWS_SECRET_ACCESS_KEY
#   GIT_COMMIT

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

source "${DIR}/jenkins.sh"

make_distribution
upload_to_s3

SPARK_DIST_URI="http://${S3_BUCKET}.s3.amazonaws.com/${S3_PREFIX}spark-${GIT_COMMIT}.tgz"
echo "${SPARK_DIST_URI}" > spark_dist_uri
