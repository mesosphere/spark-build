---
post_title: Configure Spark for HDFS
nav_title: HDFS
menu_order: 20
enterprise: 'no'
---

You can configure Spark for a specific HDFS cluster.

To configure `hdfs.config-url` to be a URL that serves your `hdfs-site.xml` and `core-site.xml`, use this example where `http://mydomain.com/hdfs-config/hdfs-site.xml` and `http://mydomain.com/hdfs-config/core-site.xml` are valid URLs:

```json
{
  "hdfs": {
    "config-url": "http://mydomain.com/hdfs-config"
  }
}
```

For more information, see [Inheriting Hadoop Cluster Configuration][8].

For DC/OS HDFS, these configuration files are served at `http://<hdfs.framework-name>.marathon.mesos:<port>/v1/endpoints`, where `<hdfs.framework-name>` is a configuration variable set in the HDFS package, and `<port>` is the port of its marathon app.

### Spark Checkpointing

In order to use spark with checkpointing make sure you follow the instructions [here](https://spark.apache.org/docs/latest/streaming-programming-guide.html#checkpointing) and use an hdfs directory as the checkpointing directory. For example:
```
val checkpointDirectory = "hdfs://hdfs/checkpoint"
val ssc = ...
ssc.checkpoint(checkpointDirectory)
```
That hdfs directory will be automatically created on hdfs and spark streaming app will work from checkpointed data even in the presence of application restarts/failures.

# HDFS Kerberos

You can access external (i.e. non-DC/OS) Kerberos-secured HDFS clusters from Spark on Mesos.

## HDFS Configuration

After you've set up a Kerberos-enabled HDFS cluster, configure Spark to connect to it. See instructions [here](#hdfs).

## Installation

1.  A `krb5.conf` file tells Spark how to connect to your KDC.  Base64 encode this file:

        cat krb5.conf | base64

1.  Add the following to your JSON configuration file to enable Kerberos in Spark:

        {
           "security": {
             "kerberos": {
              "krb5conf": "<base64 encoding>"
              }
           }
        }

1. If you've enabled the history server via `history-server.enabled`, you must also configure the principal and keytab for the history server.  **WARNING**: The keytab contains secrets, so you should ensure you have SSL enabled while installing DC/OS Apache Spark.

    Base64 encode your keytab:

        cat spark.keytab | base64

    And add the following to your configuration file:

         {
            "history-server": {
                "kerberos": {
                  "principal": "spark@REALM",
                  "keytab": "<base64 encoding>"
                }
            }
         }

1.  Install Spark with your custom configuration, here called `options.json`:

        dcos package install --options=options.json spark

## Job Submission

To authenticate to a Kerberos KDC, DC/OS Apache Spark supports keytab files as well as ticket-granting tickets (TGTs).

Keytabs are valid infinitely, while tickets can expire. Especially for long-running streaming jobs, keytabs are recommended.

### Keytab Authentication

Submit the job with the keytab:

    dcos spark run --submit-args="\
    --kerberos-principal user@REALM \
    --keytab-secret-path /__dcos_base64__hdfs-keytab \
    --conf ... --class MySparkJob <url> <args>"

### TGT Authentication

Submit the job with the ticket:
```$bash
    dcos spark run --submit-args="\
    --kerberos-principal hdfs/name-0-node.hdfs.autoip.dcos.thisdcos.directory@LOCAL \
    --tgt-secret-path /__dcos_base64__tgt \
    --conf ... --class MySparkJob <url> <args>"
```

**Note:** These credentials are security-critical. The DC/OS Secret Store requires you to base64 encode binary secrets (such as the Kerberos keytab) before adding them. If they are uploaded with the `__dcos_base64__` prefix, they are automatically decoded when the secret is made available to your Spark job. If the secret name **doesn't** have this prefix, the keytab will be decoded and written to a file in the sandbox. This leaves the secret exposed and is not recommended. We also highly recommended configuring SSL encryption between the Spark components when accessing Kerberos-secured HDFS clusters. See the Security section for information on how to do this.


[8]: http://spark.apache.org/docs/latest/configuration.html#inheriting-hadoop-cluster-configuration
