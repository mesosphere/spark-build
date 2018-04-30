#!/bin/sh
cd "${0%/*}" # to the folder containing this script.

set -x

# Usage:
#    (1) Login to cluster via "dcos cluster" command.
#    (2) Run this script:
#        ./uninstall-dispatchers.sh [dispatchers_file]
#
# This script:
# - uninstalls instances of spark listed in an input file.

if [ "$#" -lt 1 ]; then
    echo "Usage: ./uninstall-dispatchers.sh [dispatchers_file]"
    exit 1
fi

ACS_TOKEN=`dcos config show core.dcos_acs_token`
PACKAGE_NAME=spark

uninstall_instance () {
    SERVICE_NAME=$1
    dcos package uninstall $PACKAGE_NAME --app-id=${SERVICE_NAME} --yes
}

run_janitor () {
    ZKNODE=$1
    JANITOR_CMD="sudo docker run mesosphere/janitor /janitor.py -r spark-role -p spark-principal -z $ZKNODE --auth_token=$ACS_TOKEN"
    dcos node ssh --leader --user=centos --master-proxy "$JANITOR_CMD"
}

for instance in `cat dispatchers.out`
do
    uninstall_instance $instance
done

sleep 10

#TODO: if instance is "spark", the znode name is simply "spark_mesos_dispatcher"
for instance in `cat dispatchers.out`
do
    run_janitor spark_mesos_dispatcher${instance}
done
