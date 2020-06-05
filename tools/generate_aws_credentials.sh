#!/usr/bin/env bash
set -e -u

DEFAULT_CREDENTIALS_FILE="${HOME:-}/.aws/credentials"
AWS_SHARED_CREDENTIALS_FILE="${1-}"
AWS_PROFILE="${2-default}"



if [[ -f "${DEFAULT_CREDENTIALS_FILE}" ]]; then
    echo "Using existing user credentials file ${DEFAULT_CREDENTIALS_FILE}"
    cp -f -a ${DEFAULT_CREDENTIALS_FILE} ${AWS_SHARED_CREDENTIALS_FILE}
else
    echo "Default AWS credentials file doesn't exist, trying environment variables"
    if [[ ! -z "${AWS_ACCESS_KEY_ID:-}" && ! -z "${AWS_SECRET_ACCESS_KEY:-}" ]]; then
        echo "AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY available, generating credentials file"
        cat >${AWS_SHARED_CREDENTIALS_FILE} <<EOF
[${AWS_PROFILE}]
aws_access_key_id     = ${AWS_ACCESS_KEY_ID}
aws_secret_access_key = ${AWS_SECRET_ACCESS_KEY}
EOF
    else
        echo "ERROR: Neither AWS credentials file nor environment variables are present"
        exit 1
    fi
fi

