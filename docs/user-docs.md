# Overview

Spark is a fast and general-purpose cluster computing system for big data. It provides high-level APIs in Scala, Java, Python, and R, and an optimized engine that supports general computation graphs for data analysis. It also supports a rich set of higher-level tools including Spark SQL for SQL and DataFrames, MLlib for machine learning, GraphX for graph processing, and Spark Streaming for stream processing. For more information, see the [Apache Spark documentation][1].

DCOS Spark includes:

*   [Mesos Cluster Dispatcher][2]
*   [Spark History Server][3]
*   DCOS Spark CLI

## Benefits

*   Utilization: DCOS Spark leverages Mesos to run Spark on the same cluster as other DCOS services
*   Improved efficiency
*   Simple Management
*   Multi-team support
*   Interactive analytics through notebooks
*   UI integration
*   Security

## Features

*   Multiversion support
*   Run multiple Spark dispatchers
*   Run against multiple HDFS clusters
*   Backports of scheduling improvements
*   Simple installation of all Spark components, including the dispatcher and the history server
*   Integration of the dispatcher and history server
*   Zeppelin integration
*   Kerberos and SSL support

## Related Services

*   [HDFS][4]
*   [Kafka][5]
*   [Zeppelin][6]

# Quick Start

1.  Install DCOS Spark via the DCOS CLI:

    ```
    $ dcos package install spark
    ```

2.  Run a Spark job:

    ```
    $ dcos spark run --submit-args="--class org.apache.spark.examples.SparkPi http://downloads.mesosphere.com.s3.amazonaws.com/assets/spark/spark -examples_2.10-1.4.0-SNAPSHOT.jar 30"
    ```

3.  View your job:

    Visit the Spark cluster dispatcher at `http://<dcos-url>/service/spark/` to view the status of your job. Also visit the Mesos UI at `http://<dcos-url>/mesos/` to see job logs.

# Install

To start a basic Spark cluster, run the following command on the DCOS CLI. This command installs the dispatcher, and, optionally, the history server. See [Custom Installation][7] to install the history server.

```
$ dcos package install spark
```

Monitor the deployment at `http://<dcos-url>/marathon`. Once it is complete, visit Spark at `http://<dcos-url>/service/spark/`.

<a name="custom"></a>

## Custom Installation

You can customize the default configuration properties by creating a JSON options file and passing it to `dcos package install --options`. For example, to install the history server, create a file called `options.json`:

```
{
  "history-server": {
    "enabled": true
  }
}
```

Then, install Spark with your custom configuration:

```
$ dcos package install --options=options.json spark
```

Run the following command to see all configuration options:

```
$ dcos package describe spark --config
```

### Minimal Installation

For development purposes, you may wish to install Spark on a local
DCOS cluster. For this, you can use [dcos-vagrant][16].

1. Install DCOS Vagrant:

   Install a minimal DCOS Vagrant according to the instructions [here][16].

2. Install Spark:

   ```
   $ dcos package install spark
   ```

3. Run a simple Job:

   ```
   $ dcos spark run --submit-args="--class org.apache.spark.examples.SparkPi http://downloads.mesosphere.com.s3.amazonaws.com/assets/spark/spark-examples_2.10-1.5.0.jar"
   ```

NOTE: A limited resource environment such as DCOS Vagrant restricts
some of the features available in DCOS Spark.  For example, unless you
have enough resources to start up a 5-agent cluster, you will not be
able to install DCOS HDFS, and you thus won't be able to enable the
history server.

Also, a limited resource environment can restrict how you size your
executors, for example with `spark.executor.memory`.

<a name="hdfs"></a>

### HDFS

By default, DCOS Spark jobs are configured to read from DCOS HDFS. To submit Spark jobs that read from a different HDFS cluster, customize `hdfs.config-url` to be a URL that serves `hdfs-site.xml` and `core-site.xml`. [Learn more][8].

For DCOS HDFS, these configuration files are served at `http://<hdfs.framework-name>.marathon.mesos:<port>/config/`, where `<hdfs.framework-name>` is a configuration variable set in the HDFS package, and `<port>` is the port of its marathon app.

### HDFS Kerberos

You can access external (i.e. non-DCOS) Kerberos-secured HDFS clusters from Spark on Mesos.

#### Credentials

To authenticate to a Kerberos KDC on Spark, Mesos supports keytab files as well as ticket files (TGTs).

Keytabs are valid infinitely, while tickets can expire. Especially for long-running streaming jobs, keytabs are recommended.

##### Keytab Authentication

On Unix machines with Heimdal Kerberos, the following command creates a compatible keytab:

```
$ ktutil -k user.keytab add -p user@REALM -e aes256-cts-hmac-sha1-96 -V 1
```

Submit the job with the keytab:

```
$ dcos spark run --submit-args="--principal user@REALM --keytab &lt;keytab-file-path&gt;..."
```

##### TGT Authentication

On Unix machines with Heimdal Kerberos, the following command creates a Ticket Granting Ticket (TGT), which is valid for 3 hours:

```
$ kinit -c user.tgt -f -l 3h -V user@REALM
```

