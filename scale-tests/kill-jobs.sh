#!/bin/sh

set -x

# Usage: ./kill-jobs.sh [submissions_file]
#
# This script kills app jobs specified in the submissions file.

if [ "$#" -eq 0 ] || [ "$#" -gt 2 ]; then
  echo "Usage: ./kill-jobs.sh [submissions_file]"
  exit 1
fi

readonly SUBMISSIONS_FILE="${1}"
readonly SUBMISSIONS="$(cat "${SUBMISSIONS_FILE}")"

dcos package install spark --cli --yes

for submission in ${SUBMISSIONS}
do
  dispatcher_app_name="$(echo ${submission} | cut -d, -f1)"
  submission_id="$(echo ${submission} | cut -d, -f2)"

  dcos spark --name="${dispatcher_app_name}" kill "${submission_id}"
done
