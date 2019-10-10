#!/bin/sh

set -x

create_service_account() {
    SERVICE_ACCOUNT=$1
    SECRET_NAME="${SERVICE_ACCOUNT}-secret"

    dcos security org service-accounts delete ${SERVICE_ACCOUNT} &>/dev/null
    dcos security secrets delete ${SECRET_NAME} &>/dev/null

    dcos security org service-accounts keypair private.pem public.pem
    dcos security org service-accounts create -p public.pem -d "Service account for ${SERVICE_ACCOUNT}" ${SERVICE_ACCOUNT}
    dcos security secrets create-sa-secret --strict private.pem ${SERVICE_ACCOUNT} ${SECRET_NAME}

    rm -f private.pem public.pem
}

grant_permissions() {
    SERVICE_ACCOUNT=$1

    echo "Granting permissions to Service Account ${SERVICE_ACCOUNT}"

    dcos security org users grant ${SERVICE_ACCOUNT} dcos:mesos:master:task:user:nobody create
    dcos security org users grant ${SERVICE_ACCOUNT} dcos:mesos:agent:task:user:nobody create
    dcos security org users grant ${SERVICE_ACCOUNT} dcos:secrets:list:default:__dcos_base64__hdfs_jupyter_keytab read
}

grant_spark_permissions() {
    SERVICE_ACCOUNT=$1
    echo "Granting Spark permissions to Jupyter Service Account ${SERVICE_ACCOUNT}"

    dcos security org users grant ${SERVICE_ACCOUNT} dcos:mesos:master:framework:role:${SERVICE_ACCOUNT} create
    dcos security org users grant ${SERVICE_ACCOUNT} dcos:mesos:master:reservation:role:${SERVICE_ACCOUNT} create
    dcos security org users grant ${SERVICE_ACCOUNT} dcos:mesos:master:reservation:principal:${SERVICE_ACCOUNT} delete
    dcos security org users grant ${SERVICE_ACCOUNT} dcos:mesos:master:volume:role:${SERVICE_ACCOUNT} create
    dcos security org users grant ${SERVICE_ACCOUNT} dcos:mesos:master:volume:principal:${SERVICE_ACCOUNT} delete

    dcos security org users grant ${SERVICE_ACCOUNT} dcos:mesos:master:task:role:${SERVICE_ACCOUNT} create
    dcos security org users grant ${SERVICE_ACCOUNT} dcos:mesos:master:task:principal:${SERVICE_ACCOUNT} create
    dcos security org users grant ${SERVICE_ACCOUNT} dcos:mesos:master:task:app_id:jupyter/jupyter create
}
create_service_account jupyter__jupyter

grant_permissions jupyter__jupyter
grant_spark_permissions jupyter__jupyter

dcos package install --yes data-science-engine --options=scale-tests/configs/jupiter-options.json



# Run the following in the Jupyter notebook UI (password: jupyter):
#
# ! spark-submit \
#--conf spark.mesos.gpus.max=<number of GPUS> \
#--conf spark.cores.max=<should be gte spark.mesos.gpus.max> \
#--conf spark.mesos.executor.gpus=1 \
#--conf spark.executor.cores=1 \
#--verbose \
#--class MockTaskRunner \
#https://infinity-artifacts.s3.amazonaws.com/scale-tests/dcos-spark-scala-tests-assembly-2.4.0-20190325.jar 5000 10