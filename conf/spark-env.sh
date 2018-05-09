#!/usr/bin/env bash

# This file is sourced when running various Spark programs.
# Copy it as spark-env.sh and edit that to configure Spark for your site.

# A custom HDFS config can be fetched via spark.mesos.uris.  This
# moves those config files into the standard directory.  In DCOS, the
# CLI reads the "SPARK_HDFS_CONFIG_URL" marathon label in order to set
# spark.mesos.uris

mkdir -p "${HADOOP_CONF_DIR}"
[ -f "${MESOS_SANDBOX}/hdfs-site.xml" ] && cp "${MESOS_SANDBOX}/hdfs-site.xml" "${HADOOP_CONF_DIR}"
[ -f "${MESOS_SANDBOX}/core-site.xml" ] && cp "${MESOS_SANDBOX}/core-site.xml" "${HADOOP_CONF_DIR}"


cd $MESOS_SANDBOX

MESOS_NATIVE_JAVA_LIBRARY=/opt/mesosphere/libmesos-bundle/lib/libmesos.so

# Unless explicitly directed, use bootstrap (defined on L55 of Dockerfile) to lookup the IP of the driver agent
# this should be LIBPROCESS_IP iff the driver is on the host network, $(hostname) when it's not (e.g. CNI).
if [ -z ${SKIP_BOOTSTRAP_IP_DETECT} ]; then
    if [ -f ${BOOTSTRAP} ]; then
        SPARK_LOCAL_IP=$($BOOTSTRAP --get-task-ip)
        echo "spark-env: Configured SPARK_LOCAL_IP with bootstrap: ${SPARK_LOCAL_IP}" >&2
    else
        echo "ERROR: Unable to find bootstrap to configure SPARK_LOCAL_IP at ${BOOTSTRAP}, exiting." >&2
        exit 1
    fi
else
    echo "spark-env: Skipping bootstrap IP detection" >&2
fi

# I first set this to MESOS_SANDBOX, as a Workaround for MESOS-5866
# But this fails now due to MESOS-6391, so I'm setting it to /tmp
MESOS_DIRECTORY=/tmp

export LIBPROCESS_SSL_CA_DIR=/mnt/mesos/sandbox/.ssl/
export LIBPROCESS_SSL_CA_FILE=/mnt/mesos/sandbox/.ssl/ca.crt
export LIBPROCESS_SSL_CERT_FILE=/mnt/mesos/sandbox/.ssl/scheduler.crt
export LIBPROCESS_SSL_KEY_FILE=/mnt/mesos/sandbox/.ssl/scheduler.key
export MESOS_MODULES="{\"libraries\": [{\"file\": \"libdcos_security.so\", \"modules\": [{\"name\": \"com_mesosphere_dcos_ClassicRPCAuthenticatee\"}]}]}"
export MESOS_AUTHENTICATEE="com_mesosphere_dcos_ClassicRPCAuthenticatee"

echo "spark-env: User: $(whoami)" >&2

if [ -n "${SPARK_SECURITY_KERBEROS_KDC_HOSTNAME}" ] && [ -n "${SPARK_SECURITY_KERBEROS_KDC_PORT}" ] && [ -n "${SPARK_SECURITY_KERBEROS_REALM}" ]; then
    echo "Templating krb5.conf from environment" >&2
    # working dir is /mnt/mesos/sandbox
    CONFIG_TEMPLATE_KRB5CONF=../../../etc/krb5.conf.mustache,../../../etc/krb5.conf $BOOTSTRAP -template -resolve=false --print-env=false -install-certs=false
    cat ../../../etc/krb5.conf
fi

if [[ -n "${SPARK_MESOS_KRB5_CONF_BASE64}" ]]; then
    KRB5CONF=${SPARK_MESOS_KRB5_CONF_BASE64}
fi

if [[ -n "${KRB5_CONFIG_BASE64}" ]]; then
    KRB5CONF=${KRB5_CONFIG_BASE64}
fi

if [[ -n "${KRB5CONF}" ]]; then
    echo "Decoding base64 encoded krb5.conf" >&2
    if base64 --help | grep -q GNU; then
          BASE64_D="base64 -d" # GNU
      else
          BASE64_D="base64 -D" # BSD
    fi
    echo "spark-env: Copying krb config from $KRB5CONF to /etc/" >&2
    echo "${KRB5CONF}" | ${BASE64_D} > /etc/krb5.conf
else
    echo "spark-env: No SPARK_MESOS_KRB5_CONF_BASE64 to decode" >&2
fi

