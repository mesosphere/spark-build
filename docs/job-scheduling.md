---
post_title: Job Scheduling
menu_order: 110
feature_maturity: stable
enterprise: 'no'
---

This document is a simple overview of material described in greater detail in the Apache Spark documentation [here][1] and [here][2].

# Modes

Spark on Mesos supports two "modes" of operation: coarse-grained mode and fine-grained mode. Coarse-grained mode provides lower latency, whereas fine-grained mode provides higher utilization. More info [here][2].

# Coarse-grained mode

"Coarse-grained" mode is so-called because each Spark **executor** is represented by a single Mesos task. As a result, executors have a constant size throughout their lifetime.

*   **Executor memory**: `spark.executor.memory`
*   **Executor CPUs**: `spark.executor.cores`, or all the cores in the offer.
*   **Number of Executors**: `spark.cores.max` / `spark.executor.cores`. Executors are brought up until `spark.cores.max` is reached. Executors survive for duration of the job.
*   **Executors per agent**: Multiple

Notes:

*   We highly recommend you set `spark.cores.max`. If you do not, your Spark job may consume all available resources in your cluster, resulting in unhappy peers.

# Fine-grained mode

In "fine-grained" mode, each Spark **task** is represented by a single Mesos task. When a Spark task finishes, the resources represented by its Mesos task are relinquished. Fine-grained mode enables finer-grained resource allocation at the cost of task startup latency.

*   **Executor memory**: `spark.executor.memory`
*   **Executor CPUs**: Increases and decreases as tasks start and terminate.
*   **Number of Executors**: Increases and decreases as tasks start and terminate.
*   **Executors per agent**: At most 1

# Properties

The following is a description of the most common Spark on Mesos scheduling properties. For a full list, see the [Spark configuration page][1] and the [Spark on Mesos configuration page][2].

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
<td>Coarse-grained mode only. DC/OS Spark >= 1.6.1. Executor CPU allocation.</td>
</tr>

<tr>
<td>spark.cores.max</td>
<td>unlimited</td>
<td>Maximum total number of cores to allocate.</td>
</tr>
</table>
 [1]: http://spark.apache.org/docs/latest/configuration.html
 [2]: http://spark.apache.org/docs/latest/running-on-mesos.html