Submit the job with the ticket:

```
$ dcos spark run --principal user@REALM --tgt &lt;ticket-file-path&gt; …
```

**Note:** These credentials are security-critical. We highly recommended [configuring SSL encryption][9] between the Spark components when accessing Kerberos-secured HDFS clusters.

#### HDFS Configuration

Once you've set up a Kerberos-enabled HDFS cluster, configure Spark to
connect to it. See instructions [here](#hdfs).

It is assumed that the HDFS namenodes are configured in the core-site.xml of Hadoop in this way:

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

#### Installation

1.  Base64 encode your `krb5.conf` file:

    ```
    $ cat krb5.conf | base64 W2xpYmRlZmF1bHRzXQogICAgICA….
    ```

This file tells Spark how to connect to your KDC.

1.  Add the following to your JSON configuration file to enable Kerberos in Spark:

    ```
    {
      "security": {
        "kerberos": {
          "krb5conf": "W2xp..."
        }
      }
    }
    ```

2.  Install Spark with your custom configuration, here called `options.json`:

    ```
    $ dcos package install --options=options.json spark
    ```

### History Server

DCOS Spark includes the [Spark history server][3]. Because the history server requires HDFS, you must explicitly enable it.

1.  Install HDFS first:

    ```
    $ dcos package install hdfs
    ```

    **Note:** HDFS requires 5 private nodes.

2.  Create a history HDFS directory (default is `/history`). [SSH into your cluster][10] and run:

    ```
    $ hdfs dfs -mkdir /history
    ```

3.  Enable the history server when you install Spark. Create a JSON configuration file. Here we call it `options.json`:

    ```
    {
      "history-server": {
        "enabled": true
      }
    }
    ```

4.  Install Spark:

    ```
    $ dcos package install spark --options=options.json
    ```

5.  Run jobs with the event log enabled:

    ```
    $ dcos spark run --submit-args=`-Dspark.eventLog.enabled=true -Dspark.eventLog.dir=hdfs://hdfs/history ... --class MySampleClass http://external.website/mysparkapp.jar`
    ```

6.  Visit your job in the dispatcher at `http://<dcos_url>/service/spark/Dispatcher/`. It will include a link to the history server entry for that job.

<a name="ssl"></a>

### SSL

SSL support in DCOS Spark encrypts the following channels:

*   From the [DCOS admin router][11] to the dispatcher
*   From the dispatcher to the drivers
*   From the drivers to their executors

There are a number of configuration variables relevant to SSL setup. List them with the following command:

```
$ dcos package describe spark --config
```

There are only two required variables:

<table class="table">
  <tr>
    <th>
      Variable
    </th>

    <th>
      Description
    </th>
  </tr>

  <tr>
    <td>
      `spark.ssl.enabled`
    </td>

    <td>
      Set to true to enable SSL (default: false).
    </td>
  </tr>

  <tr>
    <td>
      spark.ssl.keyStoreBase64
    </td>

    <td>
      Base64 encoded blob containing a Java keystore.
    </td>
  </tr>
</table>

The Java keystore (and, optionally, truststore) are created using the [Java keytool][12]. The keystore must contain one private key and its signed public key. The truststore is optional and might contain a self-signed root-ca certificate that is explicitly trusted by Java.

Both stores must be base64 encoded, e.g. by:

```
$ cat keystore | base64 /u3+7QAAAAIAAAACAAAAAgA...
```

**Note:** The base64 string of the keystore will probably be much longer than the snippet above, spanning 50 lines or so.

With this and the password `secret` for the keystore and the private key, your JSON options file will look like this:

```
{
  "security": {
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

```
$ docs package install --options=options.json spark
```

In addition to the described configuration, make sure to connect the DCOS cluster only using an SSL connection, i.e. by using an `https://<dcos-url>`. Use the following command to set your DCOS URL:

```
$ dcos config set core.dcos_url https://&lt;dcos-url&gt;
```

## Multiple Install

Installing multiple instances of the DCOS Spark package provides basic multi-team support. Each dispatcher displays only the jobs submitted to it by a given team, and each team can be assigned different resources.

To install mutiple instances of the DCOS Spark package, set each `service.name` to a unique name (e.g.: "spark-dev") in your JSON configuration file during installation:

```
{
  "service": {
     "name": "spark-dev"
  }
}
```

To use a specific Spark instance from the DCOS Spark CLI:

```
$ dcos config set spark.app_id <service.name>
```

# Upgrade

1.  In the Marathon web interface, destroy the Spark instance to be updated.
2.  Verify that you no longer see it in the DCOS web interface.
3.  Reinstall Spark.

    ```
    $ dcos package install spark
    ```

# Run a Spark Job

1.  Before submitting your job, upload the artifact (e.g., jar file) to a location visible to the cluster (e.g., S3 or HDFS). [Learn more][13].

2.  Run the job

    ```
    $ dcos spark run --submit-args=`--class MySampleClass http://external.website/mysparkapp.jar 30`
    ```

    `dcos spark run` is a thin wrapper around the standard Spark `spark-submit` script. You can submit arbitrary pass-through options to this script via the `--submit-args` options.

    The first time you run a job, the CLI must download the Spark distribution to your local machine. This may take a while.

    If your job runs successfully, you will get a message with the job’s submission ID:

   ```
   Run job succeeded. Submission id: driver-20160126183319-0001
   ```

3.  View the Spark scheduler progress by navigating to the Spark dispatcher at `http://<dcos-url>/service/spark/`

4.  View the job's logs through the Mesos UI at `http://<dcos-url>/mesos/`

## Setting Spark properties

Spark job settings are controlled by configuring [Spark properties][14]. You can set Spark properties during submission, or you can create a configuration file.

### Submission

All properties are submitted through the `--submit-args` option to `dcos spark run`. These are ultimately passed to the [`spark-submit` script][13].

Certain common properties have their own special names. You can view these through `dcos spark run --help`. Here is an example of using `--supervise`:

```
$ dcos spark run --submit-args="--supervise --class MySampleClass http://external.website/mysparkapp.jar 30`
```


Or you can set arbitrary properties as java system properties by using `-D<prop>=<value>`:

```
$ dcos spark run --submit-args="-Dspark.executor.memory=4g --class MySampleClass http://external.website/mysparkapp.jar 30`
```

### Configuration file

To set Spark properties with a configuration file, create a `spark-defaults.conf` file and set the environment variable `SPARK_CONF_DIR` to the containing directory. [Learn more][15].

# Uninstall

```
$ dcos package uninstall --app-id=&lt;app-id&gt; spark
```

The Spark dispatcher persists state in Zookeeper, so to fully uninstall the Spark DCOS package, you must go to `http://<dcos-url>/exhibitor`, click on `Explorer`, and delete the znode corresponding to your instance of Spark. By default this is `spark_mesos_Dispatcher`.

# Runtime Configuration Change

You can customize DCOS Spark in-place when it is up and running.

1.  View your Marathon dashboard at `http://<dcos-url>/marathon`

2.  In the list of `Applications`, click the name of the Spark framework to be updated.

3.  Within the Spark instance details view, click the `Configuration` tab, then click the `Edit` button.

4.  In the dialog that appears, expand the `Environment Variables` section and update any field(s) to their desired value(s).

5.  Click `Change and deploy configuration` to apply any changes and cleanly reload Spark.

# Troubleshooting

## Dispatcher

The Mesos cluster dispatcher is responsible for queuing, tracking, and supervising drivers. Potential problems may arise if the dispatcher does not receive the resources offers you expect from Mesos, or if driver submission is failing. To debug this class of issue, visit the Mesos UI at `http://<dcos-url>/mesos/` and navigate to the sandbox for the dispatcher.

## Jobs

*   DCOS Spark jobs are submitted through the dispatcher, which displays Spark properties and job state. Start here to verify that the job is configured as you expect.

*   The dispatcher further provides a link to the job's entry in the history server, which displays the Spark Job UI. This UI shows the for the job. Go here to debug issues with scheduling and performance.

*   Jobs themselves log output to their sandbox, which you can access through the Mesos UI. The Spark logs will be sent to `stderr`, while any output you write in your job will be sent to `stdout`.

## CLI

The Spark CLI is integrated with the dispatcher so that they always use the same version of Spark, and so that certain defaults are honored. To debug issues with their communication, run your jobs with the `--verbose` flag.

## HDFS Kerberos

To debug authentication in a Spark job, enable Java security debug output:

```
$ dcos spark run --submit-args="-Dsun.security.krb5.debug=true..."
```

# Limitations

*   DCOS Spark only supports submitting jars.  It does not support Python or R.

*   Spark jobs run in Docker containers. The first time you run a Spark job on a node, it might take longer than you expect because of the `docker pull`.

*   Spark shell is not supported. For interactive analytics, we recommend Zeppelin, which supports visualizations and dynamic dependency management.

 [1]: http://spark.apache.org/documentation.html
 [2]: http://spark.apache.org/docs/latest/running-on-mesos.html#cluster-mode
 [3]: http://spark.apache.org/docs/latest/monitoring.html#viewing-after-the-fact
 [4]: https://docs.mesosphere.com/manage-service/hdfs/
 [5]: https://docs.mesosphere.com/manage-service/kafka/
 [6]: https://zeppelin.incubator.apache.org/
 [7]: #custom
 [8]: http://spark.apache.org/docs/latest/configuration.html#inheriting-hadoop-cluster-configuration
 [9]: #ssl
 [10]: https://docs.mesosphere.com/administration/sshcluster/
 [11]: https://docs.mesosphere.com/administration/dcosarchitecture/components/
 [12]: http://docs.oracle.com/javase/8/docs/technotes/tools/unix/keytool.html
 [13]: http://spark.apache.org/docs/latest/submitting-applications.html
 [14]: http://spark.apache.org/docs/latest/configuration.html#spark-properties
 [15]: http://spark.apache.org/docs/latest/configuration.html#overriding-configuration-directory
 [16]: https://github.com/mesosphere/dcos-vagrant
