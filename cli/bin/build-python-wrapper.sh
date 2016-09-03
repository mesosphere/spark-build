#!/bin/bash

set +x

BIN_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd $BIN_DIR/../python/

print_file() {
    # Only show 'file <filename>' if that utility is available: often missing in CI builds.
    if [ -n "$(which file)" ]; then
        file "$1"
    fi
    ls -l "$1"
    echo ""
}

python setup.py bdist_wheel
print_file dist/*.whl
