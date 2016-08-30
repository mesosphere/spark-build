#!/bin/bash -e

set -eux

BASEDIR=`dirname $0`/..

rm -rf $BASEDIR/.tox $BASEDIR/env $BASEDIR/build $BASEDIR/dist
echo "Deleted virtualenv and test artifacts."
