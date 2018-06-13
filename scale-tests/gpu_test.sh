#!/bin/bash

DISPATCHERS_FILE=$1
DISPATCHERS=()
EXECUTORS=()

while IFS=',' read DISPATCHER DRIVER_ROLE EXECUTOR_ROLE
do
  DISPATCHERS+=($DISPATCHER)
  EXECUTORS+=($EXECUTOR_ROLE)
done < $DISPATCHERS_FILE

# Install Spark CLI
dcos package install spark --cli --yes 

# Submit 15 GPU jobs per dispatcher each hour
# Number of GPUs used for each job is randomly picked between [1,8]
while true
do
  let NUM_GPUS=1+$RANDOM%8
  let MEMORY=$NUM_GPUS*20
  echo "Submitting job with gpus: $NUM_GPUS, mem: $MEMORY"
  for ((i=0; i<${#DISPATCHERS[@]}; ++i))
  do
    dcos spark run --name=/${DISPATCHERS[i]} --submit-args="\
      --conf spark.cores.max=4 \
      --conf spark.driver.memory=${MEMORY}g \
      --conf spark.executor.memory=${MEMORY}g \
      --conf spark.mesos.gpus.max=${NUM_GPUS} \
      --conf spark.mesos.executor.gpus=${NUM_GPUS} \
      --conf spark.mesos.executor.docker.forcePullImage=false \
      --conf spark.mesos.executor.docker.image=samvantran/spark-dcos-gpu:minpatch-nv390-cuda9-cudnn7115-tf15 \
      --conf spark.mesos.containerizer=mesos \
      --conf spark.mesos.role=${EXECUTORS[i]} \
      --conf spark.scheduler.maxRegisteredResourcesWaitingTime=240s \
      --conf spark.scheduler.minRegisteredResourcesRatio=1.0 \
      https://s3-us-west-1.amazonaws.com/svt-dev/run_image_recognition-final.py 500 3"
  done
  sleep 4
done
