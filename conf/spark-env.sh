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

# For non-CNI, tell the Spark driver to bind to LIBPROCESS_IP
#
# For CNI, LIBPROCESS_IP is 0.0.0.0, so we can't do this.  Instead, we
# let Spark perform its default behavior of doing a DNS lookup on the
# hostname, which should work because the container is set up with a
# $(hostname) in /etc/hosts.
if ! getent hosts $(hostname) > /dev/null && [ -n "$LIBPROCESS_IP" ]; then
    SPARK_LOCAL_IP=${LIBPROCESS_IP}
fi

# I first set this to MESOS_SANDBOX, as a Workaround for MESOS-5866
# But this fails now due to MESOS-6391, so I'm setting it to /tmp
MESOS_DIRECTORY=/tmp

export LIBPROCESS_SSL_CA_DIR=/mnt/mesos/sandbox/.ssl/
export LIBPROCESS_SSL_CA_FILE=/mnt/mesos/sandbox/.ssl/ca.crt
export LIBPROCESS_SSL_CERT_FILE=/mnt/mesos/sandbox/.ssl/scheduler.crt
export LIBPROCESS_SSL_KEY_FILE=/mnt/mesos/sandbox/.ssl/scheduler.key

export DCOS_SERVICE_ACCOUNT_CREDENTIAL="{\"secret\": \"spark-secret\"}"
# 1.9
export DCOS_SERVICE_ACCOUNT_CREDENTIAL="{\"login_endpoint\":\"https://leader.mesos/acs/api/v1/auth/login\",\"private_key\":\"-----BEGIN PRIVATE KEY-----\\nMIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQDXqxJLt0qs3Y0f\\n1xl0827t1k/mjrlCME07ZdxVaoUppIPrDYl7elGcvWEBxtCdS6qrSFL1vDbanLt9\\nomQUWx2omLB/7KPg7xu5Gz8GKr3UPMzpJk8kcb1BWBIXW9tUkDZHOfufLE+n9o8y\\n5MboTjuqxxEYYGz1StCYRwYwddBZBh1IaTusg8ZYJRh0TfUYQoRqNL7z2W1Hw6cD\\nW2h5o8JOut90uEJ5ftPDDXLanagJvC433VtO9a3cCaUzogPQy8GhRIu7CxMi1a/V\\n2fSqW2od+8mwx5j1n2jK/4hWyyLAeTI4w4HCA92s78gNpFlrdSTM+WHW/JqphHEL\\nESVl1/0JAgMBAAECggEAC8mf4F+OR1B8rCbXj1rWz00NZO6cFZAKSJrSpiCCUrpZ\\nM3mz7/nJiCWZrb0uHcrK8z2qux+kZ+J1JPLBQZORVWuzCernMh4fh8iDc1TWt0jz\\ncjLT1Iwa6f1kT76HiGGxdccnh5WmbOm+/esfLAdKn5TtzEVI70c9i3UmU3O9BYCE\\nTaafxn+fYSJ82/yxdG2xpdm8kLIirb0BhtTcZM/P+hLAWI+DhJ87ax8oCKOFnUzo\\nTADB7QaZCeT37TtW/FVi92b5vhSGH2n/LQtvhqPrRY6pybaLGy2DVQrgqVe2XYTC\\n9LYA3srxnacpoptg0UKFjultBcpPsJmjivreIeFY2QKBgQD7+rKwBNiNz9IP+wSP\\nvyPD1Bs8YTpYM3bgF0EITy+eYXipyeYaWgdeHyWvPh0/2es16sooQTvkQXFokVX0\\nzddENXcFXICGvBs7jPjMECw4anz2fip4A5bdv5Ay5YKB8m5yRGACXth+OAVnrayD\\njJJe+TsslXkEXV1g1Co6tA+xjwKBgQDbHAw0q0kIKmyehgpB9mlcIl1gGBMMgxk6\\ntnlXU79pZv0kIpyxVShFBDQnHC0Oga6NCIhpq8bKSIxiyKgYLs9gWTmldD+ij5mJ\\nXWsx40PIiXoDDf+NvYgBpIFdbmXzejNPW6naPQTALq2JRXPNiOKSRHMrvDOUX8ht\\nyz2+MAhr5wKBgFAuJ+nmwNnvRVKcd4keM00/EyOVdLFYPv1zqNfyCp8FORYeDsBX\\n4XxLwPwQcdI9j6Dqg0Vn7JznTiUOCiIJ1fP4Z1UnaCZ3eNrsMscMZmXVTMpKv0zN\\nJ5aMPGBVs7+R2x81Lq/SamVPgjjJhNmfQ3xBJlk7fvSqmOoU2RMw9MV1AoGAJD99\\nnXEAwgMSuR7/r23ufDmLLQyOijFeCSKK7HGEZxGMq1+2gHfQE6rgXeABbDb0A4z3\\n1FOArZJW9ziu5mFIGW5pZP/YTzJmeh0kULqCSjjEIKE+N9q1F2B5rlVHNIJw3p4R\\neXNCx/Bw8Ra2U7hjk0MTspaOCevWoqNO8ZnMqt0CgYEAylq1tdDpm0s2qBE5hmbJ\\nlY0yPYIgVACSoAcp+0ZHPo/8ojiNUdMDyCvO4cHCX6NqCxw8p96v+R8gCVrpNqmo\\nxizND8JBk06E0QHmQL93CpK3bm8szXnDIa83ZsJAM42LHWluvFuO93zEM4l0ISks\\nIUIRtCHNJ8n2KRRNRxlDMVE=\\n-----END PRIVATE KEY-----\\n\",\"scheme\":\"RS256\",\"uid\":\"spark-principal\"}"
# 1.10
#export DCOS_SERVICE_ACCOUNT_CREDENTIAL="{\"login_endpoint\":\"https://leader.mesos/acs/api/v1/auth/login\",\"private_key\":\"-----BEGIN PRIVATE KEY-----\\nMIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQDDQC2J5wNNDusP\\nGXUOou98z0Jfua1ORik5wIg1PbaZteNOrNKeHz4QTH9WZWfbNTSypij2QQ/KfVg0\\nYMCDKGpOHLWgU1jq3Qfm7sip2A6TSqGpDkR4hlPby7KHe6hKBwcI2uC8/cHuDa7Y\\nrK89N4lepIdTkODviiMFGM5qRlcKNzDy085Ji5OPpVxEbgQu1BaDig1VWjVic2+k\\nE72H8Y45gYBnn7lJiHkKN466/X1qCTTzKPO4eAHex7K/i6DyoaeT8MZBlmiasD8x\\nYlBWXl36gkwMefrqYHe2Pmb2+6UJLdTQKh15v1w+suDhJ+JcCvHVCeymeuxbJBja\\n9G3qxEQbAgMBAAECggEAdeH5nJjtVUj8glFMa1nUXfaEjGb+S5Pwr/2ePwbTiFpY\\nsteFEhKq1gxZlUAEREULXBEWCheeARNMfdMsaAOuqxqKThIETUjFzJe+b00S/7q/\\nf+ItVNdFKh8B2uq94HP9u0rrBS/wNlnshsU7yCoPtiR/z+RY6kbsfddMSL3PL0q0\\n3ODFWrwrebB1LjCYNKDE3sbgt7Avz5kYulz3cwZZ4MBgUmcCn2pBPlotuAFJYTkD\\nqWgNvZ9ULWXMQxzDsW3KhC4Dl2pIPYAPb8aCpc3W4Ni7Os/tTtWrF9NtqH5RV4Ds\\nPvKKfHEohogli4QAq/RzbxX82Ltd/KNMxZPeqDV3AQKBgQDrksj0EzG3IJRMIa5z\\ntE24WYif41nJz8uTe9WBCxk2UOsWZIE3ZsjuEzDUCXWL+vqT+XM6+oZ/HdNyfiKo\\n5kqrOJCerO5BbuWqgci1aVP2ZYQneghECcldNk3jmHhyZJm2Xuc7FevlPj7azl+r\\nuNjjAwgzfII21iiC1KkY3TZkuQKBgQDULlE67Vxoqa8kbxtybLLsMZcDqMG+SP8s\\n4PxjGZXnpiqKmjU/sjfuFFn7sEuVSVxxV2vd+MK1f6xY1cvjWzX9YR4PUoXJilpj\\nGhThIo5pWa3xGcYHbBz912v5gnWSxgAQXWTG9tmKT1RfYr1eY3+zSZzRzzySygVb\\n/0A6eWStcwKBgQCU4nR3LhphrwmLBE6Jeg8U0CF1S+9XiSkU0VMi96y7k3DA+kxg\\ng2nCbgaSPFg6XCk6lJGrWOLgPC2DUwz8ym+uv1VHs+vxFvG4TcZYQXV7aLWZbZsD\\nxVuqucOIcLjPM52ikWB7C2PHwwtepsf4dB8/eo8YWzzBA6Ee7uDggg76oQKBgFQh\\nsW/OIjAV6C5oJ9ftJdzlpN18kqXix9uBslGRGZFqn7+peaeyAN9UDoHv22hsWE1Q\\nvqKbOolBAJOQ4nFZ/0Rit8qXjBjn1QMqmlDSpOk89+17rLvQsIYuXs/mXLw/6lKS\\n1ZzW0Fc5MVlJC5Fbnoz2iUngBEKn/AwIX+1PqQ3lAoGAT8l42ikwBAdnPpf0epQX\\n/xez8Iygi6v6N3ncp20Op7N8hRRAVy8lzwPBLo+mKBnDTU3VaUiQFJV2Xfp9FaFp\\npS2F9TJSbf1udoJSUczhZa/RRM8UbekL1Q0s5XhGj239wC2RfLVdQSLhDjbynkg4\\nJu/UryddvjUEu/Lduc09hH4=\\n-----END PRIVATE KEY-----\\n\",\"scheme\":\"RS256\",\"uid\":\"spark-principal\"}"

export MESOS_MODULES="{\"libraries\": [{\"file\": \"libdcos_security.so\", \"modules\": [{\"name\": \"com_mesosphere_dcos_ClassicRPCAuthenticatee\"}]}]}"
export MESOS_AUTHENTICATEE="com_mesosphere_dcos_ClassicRPCAuthenticatee"

echo "spark-env: Printing environment" >&2
env >&2
echo "spark-env: User: $(whoami)" >&2

for f in $MESOS_SANDBOX/*.base64 ; do
    echo "decoding $f" >&2
    secret=$(basename ${f} .base64)
    cat ${f} | base64 -d > ${secret}
done

if [[ -n "${KRB5_CONFIG_BASE64}" ]]; then
    echo "spark-env: Copying krb config from $KRB5_CONFIG_BASE64 to /etc/" >&2
    echo "${KRB5_CONFIG_BASE64}" | base64 -d > /etc/krb5.conf
else
    echo "spark-env: No kerberos KDC config found" >&2
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
