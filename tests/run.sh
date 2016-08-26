#! /bin/bash

set -e -u -x

virtualenv env
source env/bin/activate
pip install
