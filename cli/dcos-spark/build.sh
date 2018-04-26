#!/usr/bin/env bash
set -e

# Builds the custom CLI used by the Spark service.
# Produces 3 artifacts: dcos-spark[-linux|-darwin|.exe]

CUR_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd $CUR_DIR

# required env:
export REPO_ROOT_DIR=$(dirname $(dirname $CUR_DIR))
export REPO_NAME=$(basename $REPO_ROOT_DIR)
$REPO_ROOT_DIR/tools/build_go_exe.sh cli/dcos-spark/ dcos-spark linux darwin windows
