---
layout: layout.pug
excerpt:
title: Integration with HDFS
navigationTitle: HDFS
menuWeight: 20
---

# HDFS

If you plan to read and write from HDFS using Spark, there are two Hadoop configuration files that should be included on Spark's classpath: `hdfs-site.xml`, which provides default behaviors for the HDFS client. `core-site.xml`, which sets the default filesystem name. You can specify the location of these files at install time or for each job.

## Spark Installation
Within the Spark service configuration, set `hdfs.config-url` to be a URL that serves your `hdfs-site.xml` and `core-site.xml`, use this example where `http://mydomain.com/hdfs-config/hdfs-site.xml` and `http://mydomain.com/hdfs-config/core-site.xml` are valid URLs:

```json
{
  "hdfs": {
    "config-url": "http://mydomain.com/hdfs-config"
  }
}
```
This can also be done through the UI. If you are using the default installation of HDFS from Mesosphere this is probably `http://api.hdfs.marathon.l4lb.thisdcos.directory/v1/endpoints`.

## Adding HDFS configuration files per-job
To add the configuration files manually for a job, use `--conf spark.mesos.uris=<location_of_hdfs-site.xml>,<location_of_core-site.xml>`. This will download the files to the sandbox of the Driver Spark application, and DC/OS Spark will automatically load these files into the correct location. **Note** It is important these files are called `hdfs-site.xml` and `core-site.xml`.

### Spark Checkpointing

In order to use spark with checkpointing make sure you follow the instructions [here](https://spark.apache.org/docs/latest/streaming-programming-guide.html#checkpointing) and use an hdfs directory as the checkpointing directory. For example:
```
val checkpointDirectory = "hdfs://hdfs/checkpoint"
val ssc = ...
ssc.checkpoint(checkpointDirectory)
```
That hdfs directory will be automatically created on hdfs and spark streaming app will work from checkpointed data even in the presence of application restarts/failures.

# S3
You can read/write files to S3 using environment-based secrets to pass your AWS credentials. Your credentials must first be uploaded to the DC/OS secret store:

```
dcos security secrets create <secret_path_for_key_id> -v <AWS_ACCESS_KEY_ID>
dcos security secrets create <secret_path_for_secret_key> -v <AWS_SECRET_ACCESS_KEY> 
```
Then your Spark jobs can get these credentials directly:

```
dcos spark run --submit-args="\
...
--conf spark.mesos.containerizer=mesos  # required for secrets
--conf spark.mesos.driver.secret.names=<secret_path_for_key_id>,<secret_path_for_secret_key>
--conf spark.mesos.driver.secret.envkeys=AWS_ACCESS_KEY_ID,AWS_SECRET_ACCESS_KEY
...
```

[8]: http://spark.apache.org/docs/latest/configuration.html#inheriting-hadoop-cluster-configuration
[9]: https://docs.mesosphere.com/services/spark/2.1.0-2.2.0-1/limitations/
