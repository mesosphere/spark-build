#!/bin/bash

set +x

BIN_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd $BIN_DIR/..

rm -f dcos-spark/dcos-spark*
rm -rf python/build/ python/dist/ python/bin_wrapper.egg-info/
