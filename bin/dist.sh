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

set -e -x -o pipefail

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
SPARK_DIR="${DIR}/../../spark"

source "${DIR}/jenkins.sh"

make_distribution
upload_to_s3

SPARK_FILENAME=$(basename $(ls ${SPARK_DIR}/spark*.tgz))
SPARK_DIST_URI="http://${S3_BUCKET}.s3.amazonaws.com/${S3_PREFIX}/${SPARK_FILENAME}"
echo "SPARK_DIST_URI=${SPARK_DIST_URI}" > spark_dist_uri.properties
