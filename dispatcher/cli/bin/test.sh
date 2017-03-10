#!/bin/bash -e

BASEDIR=`dirname $0`/..

cd $BASEDIR

# no idea why this is necessary
# PATH=$(pwd)/dist:$PATH
$BASEDIR/env/bin/tox
