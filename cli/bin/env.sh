#!/bin/bash

set -ex

BASEDIR=`dirname $0`/..

if [ ! -d "$BASEDIR/env" ]; then
    virtualenv -q $BASEDIR/env --prompt='(dcos-spark) '
    echo "Virtualenv created."
fi

if [ -f "$BASEDIR/env/bin/activate" ]; then
    source $BASEDIR/env/bin/activate
else
    $BASEDIR/env/Scripts/activate
fi

echo "Virtualenv activated."

if [ ! -f "$BASEDIR/env/updated" -o $BASEDIR/setup.py -nt $BASEDIR/env/updated ]; then
    pip install -e $BASEDIR
    touch $BASEDIR/env/updated
    echo "Requirements installed."
fi

pip install -r $BASEDIR/requirements.txt
