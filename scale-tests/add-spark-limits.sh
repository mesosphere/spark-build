#!/bin/bash

source configs/2019-08-01-mwst18.env

for i in `seq 1 ${NON_GPU_NUM_DISPATCHERS}`; do
  DRIVERS_ROLE="data-services-mwtdr18-preflight__spark-$(printf "%02d" $i)-drivers-role"
  EXECUTORS_ROLE="data-services-mwtdr18-preflight__spark-$(printf "%02d" $i)-executors-role"

  echo dcos quota create ${DRIVERS_ROLE} --cpu ${NON_GPU_QUOTA_DRIVERS_CPUS} --mem ${NON_GPU_QUOTA_DRIVERS_MEM}
  echo dcos quota create ${EXECUTORS_ROLE} --cpu ${NON_GPU_QUOTA_DRIVERS_CPUS} --mem ${NON_GPU_QUOTA_DRIVERS_MEM}
done

