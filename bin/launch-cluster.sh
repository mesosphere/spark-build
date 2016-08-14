#!/usr/bin/env bash

# ENV VARS
#   CCM_AUTH_TOKEN
#   CLUSTER_NAME
#   DCOS_CHANNEL (optional)

set -e
set -x
set -o pipefail

if [ -z "${DCOS_CHANNEL}" ]; then
    DCOS_CHANNEL=testing/master
fi


CCM_URL=https://ccm.mesosphere.com/api/cluster/
AUTH_HEADER=Authorization:"Token ${CCM_AUTH_TOKEN}"

# create cluster
CCM_RESPONSE=$(http --ignore-stdin \
                    --verify no \
                    "${CCM_URL}" \
                    "${AUTH_HEADER}" \
                    cloud_provider=0 \
                    name=${CLUSTER_NAME} \
                    region=us-west-2 \
                    time=60 \
                    channel=${DCOS_CHANNEL} \
                    cluster_desc="DC/OS Spark testing cluster" \
                    template=single-master.cloudformation.json \
                    adminlocation=0.0.0.0/0 \
                    public_agents=1 \
                    private_agents=1)

CLUSTER_ID=$(echo "${CCM_RESPONSE}" | jq ".id")

# echo "cluster created: ID=${CLUSTER_ID}"

# echo "Waiting for cluster to come up..."
# wait for cluster to come up
while true; do
    STATUS=$(http --ignore-stdin \
                  --verify no \
                  "${CCM_URL}active/all/" \
                  "${AUTH_HEADER}" | jq ".[] | select(.id == ${CLUSTER_ID}) | .status");
    if [ $STATUS -eq 0 ]; then
        break;
    fi;
    sleep 10;
done;

# get dcos_url
CLUSTER_INFO=$(http --verify no GET "${CCM_URL}active/all/" "${AUTH_HEADER}" | jq ".[] | select(.id == $CLUSTER_ID) | .cluster_info")
eval CLUSTER_INFO=$CLUSTER_INFO  # unescape json

DCOS_URL=$(echo "$CLUSTER_INFO" | jq ".DnsAddress")
DCOS_URL=${DCOS_URL:1:-1}

echo "${DCOS_URL}"
