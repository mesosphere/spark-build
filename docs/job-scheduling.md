---
layout: layout.pug
navigationTitle: 
excerpt:
title: Job Scheduling
menuWeight: 110
featureMaturity:

---

This document is a simple overview of material described in greater detail in the Apache Spark documentation [here][1]
and [here][2].

# Modes

Spark on Mesos supports two modes of operation: coarse-grained mode and fine-grained mode. Coarse-grained mode
provides lower latency, whereas fine-grained mode provides higher utilization. More info [here][2].

# Coarse-grained mode

"Coarse-grained" mode is so-called because each Spark **executor** is represented by a single Mesos task. As a result,
executors have a constant size throughout their lifetime.

*   **Executor memory**: `spark.executor.memory`
*   **Executor CPUs**: `spark.executor.cores`, or all the cores in the offer.
*   **Number of Executors**: `spark.cores.max` / `spark.executor.cores`. Executors are brought up until
    `spark.cores.max` is reached. Executors survive for duration of the job.
*   **Executors per agent**: Multiple

Notes:

*   We highly recommend you set `spark.cores.max`. If you do not, your Spark job may consume all available resources in
    your cluster, resulting in unhappy peers.

# Quota for Drivers and Executors

Setting [Mesos Quota](http://mesos.apache.org/documentation/latest/quota/) for the Drivers prevents the Dispatcher from
greedily consuming too many resources and assists queueing behavior. To control the concurrent number of Drivers the
Spark service will run concurrently, we **strongly** recommend setting Quota for the Drivers. The Quota will both
guarantee that the Spark Dispatcher has resources available to launch Drivers _and limit_ the total impact on the
cluster due to Drivers.  Optionally, set Quota for the Drivers to consume, this ensures that Drivers will not be starved
of resources by other frameworks as well as make sure they do not consume too much of the cluster (see coarse-grained
mode above).

## Setting Quota for the Drivers

Quota for the Drivers allows the operator of the cluster to ensure that only a given number of Drivers are concurrently
running. As additional Drivers are submitted, they will be enqueued by the Spark Dispatcher. Below are the recommended
steps for setting Quota for the Drivers:

1.  Set the Quota conservatively, keeping in mind that it will effect the number of jobs that can run concurrently.
1.  Decide how much of your cluster's resources to allocate to running Drivers. These resources will only be used for
    the Spark Drivers, meaning that here we can decide roughly how many concurrent jobs we’d like to have running at a
    time. As additional jobs are submitted, they will be enqueued and run with first-in-first-out semantics.
1.  For the most predictable behavior, enforce uniform driver resource requirements and a particular Quota size for the
    Dispatcher.  If each driver consumes 1.0 cpu and it is desirable to run up to 5 Spark jobs concurrently, Quota with
    5 cpus should be created.
        
ssh to the Mesos master and set the Quota for a role (`dispatcher` in this example):

```bash
$ cat dispatcher-quota.json
{
 "role": "dispatcher",
 "guarantee": [
   {
     "name": "cpus",
     "type": "SCALAR",
     "scalar": { "value": 5.0 }
   },
   {
     "name": "mem",
     "type": "SCALAR",
     "scalar": { "value": 5120.0 }
   }
 ]
}
$ curl -d @dispatcher-quota.json -X POST http://<master>:5050/quota
```

Then install the Spark service with the following options (at a minimum):

```bash
$ cat options.json
{
    "service": {
        "role": "dispatcher"
    }
}
$ dcos package install spark --options=options.json
```

## Setting Quota for the Executors
        
It is recommended to allocate Quota for Spark job executors.  Allocating Quota for the Spark executors provides:
1.  A guarantee that Spark jobs will receive the requested amount of resources.
1.  Additional assurance that even misconfigured (e.g. greedy Driver with unset `spark.cores.max`) Spark jobs do not consume
    too many resources impacting other tenants on the cluster.

The drawback to allocating Quota to the Executors is that Quota resources cannot be used by other frameworks in the
cluster.

Quota can be allocated for Spark executors in the same way it was allocated for Spark dispatchers.  If we assume we want
to be able to run 100 executors concurrently each with 1.0 cpu and 4096 MB of memory we should do the following:

```bash
$ cat executor-quota.json
{
  "role": "executor",
  "guarantee": [
    {
      "name": "cpus",
      "type": "SCALAR",
      "scalar": { "value": 100.0 }
    },
    {
      "name": "mem",
      "type": "SCALAR",
      "scalar": { "value": 409600.0 }
    }
  ]
}
$ curl -d @executor-quota.json -X POST http://<master>:5050/quota

```

When Spark jobs are submitted they must indicate the role for which the Quota has been set in order to consume resources
from this quota, for example:

```bash
$ dcos spark run --verbose --name=spark --submit-args="\
--driver-cores=1 \
--driver-memory=1024M \
--conf spark.cores.max=8 \
--conf spark.mesos.role=executor \
--class org.apache.spark.examples.SparkPi \
http://downloads.mesosphere.com/spark/assets/spark-examples_2.11-2.0.1.jar 3000"

```

**Special consideration for streaming and long-running Spark jobs**: to prevent a single long-running or streaming Spark
job from consuming the entire Quota the max CPUs for that Spark job should be set to roughly one “job’s worth” of the
Quota’s resources. This ensures that the Spark job will get sufficient resources to make progress, setting the max CPUs
ensures it will not starve other Spark jobs of resources as well as predictable offer suppression semantics.

## Permissions when using Quota with Strict mode 

Strict mode clusters (see [security modes](https://docs.mesosphere.com/1.10/security/ent/#security-modes)) require extra
permissions to be set in order to use Quota. Follow the instructions in
[installing](https://github.com/mesosphere/spark-build/blob/master/docs/install.md) and add the additional permissions
for the roles you intend to use, detailed below. Following the example above they would be set as follows:

1.    First set Quota for the Dispatcher's role (`dispatcher`)

    ```bash
    $ cat dispatcher-quota.json
    {
     "role": "dispatcher",
     "guarantee": [
       {
         "name": "cpus",
         "type": "SCALAR",
         "scalar": { "value": 5.0 }
       },
       {
         "name": "mem",
         "type": "SCALAR",
         "scalar": { "value": 5120.0 }
       }
     ]
    }
    ```

    Then set the Quota *from your local machine*, this assumes you've downloaded the CA certificate,`dcos-ca.crt` to
    your local machine via the `https://<dcos_url>/ca/dcos-ca.crt` endpoint:
    
    ```bash
    curl -X POST --cacert dcos-ca.crt -H "Authorization: token=$(dcos config show core.dcos_acs_token)" $(dcos config show core.dcos_url)/mesos/quota -d @dispatcher-quota.json -H 'Content-Type: application/json'
    ```

1.    Optionally set Quota for the executors also, this is the same as above:

    ```bash
    $ cat executor-quota.json
    {
      "role": "executor",
      "guarantee": [
        {
          "name": "cpus",
          "type": "SCALAR",
          "scalar": { "value": 100.0 }
        },
        {
          "name": "mem",
          "type": "SCALAR",
          "scalar": { "value": 409600.0 }
        }
      ]
    }
    ```

    Then set the Quota from your local machine, again assuming you have `dcos-ca.crt` locally:

    ```bash
    curl -X POST --cacert dcos-ca.crt -H "Authorization: token=$(dcos config show core.dcos_acs_token)" $(dcos config show core.dcos_url)/mesos/quota -d @executor-quota.json -H 'Content-Type: application/json'
    ```

1.    Install Spark with these minimal configurations:

    ```bash
    { 
        "service": {
                "service_account": "spark-principal",
                "role": "dispatcher",
                "user": "root",
                "service_account_secret": "spark/spark-secret"
        }
    }
    ```

1.    Now you're ready to run a Spark job using the principal you set and the roles:

    ```bash
    dcos spark run --verbose --submit-args=" \
    --conf spark.mesos.principal=spark-principal \
    --conf spark.mesos.role=executor \
    --conf spark.mesos.containerizer=mesos \
    --class org.apache.spark.examples.SparkPi http://downloads.mesosphere.com/spark/assets/spark-examples_2.11-2.0.1.jar 100"
    ```

# Setting `spark.cores.max`

To improve Spark job execution reliability, set the maximum number of cores consumed by any given job.  This avoids
any particular Spark job consuming too many resources in a cluster.  It is highly recommended that each Spark job be
submitted with a limitation on the maximum number of cores (cpus) it can consume. This is especially important for
long-running and streaming Spark jobs. 

```bash
$ dcos spark run --verbose --name=spark --submit-args="\
--driver-cores=1 \
--driver-memory=1024M \
--conf spark.cores.max=8 \ #<< Very important!
--class org.apache.spark.examples.SparkPi \
http://downloads.mesosphere.com/spark/assets/spark-examples_2.11-2.0.1.jar 3000"
```

When running multiple concurrent Spark jobs, consider setting spark.cores.max between
`<total_executor_quota>/<max_concurrent_jobs>` and `<total_executor_quota>`, depending on your workload characteristics
and goals.

# Fine-grained mode

**Note** Fine-grained mode has been deprecated and does not have all of the features of coarse-grained mode.

In "fine-grained" mode, each Spark **task** is represented by a single Mesos task. When a Spark task finishes, the
resources represented by its Mesos task are relinquished. Fine-grained mode enables finer-grained resource allocation at
the cost of task startup latency.

*   **Executor memory**: `spark.executor.memory`
*   **Executor CPUs**: Increases and decreases as tasks start and terminate.
*   **Number of Executors**: Increases and decreases as tasks start and terminate.
*   **Executors per agent**: At most 1

# Properties

The following is a description of the most common Spark on Mesos scheduling properties. For a full list, see the [Spark
configuration page][1] and the [Spark on Mesos configuration page][2].

<table class="table">
<tr>
<th>property</th>
<th>default</th>
<th>description</th>
</tr>
	
<tr>
<td>spark.mesos.coarse</td>
<td>true</td>
<td>Described above.</td>
</tr>

<tr>
<td>spark.executor.memory</td>
<td>1g</td>
<td>Executor memory allocation.</td>
</tr>

<tr>
<td>spark.executor.cores</td>
<td>All available cores in the offer</td>
<td>Coarse-grained mode only. DC/OS Apache Spark >= 1.6.1. Executor CPU allocation.</td>
</tr>

<tr>
<td>spark.cores.max</td>
<td>unlimited</td>
<td>Maximum total number of cores to allocate.</td>
</tr>
</table>
 [1]: http://spark.apache.org/docs/latest/configuration.html
 [2]: http://spark.apache.org/docs/latest/running-on-mesos.html