if [ -n "${STATSD_UDP_HOST}" ] && [ -n "${STATSD_UDP_PORT}" ]; then
    SPARK_CONF_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
    if [ -f "${SPARK_CONF_DIR}/metrics.properties.template" ]; then
        echo "spark-env: Configuring StatsD endpoint ${STATSD_UDP_HOST}:${STATSD_UDP_PORT} in ${SPARK_CONF_DIR}/metrics.properties" >&2
        sed -e "s/<STATSD_UDP_HOST>/${STATSD_UDP_HOST}/g" \
            -e "s/<STATSD_UDP_PORT>/${STATSD_UDP_PORT}/g" \
            ${SPARK_CONF_DIR}/metrics.properties.template >${SPARK_CONF_DIR}/metrics.properties
    else
        echo "spark-env: Skipping metrics configuration: Template not found: ${SPARK_CONF_DIR}/metrics.properties.template" >&2
    fi
else
    echo "spark-env: Skipping metrics configuration: STATSD_UDP_HOST/STATSD_UDP_PORT are not defined" >&2
    echo "spark-env: StatsD metrics require Mesos UCR. For dispatcher metrics, enable the 'UCR_containerizer' option. For driver metrics, include '--conf spark.mesos.containerizer=mesos' in your run"
fi

# Options read when launching programs locally with
# ./bin/run-example or ./bin/spark-submit
# - HADOOP_CONF_DIR, to point Spark towards Hadoop configuration files
# - SPARK_LOCAL_IP, to set the IP address Spark binds to on this node
# - SPARK_PUBLIC_DNS, to set the public dns name of the driver program
# - SPARK_CLASSPATH, default classpath entries to append

# Options read by executors and drivers running inside the cluster
# - SPARK_LOCAL_IP, to set the IP address Spark binds to on this node
# - SPARK_PUBLIC_DNS, to set the public DNS name of the driver program
# - SPARK_CLASSPATH, default classpath entries to append
# - SPARK_LOCAL_DIRS, storage directories to use on this node for shuffle and RDD data
# - MESOS_NATIVE_JAVA_LIBRARY, to point to your libmesos.so if you use Mesos

# Options read in YARN client mode
# - HADOOP_CONF_DIR, to point Spark towards Hadoop configuration files
# - SPARK_EXECUTOR_INSTANCES, Number of workers to start (Default: 2)
# - SPARK_EXECUTOR_CORES, Number of cores for the workers (Default: 1).
# - SPARK_EXECUTOR_MEMORY, Memory per Worker (e.g. 1000M, 2G) (Default: 1G)
# - SPARK_DRIVER_MEMORY, Memory for Master (e.g. 1000M, 2G) (Default: 1G)
# - SPARK_YARN_APP_NAME, The name of your application (Default: Spark)
# - SPARK_YARN_QUEUE, The hadoop queue to use for allocation requests (Default: ‘default’)
# - SPARK_YARN_DIST_FILES, Comma separated list of files to be distributed with the job.
# - SPARK_YARN_DIST_ARCHIVES, Comma separated list of archives to be distributed with the job.

# Options for the daemons used in the standalone deploy mode
# - SPARK_MASTER_IP, to bind the master to a different IP address or hostname
# - SPARK_MASTER_PORT / SPARK_MASTER_WEBUI_PORT, to use non-default ports for the master
# - SPARK_MASTER_OPTS, to set config properties only for the master (e.g. "-Dx=y")
# - SPARK_WORKER_CORES, to set the number of cores to use on this machine
# - SPARK_WORKER_MEMORY, to set how much total memory workers have to give executors (e.g. 1000m, 2g)
# - SPARK_WORKER_PORT / SPARK_WORKER_WEBUI_PORT, to use non-default ports for the worker
# - SPARK_WORKER_INSTANCES, to set the number of worker processes per node
# - SPARK_WORKER_DIR, to set the working directory of worker processes
# - SPARK_WORKER_OPTS, to set config properties only for the worker (e.g. "-Dx=y")
# - SPARK_DAEMON_MEMORY, to allocate to the master, worker and history server themselves (default: 1g).
# - SPARK_HISTORY_OPTS, to set config properties only for the history server (e.g. "-Dx=y")
# - SPARK_SHUFFLE_OPTS, to set config properties only for the external shuffle service (e.g. "-Dx=y")
# - SPARK_DAEMON_JAVA_OPTS, to set config properties for all daemons (e.g. "-Dx=y")
# - SPARK_PUBLIC_DNS, to set the public dns name of the master or workers

# Generic options for the daemons used in the standalone deploy mode
# - SPARK_CONF_DIR      Alternate conf dir. (Default: ${SPARK_HOME}/conf)
# - SPARK_LOG_DIR       Where log files are stored.  (Default: ${SPARK_HOME}/logs)
# - SPARK_PID_DIR       Where the pid file is stored. (Default: /tmp)
# - SPARK_IDENT_STRING  A string representing this instance of spark. (Default: $USER)
# - SPARK_NICENESS      The scheduling priority for daemons. (Default: 0)
