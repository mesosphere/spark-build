Spark User's Guide
======================

* [Overview](#overview)
  * [Benefits](#benefits)
  * [Features](#features)
  * [Related Services](#related-services)
* [Quick Start](#quick-start)
* [Install](#install)
  * [Default](#default)
  * [Custom](#custom)
    * [HDFS](#hdfs)
    * [HDFS Kerberos](#hdfs-kerberos)
      * [Credentials](#credentials)
        * [Keytab](#keytab)
        * [Ticket](#ticket)
      * [HDFS Configuration](#hdfs-configuration)
      * [Installation](#installation)
    * [History Server](#history-server)
    * [SSL](#ssl)
  * [Multiple Install](#multiple-install)
* [Upgrade](#upgrade)
* [Run a Spark Job](#run-a-spark-job)
  * [Setting Spark properties](#setting-spark-properties)
    * [Submission](#submission)
    * [Configuration file](#configuration-file)
* [Uninstall](#uninstall)
* [Runtime Configuration Change](#runtime-configuration-change)
* [Troubleshooting](#troubleshooting-1)
  * [Dispatcher](#dispatcher)
  * [Jobs](#jobs)
  * [CLI](#cli)
* [Limitations](#limitations)

## Overview
Spark is a fast and general-purpose cluster computing system for big data. It
provides high-level APIs in Scala, Java, Python, and R, and an
optimized engine that supports general computation graphs for data
analysis. It also supports a rich set of higher-level tools including
Spark SQL for SQL and DataFrames, MLlib for machine learning, GraphX
for graph processing, and Spark Streaming for stream processing. For
more information, see the
[Apache Spark documentation][docs].

DCOS Spark includes:

- [Mesos Cluster Dispatcher][Mesos Cluster Mode].  
- [Spark History Server][Spark History Server].
- DCOS Spark CLI.

### Benefits

- Utilization: DCOS Spark leverages Mesos to run Spark on the same cluster as other DCOS services.
- Improved efficiency.
- Simple Management.
- Multi-team support.
- Interactive analytics through notebooks.
- UI integration.
- Security.

### Features

- Multiversion support.
- Run multiple Spark dispatchers.
- Run against multiple HDFS clusters.
- Backports of scheduling improvements.
- Simple installation of all Spark components, including the dispatcher and the history server.
- Integration of the dispatcher and history server.
- Zeppelin integration.
- Kerberos and SSL support.

### Related Services

[HDFS][DCOS HDFS]  
[Kafka][DCOS Kafka]  
[Zeppelin][DCOS Zeppelin]

## Quick Start

1. Install DCOS Spark via the DCOS CLI:

   ```bash
   $ dcos package install spark
   ```

2. Run a Spark job:

   ```bash
   $ dcos spark run --submit-args="--class org.apache.spark.examples.SparkPi
   http://downloads.mesosphere.com.s3.amazonaws.com/assets/spark/spark-examples_2.10-1.4.0-SNAPSHOT.jar
   30"
   ```

3. View your job:

   Visit the Spark cluster dispatcher at `http://<dcos-url>/service/spark/` to view the status of your job.  Also visit the Mesos UI at
   `http://<dcos-url>/mesos/` to see job logs.

## Install

### Default Installation

To start a basic Spark cluster, run the following command on the DCOS
CLI. This command installs the dispatcher, and, optionally, the history server. See "Custom Installation," below, to install the history server.

```
dcos package install spark
```

Monitor the deployment at `http://<dcos-url>/marathon`. Once it is
complete, visit Spark at `http://<dcos-url>/service/spark/`.

### Custom Installation

You can customize the default configuration properties by creating a JSON options file and passing it to `dcos package install --options`. For example, to install the history server, create a file called `options.json`:

```json
{
  "spark": {
    "history-server": {
      "enabled": true
    }
  }
}
```

Then, install Spark with your custom configuration:

```bash
dcos package install --options=options.json spark
```

Run the following command to see all configuration options:

``` bash
$ dcos package describe spark --config
```

#### HDFS

By default, DCOS Spark jobs are configured to read from DCOS HDFS. To
submit Spark jobs that read from a different HDFS cluster, customize `hdfs.config-url` to be a URL that serves `hdfs-site.xml` 
and `core-site.xml`. [Learn more][Spark Inheriting Hadoop Cluster Configuration].

For DCOS HDFS, these configuration files are served at
`http://<hdfs.framework-name>.marathon.mesos:<port>/config/`, where
`<hdfs.framework-name>` is a configuration variable set in the HDFS package, and
`<port>` is the port of its marathon app.

#### HDFS Kerberos

You can access external (i.e. non-DCOS) Kerberos-secured HDFS clusters
from Spark on Mesos.

##### Credentials

To authenticate to a Kerberos KDC on Spark, Mesos supports keytab
files as well as ticket files (TGTs), to log in with a given principal.

Keytabs are valid infinitely, while tickets can expire. Especially for
long-running streaming jobs, keytabs are recommended.

###### Keytab Authentication

On Unix machines with Heimdal Kerberos, the following command creates
a compatible keytab:

```bash
$ ktutil -k user.keytab add -p user@REALM -e aes256-cts-hmac-sha1-96 -V 1
```

To create: <!-- how could we be more precise? If we created the keytab in the previous step, what are we creating now? -->

```bash
$ dcos spark run --submit-args="--principal user@REALM --keytab <keytab-file-path>..."
```

###### TGT Authentication

On Unix machines with Heimdal Kerberos, the following command creates
a Ticket Granting Ticket (TGT), which is valid for 3 hours:

```bash
$ kinit -c user.tgt -f -l 3h -V user@REALM
```

To submit the ticket, run the following command:

```bash
$ dcos spark run --principal user@REALM --tgt <ticket-file-path> …
```

Note: These credentials are security-critical. We highly recommended
[configuring SSL encryption](#Configuring SSL Encryption) between the
Spark components when accessing Kerberos-secured HDFS clusters.

##### HDFS Configuration

Once you've set up a Kerberos-enabled HDFS cluster, configure
Spark to connect to it. See instructions [here][#Custom HDFS].

It is assumed that the HDFS namenodes are configured in the
core-site.xml of Hadoop in this way:

```
<property>
    <name>dfs.ha.namenodes.hdfs</name>
    <value>nn1,nn2</value>
 </property>

 <property>
    <name>dfs.namenode.rpc-address.hdfs.nn1</name>
    <value>server1:9000</value>
 </property>

 <property>
    <name>dfs.namenode.http-address.hdfs.nn1</name>
    <value>server1:50070</value>
 </property>

<property>
    <name>dfs.namenode.rpc-address.hdfs.nn2</name>
    <value>server2:9000</value>
 </property>

 <property>
    <name>dfs.namenode.http-address.hdfs.nn2</name>
    <value>server2:50070</value>
 </property>

```

##### Installation

To enable Kerberos in Spark, provide the following
configuration variable during installation: <!-- what does the rest of the JSON look like? -->

`spark.kerberos.krb5conf`

This is the base64 encoding of a `krb5.conf` file: <!-- does this need to happen before the step above? -->

```bash
$ cat krb5.conf | base64
W2xpYmRlZmF1bHRzXQogICAgICA….
```

This file tells Spark how to connect to your KDC.

#### History Server

DCOS Spark includes the
[Spark History Server][Spark History Server],
but it requires on HDFS, which you must explicitly enable it.

1. Install HDFS first:

   ```bash
   $ dcos package install hdfs
   ```

   **Note:** HDFS requires 5 private nodes.

2. Create a history HDFS directory (default is `/history`). [SSH into your cluster](https://docs.mesosphere.com/administration/sshcluster/) and run:

   ```bash
   $ hdfs dfs -mkdir /history
   ```

3. Enable the history server when you install Spark:

   `options.json`
   ```json
   {
     "spark": {
       "history-server": {
         "enabled": true
       }
     }
   }
   ```

4. Install Spark:

   ```bash
   $ dcos package install spark --options=options.json
   ```

5. Run jobs with the event log enabled:

   ```bash
   $ dcos spark run --submit-args=`-Dspark.eventLog.enabled=true
   -Dspark.eventLog.dir=hdfs://hdfs/history ... --class MySampleClass
   http://external.website/mysparkapp.jar`
   ```

6. Visit your job in the dispatcher at
   `http://<dcos_url>/service/spark/Dispatcher/`.  It will include a
   link to the history server entry for that job.


#### SSL

SSL support in DCOS Spark encrypts the following channels:

- From the DCOS admin router to the dispatcher.
- From the dispatcher to the drivers.
- From the drivers to their executors.

There are a number of configuration variables relevant to SSL setup. List them with the following command:

```bash
$ dcos package describe spark --config
```

There are only two required variables:

| Variable | Description |
| ----------- | --------------- |
| spark.ssl.enabled | Set to true to enable SSL (default: false). |
| spark.ssl.keyStoreBase64 | Base64 encoded blob containing a Java keystore. |

The Java keystore (and optionally truststore) are created using the
[Java keytool][Java Keytool]. The keystore must contain one private
key and its signed public key. The truststore is optional and might
contain a self-signed root-ca certificate that is explicitly trusted
by Java.

Both stores must be base64 encoded, e.g. by:

```bash
$ cat keystore | base64
/u3+7QAAAAIAAAACAAAAAgA...
```

**Note:** The base64 string of the keystore will probably be much longer than the snippet above,
spanning 50 lines or so.

With this and the password `secret` for the keystore and the private
key, your JSON options file will look like this:

```json
{
  "spark": {
    "ssl": {
      "enabled": true,
      "keyStoreBase64": "/u3+7QAAAAIAAAACAAAAAgA...”,
      "keyStorePassword": "secret",
      "keyPassword": "secret"
    }
  }
}
```

Install Spark with your custom configuration:

```bash
$ docs package install --options=options.json spark
```

In addition to the described configuration, make sure to connect the
DCOS cluster only using an SSL connection, i.e. by using an
`https://<dcos-url>`. Use the following command to set your connection URL:

```bash
$ dcos config set core.dcos_url https://<dcos-url>
```

### Multiple Install

Installing multiple instances of the DCOS Spark package provides basic
multi-team support. Each dispatcher displays only the jobs
submitted to it by a given team, and each team can be assigned different
resources.

To install mutiple instances of the DCOS Spark package, set each
`framework-name` to a unique name (e.g.: "spark-dev") in your JSON configuration file during
installation:

```
{
  "spark": {
    "framework-name": "spark-dev"
    }
}
```

To use a specific Spark instance from the DCOS Spark CLI:

```bash
$ dcos config set spark.app_id <framework-name>
```

## Upgrade
1. In the Marathon web interface, destroy the Spark instance to be
updated.
2. Verify that you no longer see it in the DCOS web interface.
3. Reinstall Spark.

```
dcos package install spark
```

## Run a Spark Job

1. Before submitting your job, upload the artifact (e.g., jar file)
   to a location visible to the cluster (e.g., S3 or HDFS). For more
   information, [see here][Spark Submitting Applications].

2. Run the job

   ```bash
   $ dcos spark run --submit-args=`--class MySampleClass
   http://external.website/mysparkapp.jar 30`
   ```

`dcos spark run` is a thin wrapper around the standard Spark `spark-submit` script.  You can submit arbitrary pass-through options to this script via the `--submit-args` options.

   The first time you run a job, the CLI must download the Spark
   distribution to your local machine. This may take a while.

   If your job runs successfully, you will get a message with the job’s submission ID:

   ```
   Run job succeeded. Submission id: driver-20160126183319-0001
   ```

3. View the Spark scheduler progress by navigating to the Spark
   dispatcher at `http://<dcos-url>/service/spark/`

4. View the job's logs through the Mesos UI at `http://<dcos-url>/mesos/`


### Setting Spark properties

Spark job settings are controlled by configuring
[Spark properties][Spark Properties].  You can set Spark properties
during submission, or you can create a configuration file.

#### Submission

All properties are submitted through the `--submit-args` option to
`dcos spark run`. These are ultimately passed to the
[`spark-submit` script][Spark Submitting Applications].

Certain common properties have their own special names.  You can view
these through `dcos spark run --help`. Here is an example of using
`--supervise`:

```bash
$ dcos spark run --submit-args="--supervise --class MySampleClass
http://external.website/mysparkapp.jar 30`
```

Or you can set arbitrary properties as java system properties by
using `-D<prop>=<value>`:

```bash
$ dcos spark run --submit-args="-Dspark.executor.memory=4g --class
MySampleClass http://external.website/mysparkapp.jar 30`
```

#### Configuration file

To set Spark properties with a configuration file, create a
`spark-defaults.conf` file and set the environment variable
`SPARK_CONF_DIR` to the containing directory.  For more info,
[see here][Spark Overriding Configuration Directory]


## Uninstall

``` bash
$ dcos package uninstall --app-id=<app-id> spark
```

The Spark Dispatcher persists state in Zookeeper, so to fully
uninstall the Spark DCOS package, you must go to
`http://<dcos-url>/exhibitor`, click on `Explorer`, and delete the znode
corresponding to your instance of Spark.  By default this is
`spark_mesos_Dispatcher`. <!-- Mohit's framework cleaner doesn't work for Spark? -->

## Runtime Configuration Change

You can customize DCOS Spark in-place when it is up and running.

1. View your Marathon dashboard at `http://<dcos-url>/marathon`

2. In the list of `Applications`, click the name of the Spark
   framework to be updated.

3. Within the Spark instance details view, click the `Configuration`
   tab, then click the `Edit` button.

4. In the dialog that appears, expand the `Environment Variables`
   section and update any field(s) to their desired value(s). <!-- are there any values that *should not* change? -->

5. Click `Change and deploy configuration` to apply any changes and
   cleanly reload Spark.

## Troubleshooting

### Dispatcher

The Mesos cluster dispatcher is responsible for queuing, tracking, and
supervising drivers. Potential problems may arise if the dispatcher
does not receive the resources offers you expect from Mesos, or if
driver submission is failing. To debug this class of issue,
visit the Mesos UI at `http://<dcos-url>/mesos/` and navigate to the
sandbox for the dispatcher.

### Jobs

- DCOS Spark jobs are submitted through the dispatcher, which displays
Spark properties and job state. Start here to verify that the job is
configured as you expect.

- The dispatcher further provides a link to the job's entry in the
history server, which will render the Spark Job UI. This UI renders
the schedule for the job. <!-- not sure what "render" means here -- "displays?" --> Go here to debug issues with scheduling and performance.

- Jobs themselves log output to their sandbox, which you can access
through the Mesos web interface. The Spark logs will be sent to `stderr`, while
any output you write in your job will be sent to `stdout`.

### CLI

The Spark CLI is integrated with the dispatcher so that they always use the
same version of Spark, and so that certain defaults are honored. To
debug issues with their communication, run your jobs with the `--verbose` flag.

### HDFS Kerberos

To debug authentication in a Spark job, enable Java security debug output:

```bash
$ dcos spark run --submit-args="-Dsun.security.krb5.debug=true..."
```

## Limitations

- Spark jobs run in Docker containers. The first time you run a Spark
job on a node, it might take longer than you expect because of the
`docker pull`.

- Spark shell is not supported. For interactive analytics, we recommend
Zeppelin, which supports visualizations and dynamic dependency
management.

[Spark Documentation]: http://spark.apache.org/documentation.html
[Spark History Server]:
http://spark.apache.org/docs/latest/monitoring.html#viewing-after-the-fact
[Spark Submitting Applications]:
http://spark.apache.org/docs/latest/submitting-applications.html
[Spark Properties]:
http://spark.apache.org/docs/latest/configuration.html#spark-properties
[Spark Overriding Configuration Directory]:
http://spark.apache.org/docs/latest/configuration.html#overriding-configuration-directory
[Spark Inheriting Hadoop Cluster Configuration]: http://spark.apache.org/docs/latest/configuration.html#inheriting-hadoop-cluster-configuration
[Mesos Cluster Mode]: http://spark.apache.org/docs/latest/running-on-mesos.html#cluster-mode
[DCOS HDFS]: https://docs.mesosphere.com/manage-service/hdfs/
[DCOS Kafka]: https://docs.mesosphere.com/manage-service/kafka/
[DCOS Zeppelin]: https://zeppelin.incubator.apache.org
[Java Keytool]: http://docs.oracle.com/javase/8/docs/technotes/tools/unix/keytool.html
