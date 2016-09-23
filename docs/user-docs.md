# Overview

Apache Spark is a fast and general-purpose cluster computing system for big
data. It provides high-level APIs in Scala, Java, Python, and R, and
an optimized engine that supports general computation graphs for data
analysis. It also supports a rich set of higher-level tools including
Spark SQL for SQL and DataFrames, MLlib for machine learning, GraphX
for graph processing, and Spark Streaming for stream processing. For
more information, see the [Apache Spark documentation][1].

Apache DC/OS Spark consists of
[Apache Spark with a few custom commits][17]
along with
[DC/OS-specific packaging][18].

DC/OS Spark includes:

*   [Mesos Cluster Dispatcher][2]
*   [Spark History Server][3]
*   DC/OS Spark CLI

## Benefits

*   Utilization: DC/OS Spark leverages Mesos to run Spark on the same
cluster as other DC/OS services
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
*   Simple installation of all Spark components, including the
dispatcher and the history server
*   Integration of the dispatcher and history server
*   Zeppelin integration
*   Kerberos and SSL support

## Related Services

*   [HDFS][4]
*   [Kafka][5]
*   [Zeppelin][6]

<a name="quick-start"></a>
# Quick Start

1.  Install DC/OS Spark via the DC/OS CLI:

        $ dcos package install spark

1.  Run a Spark job:

        $ dcos spark run --submit-args="--class org.apache.spark.examples.SparkPi http://downloads.mesosphere.com.s3.amazonaws.com/assets/spark/spark-examples_2.10-1.4.0-SNAPSHOT.jar 30"

1.  View your job:

    Visit the Spark cluster dispatcher at
`http://<dcos-url>/service/spark/` to view the status of your job.
Also visit the Mesos UI at `http://<dcos-url>/mesos/` to see job logs.

<a name="install"></a>
# Install

To start a basic Spark cluster, run the following command on the DC/OS
CLI. This command installs the dispatcher, and, optionally, the
history server. See [Custom Installation][7] to install the history
server.

    $ dcos package install spark

Monitor the deployment at `http://<dcos-url>/marathon`. Once it is
complete, visit Spark at `http://<dcos-url>/service/spark/`.

You can also
[install Spark via the DC/OS web interface](/usage/services/install/).
**Note:** If you install Spark via the web interface, run the
following command from the DC/OS CLI to install the Spark CLI:

    $ dcos package install spark --cli

<a name="custom"></a>

## Custom Installation

You can customize the default configuration properties by creating a
JSON options file and passing it to `dcos package install --options`.
For example, to install the history server, create a file called
`options.json`:

    {
      "history-server": {
        "enabled": true
      }
    }

Then, install Spark with your custom configuration:

    $ dcos package install --options=options.json spark

Run the following command to see all configuration options:

    $ dcos package describe spark --config

### Minimal Installation

For development purposes, you may wish to install Spark on a local
DC/OS cluster. For this, you can use [dcos-vagrant][16].

1. Install DC/OS Vagrant:

   Install a minimal DC/OS Vagrant according to the instructions
[here][16].

1. Install Spark:

        $ dcos package install spark

1. Run a simple Job:

        $ dcos spark run --submit-args="--class org.apache.spark.examples.SparkPi http://downloads.mesosphere.com.s3.amazonaws.com/assets/spark/spark-examples_2.10-1.5.0.jar"

NOTE: A limited resource environment such as DC/OS Vagrant restricts
some of the features available in DC/OS Spark.  For example, unless you
have enough resources to start up a 5-agent cluster, you will not be
able to install DC/OS HDFS, and you thus won't be able to enable the
history server.

Also, a limited resource environment can restrict how you size your
executors, for example with `spark.executor.memory`.

<a name="hdfs"></a>

### HDFS

To configure Spark for a specific HDFS cluster, configure
`hdfs.config-url` to be a URL that serves your `hdfs-site.xml` and
`core-site.xml`. For example:

    {
      "hdfs": {
        "config-url": "http://mydomain.com/hdfs-config"
      }
    }


where `http://mydomain.com/hdfs-config/hdfs-site.xml` and
`http://mydomain.com/hdfs-config/core-site.xml` are valid
URLs.[Learn more][8].

For DC/OS HDFS, these configuration files are served at
`http://<hdfs.framework-name>.marathon.mesos:<port>/v1/connect`, where
`<hdfs.framework-name>` is a configuration variable set in the HDFS
package, and `<port>` is the port of its marathon app.

### HDFS Kerberos

You can access external (i.e. non-DC/OS) Kerberos-secured HDFS clusters
from Spark on Mesos.

#### HDFS Configuration

