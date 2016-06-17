#!/bin/bash

set -eux -o pipefail

export S3_BUCKET=downloads.mesosphere.io
export S3_PREFIX=spark/assets/

function publish {
    local VERSION=${GIT_BRANCH#refs/tags/private-}

    # rename to spark-<tag>
    tar xvf spark-*.tgz
    rm spark-*.tgz
    mv spark-* spark-${VERSION}
    tar czf spark-${VERSION}.tgz spark-${VERSION}

    # publish
    aws s3 cp \
        --acl public-read \
        spark-${VERSION}.tgz \
        "s3://${S3_BUCKET}/${S3_PREFIX}spark-${VERSION}.tgz"
}


pushd spark
publish
popd
