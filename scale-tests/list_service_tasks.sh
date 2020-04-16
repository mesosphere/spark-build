#!/usr/bin/env bash

set -euo pipefail

readonly SERVICE_NAME="${1}"

case ${SERVICE_NAME} in
  kafka)     metric="kafka_app_info_version" ;;
  cassandra) metric="org_apache_cassandra_metrics_Storage_Load" ;;
  *)         echo "Only 'kafka' and 'cassandra' are valid arguments. '${SERVICE_NAME}' given"; exit 1 ;;
esac

readonly CLUSTER_URL="$(dcos config show core.dcos_url)"

curl --silent "${CLUSTER_URL}/service/monitoring/prometheus/api/v1/query?query=${metric}" \
     -H "Authorization: token=$(dcos config show core.dcos_acs_token)" \
  | jq -r '.data.result[].metric.task_name?'
