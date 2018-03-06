---
layout: layout.pug
excerpt:
title: Kerberos
navigationTitle: Kerberos
menuWeight: 120

---


# HDFS Kerberos

Kerberos is an authentication system to allow Spark to retrieve and write data securely to a Kerberos-enabled HDFS
cluster. As of Mesosphere Spark `2.2.0-2`, long-running jobs will renew their delegation tokens (authentication
credentials). This section assumes you have previously set up a Kerberos-enabled HDFS cluster. **Note** Depending on
your OS, Spark may need to be run as `root` in order to authenticate with your Kerberos-enabled service. This can be
done by setting `--conf spark.mesos.driverEnv.SPARK_USER=root` when submitting your job.

## Spark Installation

Spark (and all Kerberos-enabed) components need a valid `krb5.conf` file. You can setup the Spark service to use a
single `krb5.conf` file for all of the its drivers.

1.  A `krb5.conf` file tells Spark how to connect to your KDC.  Base64 encode this file:

        cat krb5.conf | base64 -w 0 

1.  Put the encoded file (as a string) into your JSON configuration file:

    ```json
    {
       "security": {
         "kerberos": {
          "enabled": "true",
          "krb5conf": "<base64 encoding>"
          }
       }
    }
    ```
        
     Your configuration will probably also have the `hdfs` parameters from above:
     
     ```json
         {
           "service": {
               "name": "kerberized-spark",
               "user": "nobody"
           },
           "hdfs": {
               "config-url": "http://api.hdfs.marathon.l4lb.thisdcos.directory/v1/endpoints"
           },
           "security": {
               "kerberos": {
                   "enabled": true,
                   "krb5conf": "<base64_encoding>"
             }
           }
         }
     ```

     Alternatively, you can specify properties of the `krb5.conf` with more concise options:
     ```json
         {
            "security": {
              "kerberos": {
               "enabled": true,
               "kdc": {
                  "hostname": "<kdc_hostname>",
                  "port": <kdc_port>
                },
                "realm": "<kdc_realm>"
              }
            }
         }

     ```
     
1.  Install Spark with your custom configuration, here called `options.json`:

        dcos package install --options=/path/to/options.json spark
        
