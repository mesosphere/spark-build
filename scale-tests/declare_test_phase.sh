#!/usr/bin/env bash
set -e

case "$1" in
'start'|'started'|'steady')
  code="1"
  ;;
fault*)
  code="2"
  ;;
stop*|'starting'|'end')
  code="0"
  ;;
*)
  echo "Please specify a valid test phase." >&2
  echo "Usage:" >&2
  echo "$0 {stop|start|fault} [options]" >&2
  exit 1
  ;;
esac
shift
exec "$(dirname "$0")"/push_metric.sh \
  --metric-name "test_status" \
  --metric-description "Status of the test (0==not running, 1==in steady state, 2==fault injection)." \
  --metric-value "${code}" \
  "$@"
