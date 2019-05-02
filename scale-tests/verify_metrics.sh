#!/usr/bin/env bash

set -e

if [ "$1" == "kafka" ]; then
	KAFKA_BROKERS=$(curl --silent $(dcos config show core.dcos_url)'/service/monitoring/prometheus/api/v1/query?query=kafka_app_info_version' -H "Authorization: token=$(dcos config show core.dcos_acs_token)" | jq '.data.result[].metric.task_name?')
	printf "Brokers for kafka detected:\n$KAFKA_BROKERS \n"
fi

if [ "$1" == "cassandra" ]; then
	CASSANDRA_NODES=$(curl --silent $(dcos config show core.dcos_url)'/service/monitoring/prometheus/api/v1/query?query=org_apache_cassandra_metrics_Storage_Load' -H "Authorization: token=$(dcos config show core.dcos_acs_token)" | jq '.data.result[].metric.task_name?')
	printf "Nodes for cassandra detected:\n$CASSANDRA_NODES \n"
fi

if [ "$1" == "" ]; then
	CASSANDRA_NODES=$(curl --silent $(dcos config show core.dcos_url)'/service/monitoring/prometheus/api/v1/query?query=org_apache_cassandra_metrics_Storage_Load' -H "Authorization: token=$(dcos config show core.dcos_acs_token)" | jq '.data.result[].metric.task_name?')
	printf "Nodes for cassandra detected:\n$CASSANDRA_NODES \n"
fi