1.  Make sure your keytab is in the DC/OS Secret Store, under a path that is accessible
    by the Spark service. Since the keytab is a binary file, you must also base64 encode it on DC/OS 1.10 or lower.
    See [Using the Secret Store][../security/#using-the-secret-store]
    for details.


1. If you are using the history server, you must also configure the `krb5.conf`, principal, and keytab
   for the history server.

   Add the Kerberos configurations to your spark-history JSON configuration file:
   ```json
         {
            "service": {
                "user": "nobody",
                "hdfs-config-url": "http://api.hdfs.marathon.l4lb.thisdcos.directory/v1/endpoints"
            },
            "security": {
                "kerberos": {
                  "enabled": true,
                  "krb5conf": "<base64_encoding>",
                  "principal": "<Kerberos principal>",  # e.g. spark@REALM
                  "keytab": "<keytab secret path>"      # e.g. spark-history/hdfs_keytab
                }
            }
         }
    ```

   Alternatively, you can specify properties of the `krb5.conf`:
   ```json
            {
               "security": {
                   "kerberos": {
                     "enabled": true,
                     "kdc": {
                       "hostname": "<kdc_hostname>",
                       "port": <kdc_port>
                     },
                     "realm": "<kdc_realm>"
                     "principal": "<Kerberos principal>",  # e.g. spark@REALM
                     "keytab": "<keytab secret path>"      # e.g. spark-history/hdfs_keytab
                   }
               }
            }
       ```

1. Make sure all users have write permission to the history HDFS directory. In an HDFS client:
    ```bash
    hdfs dfs -chmod 1777 <history directory>
    ```

## Job Submission

To authenticate to a Kerberos KDC, Spark on Mesos supports keytab files as well as ticket-granting tickets (TGTs).
Keytabs are valid indefinitely, while tickets can expire. Keytabs are recommended, especially for long-running streaming
jobs.

### Controlling the `krb5.conf` with environment variables

If you did not specify `service.security.kerberos.kdc.hostname`, `service.security.kerberos.kdc.port`, and
`services.security.realm` at install time, but wish to use a templated krb5.conf on a job submission you can do this
with the following environment variables:
    ```
    --conf spark.mesos.driverEnv.SPARK_SECURITY_KERBEROS_KDC_HOSTNAME=<kdc_hostname> \
    --conf spark.mesos.driverEnv.SPARK_SECURITY_KERBEROS_KDC_PORT=<kdc_port> \
    --conf spark.mesos.driverEnv.SPARK_SECURITY_KERBEROS_REALM=<kerberos_realm> \
    ```
You can also set the base64 encoded krb5.conf after install time:

    ```
    --conf spark.mesos.driverEnv.SPARK_MESOS_KRB5_CONF_BASE64=<krb5.conf_base64_encoding> \
    ```

**Note** This setting `SPARK_MESOS_KRB5_CONF_BASE64` will overwrite/override any settings set with
`SPARK_SECURITY_KERBEROS_KDC_HOSTNAME`, `SPARK_SECURITY_KERBEROS_KDC_PORT`, and `SPARK_SECURITY_KERBEROS_REALM`

### Setting the Spark User

By default, when Kerberos is enabled, Spark runs as the OS user
corresponding to the primary of the specified Kerberos principal.
For example, the principal "alice@LOCAL" would map to the username "alice".
If it is known that "alice" is not available as an OS user, either in
the docker image or in the host,
the Spark user should be specified as "root" or "nobody" instead:

    ```
    --conf spark.mesos.driverEnv.SPARK_USER=<Spark user>
    ```

### Keytab Authentication

Submit the job with the keytab:

    dcos spark run --submit-args="\
    --kerberos-principal user@REALM \
    --keytab-secret-path /spark/hdfs-keytab \
    --conf spark.mesos.driverEnv.SPARK_USER=<spark user> \
    --conf ... --class MySparkJob <url> <args>"

### TGT Authentication

Submit the job with the ticket:

    dcos spark run --submit-args="\
    --kerberos-principal user@REALM \
    --tgt-secret-path /spark/tgt \
    --conf spark.mesos.driverEnv.SPARK_USER=<spark user> \
    --conf ... --class MySparkJob <url> <args>"

**Note:** The examples on this page assume that you are using the default
service name for Spark, "spark". If using a different service name, update
the secret paths accordingly.

**Note:** You can access external (i.e. non-DC/OS) Kerberos-secured HDFS clusters from Spark on Mesos.

**DC/OS 1.10 or lower:** These credentials are security-critical. The DC/OS Secret Store requires you to base64 encode binary secrets
(such as the Kerberos keytab) before adding them. If they are uploaded with the `__dcos_base64__` prefix, they are
automatically decoded when the secret is made available to your Spark job. If the secret name **doesn't** have this
prefix, the keytab will be decoded and written to a file in the sandbox. This leaves the secret exposed and is not
recommended. 


# Using Kerberos-secured Kafka

Spark can consume data from a Kerberos-enabled Kafka cluster. Connecting Spark to secure Kafka does not require special
installation parameters, however does require the Spark Driver _and_ the Spark Executors can access the following files:

*   Client JAAS (Java Authentication and Authorization Service) file. This is provided using Mesos URIS with `--conf
    spark.mesos.uris=<location_of_jaas>`.
*   `krb5.conf` for your Kerberos setup. Similarly to HDFS, this is provided using a base64 encoding of the file.
 
        cat krb5.conf | base64 -w 0
        
    Then assign the environment variable, `KRB5_CONFIG_BASE64`, this value for the Driver and the Executors:
        --conf spark.mesos.driverEnv.KRB5_CONFIG_BASE64=<base64_encoded_string>
        --conf spark.executorEnv.KRB5_CONFIG_BASE64=<base64_encoded_string>
        
*   The `keytab` containing the credentials for accessing the Kafka cluster.
        
        --conf spark.mesos.containerizer=mesos                            # required for secrets
        --conf spark.mesos.driver.secret.names=<keytab>                   # e.g. spark/kafka_keytab
        --conf spark.mesos.driver.secret.filenames=<keytab_file_name>     # e.g. kafka.keytab
        --conf spark.mesos.executor.secret.names=<keytab>                 # e.g. spark/kafka_keytab
        --conf spark.mesos.executor.secret.filenames=<keytab_file_name>   # e.g. kafka.keytab
        

Finally, you'll likely need to tell Spark to use the JAAS file:
        
        --conf spark.driver.extraJavaOptions=-Djava.security.auth.login.config=/mnt/mesos/sandbox/<jaas_file>
        --conf spark.executor.extraJavaOptions=-Djava.security.auth.login.config=/mnt/mesos/sandbox/<jaas_file>


It is important that the filename is the same for the driver and executor keytab file (`<keytab_file_name>` above) and
that this file is properly addressed in your JAAS file. For a worked example of a Spark consumer from secure Kafka see
the [advanced examples][https://docs.mesosphere.com/services/spark/2.1.1-2.2.0-2/usage-examples/]
