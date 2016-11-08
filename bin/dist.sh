#!/bin/bash
#
# 1. Builds a spark distribution
# 2. Uploads it to S3
# 3. Creates a properties file spark_dist_uri.properties containing the URL of the distribution.

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
SPARK_DIR="${DIR}/../../spark"

check_env() {
    # Check env early, before starting the cluster:
    if [ -z "$S3_BUCKET" -o -z "${S3_PREFIX+x}" ]; then
        echo "Missing required env. See check in ${BIN_DIR}/dist.sh."
        env
        exit 1
    fi
}

function write_properties() {
    SPARK_FILENAME=$(basename $(ls ${SPARK_DIR}/spark*.tgz))
    SPARK_DIST_URI="http://${S3_BUCKET}.s3.amazonaws.com/${S3_PREFIX}/spark/${GIT_COMMIT}/${SPARK_FILENAME}"
    echo "SPARK_DIST_URI=${SPARK_DIST_URI}" > spark_dist_uri.properties
}

check_env
source "${DIR}/jenkins.sh"
make_distribution
upload_to_s3
write_properties
