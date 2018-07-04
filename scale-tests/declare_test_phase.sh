#!/usr/bin/env bash
set -e

prometheus="prometheus"
proxy_port="8080"
job="ds-streaming"

TEMP=$(getopt -o 's:p:' --long 'prometheus-service:,proxy-port:,job:' -n "$0" -- "$@")
eval set -- "$TEMP"
unset TEMP
while true; do
  case "$1" in
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
  exit 1
  ;;
esac

endpoints_tempfile="$(mktemp)"
trap "rm -f ${endpoints_tempfile}" EXIT
echo "Discovering push gateway endpoint address..." >&2
dcos prometheus --name="${prometheus}" endpoints pushgateway > "${endpoints_tempfile}"
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

(echo '# TYPE test_status gauge'
 echo '# HELP test_status Status of the test (0==not running, 1==in steady state, 2==fault injection).'
 echo "test_status ${code}") | curl --preproxy "localhost:${proxy_port}" --data-binary @- "${url}"
echo "Metric pushed successfully. Note that it may take up to 15 seconds for it to propagate to prometheus." >&2

