#!/bin/sh

set -x

# Usage:
#    (1) Login to cluster via "dcos cluster" command.
#    (2) Run this script:
#        ./uninstall-dispatchers.sh [dispatchers_file] [spark_principal]
#
# This script:
# - uninstalls instances of spark listed in an input file.

if [ "$#" -eq 0 ] || [ "$#" -gt 2 ]; then
    echo "Usage: ./uninstall-dispatchers.sh [dispatchers_file] [spark_principal]"
    exit 1
fi

readonly DISPATCHERS_FILE="${1}"
readonly SPARK_PRINCIPAL="${2:-spark_principal}"

readonly ACS_TOKEN="$(dcos config show core.dcos_acs_token)"
readonly PACKAGE_NAME="spark"
readonly DISPATCHERS="$(cat "${DISPATCHERS_FILE}")"

uninstall_service () {
    local service_name="${1}"
    dcos package uninstall --yes "${PACKAGE_NAME}" --app-id="${service_name}"
}

remove_quota () {
    local role="${1}"

    dcos spark quota remove "${role}"
}

janitor_cmd () {
    local service_name="${1}"
    local role="${2}"
    local principal="${3}"
    local zknode="${4}"

    echo "sudo docker run mesosphere/janitor /janitor.py -r ${role} -p \"${principal}\" -z ${zknode} --auth_token=${ACS_TOKEN}"
}

run_leader_cmd () {
    local command="${1}"

    dcos node ssh --leader --user=${DCOS_SSH_USER:-centos} --master-proxy --option='StrictHostKeyChecking=no' "${command}"
}

run_janitor () {
    local service_name="${1}"
    local role="${2}"
    local principal="${3}"
    local unslashed_service_name="$(echo ${service_name} | sed 's/\//__/g')"

    if [ "${role}" = "spark" ]
       local zknode="spark_mesos_dispatcher"
    then
       local zknode="spark_mesos_dispatcher${unslashed_service_name}"
    fi

    local cmd="$(janitor_cmd "${service_name}" "${role}" "${principal}" "${zknode}")"

    run_leader_cmd "${cmd}"
}

for dispatcher in ${DISPATCHERS}
do
    service_name="$(echo ${dispatcher} | cut -d, -f1)"
    dispatcher_role="$(echo ${dispatcher} | cut -d, -f2)"
    driver_role="$(echo ${dispatcher} | cut -d, -f3)"

    uninstall_service "${service_name}"
    dcos package install --yes --cli "${PACKAGE_NAME}"
    remove_quota "${dispatcher_role}"
    remove_quota "${driver_role}"
    dcos package uninstall --cli "${PACKAGE_NAME}"
    run_janitor "${service_name}" "${dispatcher_role}" "${SPARK_PRINCIPAL}"
done
