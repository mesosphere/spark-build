#!/bin/sh
set -e -u

if [[ -n "${SSH_PRIVATE_KEY_FILE:-}" ]]; then
  echo "SSH_PRIVATE_KEY_FILE provided"
  eval $(ssh-agent | head -2)
  echo "adding ${SSH_PRIVATE_KEY_FILE}"
  ssh-add "${SSH_PRIVATE_KEY_FILE}"
else
  echo "SSH_PRIVATE_KEY_FILE is not set"
fi

exec terraform "$@"

