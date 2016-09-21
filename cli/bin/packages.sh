#!/bin/bash -e

BIN_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
BASEDIR="${BIN_DIR}/.."

if [ -n "$CLI_VERSION" ]; then
    echo "Using CLI Version: $CLI_VERSION (default $(cat $BASEDIR/dcos_spark/version.py)"
    echo "version = '${CLI_VERSION}'" > $BASEDIR/dcos_spark/version.py
fi

echo "Building wheel..."
"$BASEDIR/env/bin/python" setup.py bdist_wheel

echo "Building egg..."
"$BASEDIR/env/bin/python" setup.py sdist
