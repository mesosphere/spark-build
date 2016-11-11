#!/bin/bash
# Builds a spark distribution

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

source "${DIR}/jenkins.sh"
make_distribution
