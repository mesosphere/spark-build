#!/usr/bin/env bash
set -e

metric_name=""
metric_description=""
metric_value=""
prometheus="prometheus"
proxy_port="8080"
job="ds-streaming"

TEMP=$(getopt -o 's:p:' --long 'metric-name:,metric-description:,metric-value:,prometheus-service:,proxy-port:,job:' -n "$0" -- "$@")
eval set -- "$TEMP"
unset TEMP
while true; do
  case "$1" in
    '--metric-name')
      metric_name="$2"
      shift 2
      continue
      ;;
    '--metric-description')
      metric_description="$2"
      shift 2
      continue
      ;;
    '--metric-value')
      metric_value="$2"
      shift 2
      continue
      ;;
    '-s'|'--prometheus-service')
      prometheus="$2"
      shift 2
      continue
      ;;
    '-p'|'--proxy-port')
      proxy_port="$2"
      shift 2
      continue
      ;;
    '--job')
      job="$2"
      shift 2
      continue
      ;;
    '--')
      shift
      break
      ;;
    *)
      exit 1
      ;;
  esac
done

if [[ -n $1 ]]; then
  echo "Unexpected argument: $1" >&2
  exit 1
fi

if [[ -z $metric_name || -z $metric_description || -z $metric_value ]]; then
  echo "Metric name, description and value are required." >&2
  exit 1
fi

endpoints_tempfile="$(mktemp)"
trap "rm -f ${endpoints_tempfile}" EXIT
echo "Discovering push gateway endpoint address..." >&2
if ! dcos prometheus --name="${prometheus}" endpoints pushgateway > "${endpoints_tempfile}"; then
  echo "Discovery failed." >&2
  cat "${endpoints_tempfile}" >&2
  exit 1
fi
if ! pushgateway="$(jq --raw-output --exit-status '.address[0]' < "${endpoints_tempfile}")"; then
  echo "Failed, perhaps the gateway is not up yet? Endpoint information was:" >&2
  cat "${endpoints_tempfile}" >&2
  exit 1
fi
url="http://${pushgateway}/metrics/job/${job}"

echo "Pushing metric to ${url} via SOCKS proxy localhost:${proxy_port}." >&2
echo "NOTE: if you had not started the proxy, please start it with:" >&2
echo "  dcos package install --yes tunnel-cli" >&2
echo "  dcos tunnel socks --port=8080" >&2
echo "in another shell." >&2

(echo "# TYPE ${metric_name} gauge"
 echo "# HELP ${metric_name} ${metric_description}."
 echo "${metric_name} ${metric_value}") | curl --preproxy "localhost:${proxy_port}" --data-binary @- "${url}"
echo "Metric pushed successfully. Note that it may take up to 15 seconds for it to propagate to prometheus." >&2
