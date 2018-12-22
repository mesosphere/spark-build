#!/bin/bash
set -e
set -o pipefail

# The purpose of this script is to detect IP address to bind to based on the set of configuration parameters.
# When container is launched in virtual or overlay network SPARK_BIND_ADDRESS_DETECTION_METHOD will be used.
# In other cases, unless explicitly directed, bootstrap script (defined in docker/Dockerfile) will be used
# to lookup the IP of the agent.

# SPARK_BIND_ADDRESS_DETECTION_METHOD can be set to one of the following methods:
#  - hostname=ip-address (default if not set)
#  - hostname=fqdn
#  - interface=eth0
#  - interface=eth1
#  - interface=eth2
function detect_bind_address() {
    echo "[bind-address]: Resolving container IP to bind to using detection method: ${SPARK_BIND_ADDRESS_DETECTION_METHOD}"
    if [ ! -z "${SPARK_BIND_ADDRESS_DETECTION_METHOD}" ]; then
        type=$(echo ${SPARK_BIND_ADDRESS_DETECTION_METHOD} | cut -d= -f1)
        parameter=$(echo ${SPARK_BIND_ADDRESS_DETECTION_METHOD} | cut -d= -f2)

        echo "[bind-address]: IP resolution method type: '$type', parameter: '$parameter'"

        case ${type} in
            hostname )
                    case ${parameter} in
                        ip-address )
                            SPARK_LOCAL_IP=$(hostname -i)
                            ;;
                        fqdn )
                            SPARK_LOCAL_IP=$(hostname -f)
                            ;;
                        * ) echo "[bind-address]: Wrong parameter for ${type} resolution method, supported parameters: 'ip-address', 'fqdn'"
                            exit 1
                            ;;
                    esac
                    ;;
            interface )
                    case ${parameter} in
                        eth0|eth1|eth2 )
                            SPARK_LOCAL_IP=$(ifconfig ${parameter} | grep inet | awk '{print $2}')
                            ;;
                        * ) echo "[bind-address]: Wrong parameter for ${type} resolution method, supported interfaces: 'eth0', 'eth1', 'eth2'"
                            exit 1
                            ;;
                    esac
                    ;;
            *) echo "[bind-address]: Resolution method type is not recognized, supported methods: 'hostname', 'interface'"
                exit 1
                ;;
        esac
    else
        echo "[bind-address]: Resolution method is not specified, using the default 'hostname=ip-address'"
        SPARK_LOCAL_IP=`hostname -i`
    fi
}

function detect_bind_address_with_bootstrap() {
    if [ "${USE_BOOTSTRAP_FOR_IP_DETECT}" = true ]; then
        if [ -f ${BOOTSTRAP} ]; then
            SPARK_LOCAL_IP=$($BOOTSTRAP --get-task-ip)
            echo "[bind-address]: Configured SPARK_LOCAL_IP with bootstrap: ${SPARK_LOCAL_IP}" >&2
        else
            echo "[bind-address]: ERROR: Unable to find bootstrap to configure SPARK_LOCAL_IP at ${BOOTSTRAP}, exiting." >&2
            exit 1
        fi
    else
      echo "[bind-address]: Skipping bootstrap IP detection" >&2
    fi
}

if [ "${VIRTUAL_NETWORK_ENABLED}" = true ]; then
    detect_bind_address
else
    detect_bind_address_with_bootstrap
fi

if [ ! -z "${SPARK_LOCAL_IP}" ]; then
    echo "[bind-address]: Bind address: ${SPARK_LOCAL_IP}"
    echo "SPARK_LOCAL_IP=${SPARK_LOCAL_IP}" >> ${SPARK_HOME}/conf/spark-env.sh
    export LIBPROCESS_IP=${SPARK_LOCAL_IP}
else
    echo "[bind-address]: IP resolution was skipped, bind address will be resolved internally by Spark"
fi