Once you've set up a Kerberos-enabled HDFS cluster, configure Spark to
connect to it. See instructions [here](#hdfs).

#### Installation

1.  A krb5.conf file tells Spark how to connect to your KDC.  Base64
    encode this file:

        $ cat krb5.conf | base64

1.  Add the following to your JSON configuration file to enable
Kerberos in Spark:

        {
           "security": {
             "kerberos": {
              "krb5conf": "<base64 encoding>"
              }
           }
        }

1. If you've enabled the history server via `history-server.enabled`,
you must also configure the principal and keytab for the history
server.  **WARNING**: The keytab contains secrets, so you should
ensure you have SSL enabled while installing DC/OS Spark.

    Base64 encode your keytab:

        $ cat spark.keytab | base64

    And add the following to your configuration file:

         {
            "history-server": {
                "kerberos": {
                  "principal": "spark@REALM",
                  "keytab": "<base64 encoding>"
                }
            }
         }

1.  Install Spark with your custom configuration, here called
`options.json`:

        $ dcos package install --options=options.json spark

#### Job Submission

To authenticate to a Kerberos KDC, DC/OS Spark supports keytab
files as well as ticket-granting tickets (TGTs).

Keytabs are valid infinitely, while tickets can expire. Especially for
long-running streaming jobs, keytabs are recommended.

##### Keytab Authentication

Submit the job with the keytab:

    $ dcos spark run --submit-args="--principal user@REALM --keytab <keytab-file-path>..."

##### TGT Authentication

Submit the job with the ticket:

    $ dcos spark run --principal user@REALM --tgt <ticket-file-path>

**Note:** These credentials are security-critical. We highly
recommended [configuring SSL encryption][9] between the Spark
components when accessing Kerberos-secured HDFS clusters.


### History Server

DC/OS Spark includes the [Spark history server][3]. Because the history
server requires HDFS, you must explicitly enable it.

1.  Install HDFS first:

        $ dcos package install hdfs

    **Note:** HDFS requires 5 private nodes.

1.  Create a history HDFS directory (default is `/history`). [SSH into
your cluster][10] and run:

        $ hdfs dfs -mkdir /history

1.  Enable the history server when you install Spark. Create a JSON
configuration file. Here we call it `options.json`:

        {
           "history-server": {
             "enabled": true
           }
        }

1.  Install Spark:

        $ dcos package install spark --options=options.json

1.  Run jobs with the event log enabled:

        $ dcos spark run --submit-args="-Dspark.eventLog.enabled=true -Dspark.eventLog.dir=hdfs://hdfs/history ... --class MySampleClass  http://external.website/mysparkapp.jar"

1.  Visit your job in the dispatcher at
`http://<dcos_url>/service/spark/Dispatcher/`. It will include a link
to the history server entry for that job.

<a name="ssl"></a>

### SSL

SSL support in DC/OS Spark encrypts the following channels:

*   From the [DC/OS admin router][11] to the dispatcher
*   From the dispatcher to the drivers
*   From the drivers to their executors

There are a number of configuration variables relevant to SSL setup.
List them with the following command:

    $ dcos package describe spark --config

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

The Java keystore (and, optionally, truststore) are created using the
[Java keytool][12]. The keystore must contain one private key and its
signed public key. The truststore is optional and might contain a
self-signed root-ca certificate that is explicitly trusted by Java.

Both stores must be base64 encoded, e.g. by:

    $ cat keystore | base64 /u3+7QAAAAIAAAACAAAAAgA...

**Note:** The base64 string of the keystore will probably be much
longer than the snippet above, spanning 50 lines or so.

With this and the password `secret` for the keystore and the private
key, your JSON options file will look like this:

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

Install Spark with your custom configuration:

    $ dcos package install --options=options.json spark

In addition to the described configuration, make sure to connect the
DC/OS cluster only using an SSL connection, i.e. by using an
`https://<dcos-url>`. Use the following command to set your DC/OS URL:

    $ dcos config set core.dcos_url https://<dcos-url>

## Multiple Install

Installing multiple instances of the DC/OS Spark package provides basic
multi-team support. Each dispatcher displays only the jobs submitted
to it by a given team, and each team can be assigned different
resources.

To install mutiple instances of the DC/OS Spark package, set each
`service.name` to a unique name (e.g.: "spark-dev") in your JSON
configuration file during installation:

    {
      "service": {
        "name": "spark-dev"
      }
    }

To use a specific Spark instance from the DC/OS Spark CLI:

    $ dcos config set spark.app_id <service.name>

<a name="upgrade"></a>
# Upgrade

1.  In the Marathon web interface, destroy the Spark instance to be
updated.
1.  Verify that you no longer see it in the DC/OS web interface.
1.  Reinstall Spark.

        $ dcos package install spark

<a name="run-a-spark-job"></a>
# Run a Spark Job

1.  Before submitting your job, upload the artifact (e.g., jar file)
to a location visible to the cluster (e.g., S3 or HDFS). [Learn
more][13].

1.  Run the job

        $ dcos spark run --submit-args=`--class MySampleClass http://external.website/mysparkapp.jar 30`

    `dcos spark run` is a thin wrapper around the standard Spark
`spark-submit` script. You can submit arbitrary pass-through options
to this script via the `--submit-args` options.

    The first time you run a job, the CLI must download the Spark
distribution to your local machine. This may take a while.

    If your job runs successfully, you will get a message with the
job’s submission ID:

        Run job succeeded. Submission id: driver-20160126183319-0001

1.  View the Spark scheduler progress by navigating to the Spark
dispatcher at `http://<dcos-url>/service/spark/`

1.  View the job's logs through the Mesos UI at
`http://<dcos-url>/mesos/`

## Setting Spark properties

Spark job settings are controlled by configuring [Spark
properties][14]. You can set Spark properties during submission, or
you can create a configuration file.

### Submission

All properties are submitted through the `--submit-args` option to
`dcos spark run`. These are ultimately passed to the [`spark-submit`
script][13].

Certain common properties have their own special names. You can view
these through `dcos spark run --help`. Here is an example of using
`--supervise`:

    $ dcos spark run --submit-args="--supervise --class MySampleClass http://external.website/mysparkapp.jar 30`

Or you can set arbitrary properties as java system properties by using
`-D<prop>=<value>`:

    $ dcos spark run --submit-args="-Dspark.executor.memory=4g --class MySampleClass http://external.website/mysparkapp.jar 30`

### Configuration file

To set Spark properties with a configuration file, create a
`spark-defaults.conf` file and set the environment variable
`SPARK_CONF_DIR` to the containing directory. [Learn more][15].

<a name="uninstall"></a>
# Uninstall

    $ dcos package uninstall --app-id=<app-id> spark

The Spark dispatcher persists state in Zookeeper, so to fully
uninstall the Spark DC/OS package, you must go to
`http://<dcos-url>/exhibitor`, click on `Explorer`, and delete the
znode corresponding to your instance of Spark. By default this is
`spark_mesos_Dispatcher`.

<a name="runtime-configuration-change"></a>
# Runtime Configuration Change

You can customize DC/OS Spark in-place when it is up and running.

1.  View your Marathon dashboard at `http://<dcos-url>/marathon`

1.  In the list of `Applications`, click the name of the Spark
framework to be updated.

1.  Within the Spark instance details view, click the `Configuration`
tab, then click the `Edit` button.

1.  In the dialog that appears, expand the `Environment Variables`
section and update any field(s) to their desired value(s).

1.  Click `Change and deploy configuration` to apply any changes and
cleanly reload Spark.

<a name="troubleshooting"></a>
# Troubleshooting

## Dispatcher

The Mesos cluster dispatcher is responsible for queuing, tracking, and
supervising drivers. Potential problems may arise if the dispatcher
does not receive the resources offers you expect from Mesos, or if
driver submission is failing. To debug this class of issue, visit the
Mesos UI at `http://<dcos-url>/mesos/` and navigate to the sandbox for
the dispatcher.

## Jobs

*   DC/OS Spark jobs are submitted through the dispatcher, which
displays Spark properties and job state. Start here to verify that the
job is configured as you expect.

*   The dispatcher further provides a link to the job's entry in the
history server, which displays the Spark Job UI. This UI shows the for
the job. Go here to debug issues with scheduling and performance.

*   Jobs themselves log output to their sandbox, which you can access
through the Mesos UI. The Spark logs will be sent to `stderr`, while
any output you write in your job will be sent to `stdout`.

## CLI

The Spark CLI is integrated with the dispatcher so that they always
use the same version of Spark, and so that certain defaults are
honored. To debug issues with their communication, run your jobs with
the `--verbose` flag.

## HDFS Kerberos

To debug authentication in a Spark job, enable Java security debug
output:

    $ dcos spark run --submit-args="-Dsun.security.krb5.debug=true..."

<a name="limitations"></a>
# Limitations

*   DC/OS Spark only supports submitting jars.  It does not support
Python or R.

*   Spark jobs run in Docker containers. The first time you run a
Spark job on a node, it might take longer than you expect because of
the `docker pull`.

*   Spark shell is not supported. For interactive analytics, we
recommend Zeppelin, which supports visualizations and dynamic
dependency management.

 [1]: http://spark.apache.org/documentation.html
 [2]: http://spark.apache.org/docs/latest/running-on-mesos.html#cluster-mode
 [3]: http://spark.apache.org/docs/latest/monitoring.html#viewing-after-the-fact
 [4]: https://docs.mesosphere.com/manage-service/hdfs/
 [5]: https://docs.mesosphere.com/manage-service/kafka/
 [6]: https://zeppelin.incubator.apache.org/
 [7]: #custom
 [8]: http://spark.apache.org/docs/latest/configuration.html#inheriting-hadoop-cluster-configuration
 [9]: #ssl
 [10]: https://docs.mesosphere.com/administration/access-node/sshcluster/
 [11]: https://docs.mesosphere.com/administration/dcosarchitecture/components/
 [12]: http://docs.oracle.com/javase/8/docs/technotes/tools/unix/keytool.html
 [13]: http://spark.apache.org/docs/latest/submitting-applications.html
 [14]: http://spark.apache.org/docs/latest/configuration.html#spark-properties
 [15]: http://spark.apache.org/docs/latest/configuration.html#overriding-configuration-directory
 [16]: https://github.com/mesosphere/dcos-vagrant
 [17]: https://github.com/mesopshere/spark
 [18]: https://github.com/mesopshere/spark-build
