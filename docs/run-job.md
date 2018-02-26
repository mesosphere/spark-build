---
layout: layout.pug
navigationTitle: 
excerpt:
title: Run a Spark Job
menuWeight: 80
featureMaturity:

---
1.  Before submitting your job, upload the artifact (e.g., jar file)
    to a location visible to the cluster (e.g., HTTP, S3, or HDFS). [Learn more][13].

1.  Run the job.
    Include all configuration flags before the jar url and the args for your spark job after the jar url. Generally following the template `dcos spark run --submit-args="<flags> URL [args]` where `<flags>` can be things like `--conf spark.cores.max=16` and `--class my.aprk.App`, `URL` is the location of the application, and `[args]` are any arguments for the application.
        
        dcos spark run --submit-args=--class MySampleClass http://external.website/mysparkapp.jar"

        dcos spark run --submit-args="--py-files mydependency.py http://external.website/mysparkapp.py"

        dcos spark run --submit-args="http://external.website/mysparkapp.R"

	If your job runs successfully, you will get a message with the job’s submission ID:

        Run job succeeded. Submission id: driver-20160126183319-0001

1.  View the Spark scheduler progress by navigating to the Spark dispatcher at `http://<dcos-url>/service/spark/`.

1.  View the job's logs through the Mesos UI at `http://<dcos-url>/mesos/`. Or `dcos task log --follow <submission_id>`

# Setting Spark properties

Spark job settings are controlled by configuring [Spark properties][14].

## Submission

All properties are submitted through the `--submit-args` option to `dcos spark run`. There are a few unique options to DC/OS that are not in Spark Submit (for example `--keytab-secret-path`).  View `dcos spark run --help` for a list of all these options. All `--conf` properties supported by Spark can be passed through the command-line with within the `--submit-args` string. 

    dcos spark run --submit-args="--conf spark.executor.memory=4g --supervise --class MySampleClass http://external.website/mysparkapp.jar 30`

## Setting automatic configuration defaults

To set Spark properties with a configuration file, create a
`spark-defaults.conf` file and set the environment variable
`SPARK_CONF_DIR` to the containing directory. [Learn more][15].

## Using a properties file

To reuse spark properties without cluttering the command line the CLI supports passing a path to a local file containing Spark properties. Such a file is whitespace separated properties and values, for example
```text
spark.mesos.containerizer   mesos
spark.executors.cores       4
spark.eventLog.enabled      true
spark.eventLog.dir          hdfs:///history
```
will set the containerizer to `mesos`, the executor cores to `4` and enable the history server. This file is parsed locally so it will not be available to your driver applications. 


## Secrets

Enterprise DC/OS provides a secrets store to enable access to sensitive data such as database passwords,
private keys, and API tokens. DC/OS manages secure transportation of secret data, access control and
authorization, and secure storage of secret content. A secret can be exposed to drivers and executors
as a file and/or as an environment variable. To configure a job to access a secret, see the sections on
[Using the Secret Store][../security/#using-the-secret-store] and
[Using Mesos Secrets][../security/#using-mesos-secrets].

# DC/OS Overlay Network

To submit a Spark job inside the [DC/OS Overlay Network][16]:

    dcos spark run --submit-args="--conf spark.mesos.containerizer=mesos --conf spark.mesos.network.name=dcos --class MySampleClass http://external.website/mysparkapp.jar"

Note that DC/OS Overlay support requires the [UCR][17], rather than
the default Docker Containerizer, so you must set `--conf spark.mesos.containerizer=mesos`.

# Driver Failover Timeout

The `--conf spark.mesos.driver.failoverTimeout` option specifies the amount of time 
(in seconds) that the master will wait for the driver to reconnect, after being 
temporarily disconnected, before it tears down the driver framework by killing 
all its executors. The default value is zero, meaning no timeout: if the 
driver disconnects, the master immediately tears down the framework.

To submit a job with a nonzero failover timeout:

    dcos spark run --submit-args="--conf spark.mesos.driver.failoverTimeout=60 --class MySampleClass http://external.website/mysparkapp.jar"

**Note:** If you kill a job before it finishes, the framework will persist 
as an `inactive` framework in Mesos for a period equal to the failover timeout. 
You can manually tear down the framework before that period is over by hitting
the [Mesos teardown endpoint][18].

# Versioning

The DC/OS Apache Spark Docker image contains OpenJDK 8 and Python 2.7.6.

DC/OS Apache Spark distributions 1.X are compiled with Scala 2.10.  DC/OS Apache Spark distributions 2.X are compiled with Scala 2.11.  Scala is not binary compatible across minor verions, so your Spark job must be compiled with the same Scala version as your version of DC/OS Apache Spark.

The default DC/OS Apache Spark distribution is compiled against Hadoop 2.6 libraries.  However, you may choose a different version by following the instructions in the "Customize Spark Distribution" section of the Installation page.


[13]: http://spark.apache.org/docs/latest/submitting-applications.html
[14]: http://spark.apache.org/docs/latest/configuration.html#spark-properties
[15]: http://spark.apache.org/docs/latest/configuration.html#overriding-configuration-directory
[16]: https://dcos.io/docs/overview/design/overlay/
[17]: https://dcos.io/docs/1.9/deploying-services/containerizers/ucr/
[18]: http://mesos.apache.org/documentation/latest/endpoints/master/teardown/
[19]: https://docs.mesosphere.com/services/spark/v2.2.0-2.2.0-1/hdfs/
