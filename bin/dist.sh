#!/bin/bash

# Builds a spark distribution.
#
# Assumes: Spark source directory exists at "../../spark".
# Output: build/spark/spark-XYZ.tgz

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

source "${DIR}/jenkins.sh"
make_distribution
