#!/bin/sh

if [ "$#" -lt 7 ]; then
    echo "Usage: $0 <marathon_app_json_file> <dcos_username> <dcos_password> <input_file_uri> <script_cpus> <script_mem> <script_args>"
    echo "For example: $0 spark-batch-workload.json.template myuser mypass https://bucket.s3.amazonaws.com/dispatchers.out 2 4096" '"dispatchers.out --submits-per-min 1"'
    exit 1
fi

set -x

MARATHON_APP_JSON_FILE=$1
DCOS_USERNAME=$2
DCOS_PASSWORD=$3
INPUT_FILE_URI=$4
SCRIPT_CPUS=$5
SCRIPT_MEM=$6
SCRIPT_ARGS=$7

cat $MARATHON_APP_JSON_FILE | \
    sed 's/{{template-dcos-username}}/'"$DCOS_USERNAME"'/' | \
    sed 's/{{template-dcos-password}}/'"$DCOS_PASSWORD"'/' | \
    sed 's|{{template-input-file-uri}}|'"$INPUT_FILE_URI"'|' | \
    sed 's/{{template-script-cpus}}/'"$SCRIPT_CPUS"'/' |\
    sed 's/{{template-script-mem}}/'"$SCRIPT_MEM"'/' |\
    sed 's/{{template-script-args}}/'"$SCRIPT_ARGS"'/' | \
    dcos marathon app add
