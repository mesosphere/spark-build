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

# extract cert and key from keystore, write to /etc/nginx/spark.{crt,key}
if [[ "${SPARK_SSL_ENABLED}" == true ]]; then
	KEYDIR=`mktemp -d`
	trap "rm -rf $KEYDIR" EXIT

	echo "${SPARK_SSL_KEYSTOREBASE64}" | base64 -d > "$KEYDIR/spark.jks"
	ALIAS=$(keytool -list -keystore "$KEYDIR/spark.jks" -storepass "${SPARK_SSL_KEYSTOREPASSWORD}" | grep PrivateKeyEntry | cut -d, -f1 | head -n1)
	if [[ -z "${ALIAS}" ]]; then
		echo "Cannot find private key in keystore"
		exit 1
	fi

	# convert keystore to p12
	keytool -importkeystore -srckeystore "$KEYDIR/spark.jks" -srcalias "${ALIAS}" \
		-srcstorepass "${SPARK_SSL_KEYSTOREPASSWORD}" -destkeystore "$KEYDIR/spark.p12" \
		-deststorepass "${SPARK_SSL_KEYSTOREPASSWORD}" -deststoretype PKCS12

	# export cert and key from p12
	openssl pkcs12 -nokeys -passin pass:"${SPARK_SSL_KEYSTOREPASSWORD}" -in "$KEYDIR/spark.p12" -out /etc/nginx/spark.crt
	openssl pkcs12 -nocerts -nodes -passin pass:"${SPARK_SSL_KEYSTOREPASSWORD}" -in "$KEYDIR/spark.p12" -out /etc/nginx/spark.key
	chmod 600 /etc/nginx/spark.{crt,key}

	rm -rf "$KEYDIR"
fi

# Move hadoop config files, as specified by hdfs.config-url, into place.
if [[ -f hdfs-site.xml && -f core-site.xml ]]; then
    mkdir -p "${HADOOP_CONF_DIR}"
    cp hdfs-site.xml "${HADOOP_CONF_DIR}"
    cp core-site.xml "${HADOOP_CONF_DIR}"
fi

# Move kerberos config file, as specified by security.kerberos.krb5conf, into place.
# this only affects the krb5.conf file for the dispatcher
if [[ -n "${SPARK_MESOS_KRB5_CONF_BASE64}" ]]; then
    echo "${SPARK_MESOS_KRB5_CONF_BASE64}" | base64 -d > /etc/krb5.conf
fi


# start service
exec runsvdir -P /etc/service
