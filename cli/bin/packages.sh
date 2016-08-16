#!/bin/bash -e

BASEDIR=`dirname $0`/..

if [ -n "$CLI_VERSION" ]; then
    echo "Using CLI Version: $CLI_VERSION"
    echo "version = '${CLI_VERSION}'" > $BASEDIR/dcos_spark/version.py
fi

echo "Building wheel..."
"$BASEDIR/env/bin/python" setup.py bdist_wheel

echo "Building egg..."
"$BASEDIR/env/bin/python" setup.py sdist
