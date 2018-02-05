#!/bin/bash
set -e
set -x

export DISPATCHER_PORT="${PORT0}"
export DISPATCHER_UI_PORT="${PORT1}"
export SPARK_PROXY_PORT="${PORT2}"

# determine scheme and derive WEB
SCHEME=http
OTHER_SCHEME=https
if [[ "${SPARK_SSL_ENABLED}" == true ]]; then
	SCHEME=https
	OTHER_SCHEME=http
fi

# TODO(mgummelt): I'm pretty sure this isn't used.  Remove after some time.
# export WEBUI_URL="${SCHEME}://${FRAMEWORK_NAME}${DNS_SUFFIX}:${SPARK_PROXY_PORT}"

export DISPATCHER_UI_WEB_PROXY_BASE="/service/${DCOS_SERVICE_NAME}"

# Update nginx spark.conf to use http or https
grep -v "#${OTHER_SCHEME}#" /etc/nginx/conf.d/spark.conf.template |
	sed "s,#${SCHEME}#,," >/etc/nginx/conf.d/spark.conf

sed -i "s,<PORT>,${SPARK_PROXY_PORT}," /etc/nginx/conf.d/spark.conf
sed -i "s,<DISPATCHER_URL>,${SCHEME}://${HOST}:${DISPATCHER_PORT}," /etc/nginx/conf.d/spark.conf
sed -i "s,<DISPATCHER_UI_URL>,http://${HOST}:${DISPATCHER_UI_PORT}," /etc/nginx/conf.d/spark.conf
sed -i "s,<PROTOCOL>,${SPARK_SSL_PROTOCOL}," /etc/nginx/conf.d/spark.conf

# Disabled algorithms for Nginx because it crashes with the usual multi-1000
# bytes cipher strings of Java.
# sed -i "s,<ENABLED_ALGORITHMS>,${SPARK_SSL_ENABLEDALGORITHMS//,/:}," /etc/nginx/conf.d/spark.conf

# start service
exec runsvdir -P /etc/service
