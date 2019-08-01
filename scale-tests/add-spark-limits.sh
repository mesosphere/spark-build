#!/bin/bash

source configs/2019-08-01-mwst18.env

for i in {1..50}; do
  DRIVERS_ROLE="data-services-mwtdr18-preflight__spark-$(printf "%02d" $i)-drivers-role"
  EXECUTORS_ROLE="data-services-mwtdr18-preflight__spark-$(printf "%02d" $i)-executors-role"

  dcos quota create ${DRIVERS_ROLE} --cpu ${NON_GPU_QUOTA_DRIVERS_CPUS} --mem ${NON_GPU_QUOTA_DRIVERS_MEM}
  dcos quota create ${EXECUTORS_ROLE} --cpu ${NON_GPU_QUOTA_DRIVERS_CPUS} --mem ${NON_GPU_QUOTA_DRIVERS_MEM}
done

