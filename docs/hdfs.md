---
post_title: Configure Spark for HDFS
nav_title: HDFS
menu_order: 25
enterprise: 'yes'
---

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
`http://<hdfs.framework-name>.marathon.mesos:<port>/v1/connection`, where
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

[8]: http://spark.apache.org/docs/latest/configuration.html#inheriting-hadoop-cluster-configuration
[9]: #ssl