#!/usr/bin/env bash
set -e

if [[ $1 != ${1//[^0-9]/} || $1 == 0 ]]; then
  echo "First argument must be a positive integer." >&2
  exit 1
fi
value="$1"
shift
exec "$(dirname "$0")"/push_metric.sh \
  --metric-name "set_kafka_or_zk_cluster_count" \
  --metric-description "Expected number of kafka and zookeeper clusters." \
  --metric-value "${value}" \
  "$@"
