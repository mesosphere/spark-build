---
layout: layout.pug
navigationTitle: 
excerpt:
title: Fault Tolerance
menuWeight: 100
featureMaturity:

---

Failures such as host, network, JVM, or application failures can affect the behavior of three types of Spark components:

- DC/OS Apache Spark Service
- Batch Jobs
- Streaming Jobs

# DC/OS Apache Spark Service

The DC/OS Apache Spark service runs in Marathon and includes the Mesos Cluster Dispatcher and the Spark History Server.  The Dispatcher manages jobs you submit via `dcos spark run`.  Job data is persisted to Zookeeper. The Spark History Server reads event logs from HDFS. If the service dies, Marathon will restart it, and it will reload data from these highly available stores.

# Batch Jobs

Batch jobs are resilient to executor failures, but not driver failures.  The Dispatcher will restart a driver if you submit with `--supervise`.

## Driver

When the driver fails, executors are terminated, and the entire Spark application fails.  If you submitted your job with `--supervise`, then the Dispatcher will restart the job.

## Executors

Batch jobs are resilient to executor failure.  Upon failure, cached data, shuffle files, and partially computed RDDs are lost.  However, Spark RDDs are fault-tolerant, and Spark will start a new executor to recompute this data from the original data source, caches, or shuffle files.  There is a performance cost as data is recomputed, but an executor failure will not cause a job to fail.

# Streaming Jobs

Whereas batch jobs run once and can usually be restarted upon failure, streaming jobs often need to run constantly.  The application must survive driver failures, often with no data loss.

In summary, to experience no data loss, you must run with the WAL enabled.  The one exception is that, if you're consuming from Kafka, you can use the Direct Kafka API.

For exactly once processing semantics, you must use the Direct Kafka API.  All other receivers provide at least once semantics.

## Failures

There are two types of failures:

- Driver
- Executor

## Job Features

There are a few variables that affect the reliability of your job:

- [WAL][1]
- [Receiver reliability][2]
- [Storage level][3]

## Reliability Features

The two reliability features of a job are data loss and processing semantics.  Data loss occurs when the source sends data, but the job fails to process it.  Processing semantics describe how many times a received message is processed by the job.  It can be either "at least once" or "exactly once"

### Data loss

A Spark Job loses data when delivered data does not get processed. The following is a list of configurations with increasing data preservation guarantees:

- Unreliable receivers

Unreliable receivers do not ack data they receive from the source. This means that buffered data in the receiver will be lost upon executor failure.

executor failure => **data loss** driver failure => **data loss**

- Reliable receivers, unreplicated storage level

This is an unusual configuration.  By default, Spark Streaming receivers run with a replicated storage level.  But if you happen reduce the storage level to be unreplicated, data stored on the receiver but not yet processed will not survive executor failure.

  executor failure => **data loss**  
  driver failure => **data loss**

- Reliable receivers, replicated storage level

This is the default configuration.  Data stored in the receiver is replicated, and can thus survive a single executor failure.  Driver failures, however, result in all executors failing, and therefore result in data loss.

  (single) executor failure => **no data loss**  
  driver failure => **data loss**

- Reliable receivers, WAL

With a WAL enabled, data stored in the receiver is written to a highly available store such as S3 or HDFS.  This means that an app can recover from even a driver failure.

  executor failure => **no data loss**  
  driver failure => **no data loss**

- Direct Kafka Consumer, no checkpointing

Since Spark 1.3, The Spark+Kafka integration has supported an experimental Direct Consumer, which doesn't use traditional receivers.  With the direct approach, RDDs read directly from kafka, rather than buffering data in receivers.

However, without checkpointing, driver restarts mean that the driver will start reading from the latest Kafka offset, rather than where the previous driver left off.

  executor failure => **no data loss**  
  driver failure => **data loss**

- Direct Kafka Consumer, checkpointing

With checkpointing enabled, Kafka offsets are stored in a reliable store such as HDFS or S3.  This means that an application can restart exactly where it left off.

  executor failure => **no data loss**  
  driver failure => **no data loss**

### Processing semantics

Processing semantics apply to how many times received messages get processed.  With Spark Streaming, this can be either "at least once" or "exactly once".

The semantics below describe apply to Spark's receipt of the data.  To provide an end-to-end exactly-once guarantee, you must additionally verify that your output operation provides exactly-once guarantees. More info [here][4].

- Receivers

  **at least once**

Every Spark Streaming consumer, with the exception of the Direct Kafka Consumer described below, uses receivers.  Receivers buffer blocks of data in memory, then write them according to the storage level of the job.  After writing out the data, it will send an ack to the source so the source knows not to resend.  However, if this ack fails, or the node fails between writing out the data and sending the ack, then an inconsistency arises.  Spark believes that the data has been received, but the source does not.  This results in the source resending the data, and it being processed twice.

- Direct Kafka Consumer

  **exactly once**

The Direct Kafka Consumer avoids the problem described above by reading directly from Kafka, and storing the offsets itself in the checkpoint directory.

  More information [here][5].


[1]: https://spark.apache.org/docs/1.6.0/streaming-programming-guide.html#requirements
[2]: https://spark.apache.org/docs/1.6.0/streaming-programming-guide.html#with-receiver-based-sources
[3]: http://spark.apache.org/docs/latest/programming-guide.html#which-storage-level-to-choose
[4]: http://spark.apache.org/docs/latest/streaming-programming-guide.html#semantics-of-output-operations
[5]: https://databricks.com/blog/2015/03/30/improvements-to-kafka-integration-of-spark-streaming.html
