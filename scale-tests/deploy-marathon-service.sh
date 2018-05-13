#!/bin/sh

set -x

if [ "$#" -lt 5 ]; then
    echo "Usage: $0 <marathon_app_json_file> <dcos_username> <dcos_password> <input_file_uri> <script_args>"
    exit 1
fi

MARATHON_APP_JSON_FILE=$1
DCOS_USERNAME=$2
DCOS_PASSWORD=$3
INPUT_FILE_URI=$4
SCRIPT_ARGS=$5

cat $MARATHON_APP_JSON_FILE | \
    sed 's/{template-dcos-username}/'"$DCOS_USERNAME"'/' | \
    sed 's/{template-dcos-password}/'"$DCOS_PASSWORD"'/' | \
    sed 's|{template-input-file-uri}|'"$INPUT_FILE_URI"'|' | \
    sed 's/{template-script-args}/'"$SCRIPT_ARGS"'/' | \
    dcos marathon app add
