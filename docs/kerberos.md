---
post_title: Kerberos
nav_title: Kerberos
menu_order: 120
enterprise: 'no'
---


# HDFS Kerberos

Kerberos is an authentication system to allow Spark to retrieve and write data securely to a Kerberos-enabled HDFS cluster. As of Mesosphere Spark `2.2.0-2`, long-running jobs will renew their delegation tokens (authentication credentials). This section assumes you have previously set up a Kerberos-enabled HDFS cluster. **Note** Depending on your OS, Spark may need to be run as `root` in order to authenticate with your Kerberos-enabled service. This can be done by setting `--conf spark.mesos.driverEnv.SPARK_USER=root` when submitting your job.

## Spark Installation

Spark (and all Kerberos-enabed) components need a valid `krb5.conf` file. You can setup the Spark service to use a single `krb5.conf` file for all of the its drivers.

1.  A `krb5.conf` file tells Spark how to connect to your KDC.  Base64 encode this file:

        cat krb5.conf | base64 -w 0 

1.  Put the encoded file (as a string) into your JSON configuration file:

        {
           "security": {
             "kerberos": {
              "krb5conf": "<base64 encoding>"
              }
           }
        }
        
     Your configuration will probably also have the `hdfs` parameters from above:
     
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
                  "krb5conf": "<base64_encoding>"
            }
          }
        }

        
1.  Install Spark with your custom configuration, here called `options.json`:

        dcos package install --options=/path/to/options.json spark
        
1.  Make sure your keytab is accessible from the DC/OS [Secret Store][https://docs.mesosphere.com/latest/security/secrets/].

1. If you've enabled the history server via `history-server.enabled`, you must also configure the principal and keytab for the history server.  **WARNING**: The keytab contains secrets, in the current history server package the keytab is not stored securely. See [Limitations][9]

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

## Job Submission

To authenticate to a Kerberos KDC, Spark on Mesos supports keytab files as well as ticket-granting tickets (TGTs). Keytabs are valid infinitely, while tickets can expire. Keytabs are recommended, especially for long-running streaming jobs.

### Keytab Authentication

Submit the job with the keytab:

    dcos spark run --submit-args="\
    --kerberos-principal user@REALM \
    --keytab-secret-path /__dcos_base64__hdfs-keytab \
    --conf ... --class MySparkJob <url> <args>"

### TGT Authentication

Submit the job with the ticket:

    dcos spark run --submit-args="\
    --kerberos-principal hdfs/name-0-node.hdfs.autoip.dcos.thisdcos.directory@LOCAL \
    --tgt-secret-path /__dcos_base64__tgt \
    --conf ... --class MySparkJob <url> <args>"

**Note:** You can access external (i.e. non-DC/OS) Kerberos-secured HDFS clusters from Spark on Mesos.

**Note:** These credentials are security-critical. The DC/OS Secret Store requires you to base64 encode binary secrets (such as the Kerberos keytab) before adding them. If they are uploaded with the `__dcos_base64__` prefix, they are automatically decoded when the secret is made available to your Spark job. If the secret name **doesn't** have this prefix, the keytab will be decoded and written to a file in the sandbox. This leaves the secret exposed and is not recommended. 


# Kafka Kerberos

Spark can consume data from a Kerberos-enabled Kafka cluster. Connecting Spark to secure Kafka does not require special installation parameters, however does require the Spark Driver _and_ the Spark Executors can access the following files:

*   Client JAAS (Java Authentication and Authorization Service) file. This is provided using Mesos URIS with `--conf spark.mesos.uris=<location_of_jaas>`.
*   `krb5.conf` for your Kerberos setup. Similarly to HDFS, this is provided using a base64 encoding of the file.
 
        cat krb5.conf | base64 -w 0
        
    Then assign the environment variable, `KRB5_CONFIG_BASE64`, this value for the Driver and the Executors:
        --conf spark.mesos.driverEnv.KRB5_CONFIG_BASE64=<base64_encoded_string>
        --conf spark.executorEnv.KRB5_CONFIG_BASE64=<base64_encoded_string>
        
*   The `keytab` containing the credentials for accessing the Kafka cluster.
        
        --conf spark.mesos.driver.secret.names=<base64_encoded_keytab>    # e.g. __dcos_base64__kafka_keytab
        --conf spark.mesos.driver.secret.filenames=<keytab_file_name>     # e.g. kafka.keytab
        --conf spark.mesos.executor.secret.names=<base64_encoded_keytab>  # e.g. __dcos_base64__kafka_keytab
        --conf spark.mesos.executor.secret.filenames=<keytab_file_name>   # e.g. kafka.keytab
        

Finally, you'll likely need to tell Spark to use the JAAS file:
        
        --conf spark.driver.extraJavaOptions=-Djava.security.auth.login.config=/mnt/mesos/sandbox/<jaas_file>
        --conf spark.executor.extraJavaOptions=-Djava.security.auth.login.config=/mnt/mesos/sandbox/<jaas_file>


It is important that the filename is the same for the driver and executor keytab file (`<keytab_file_name>` above) and that this file is properly addressed in your JAAS file. For a worked example of a Spark consumer from secure Kafka see the [advanced examples][https://docs.mesosphere.com/service-docs/spark/2.1.1-2.2.0-2/usage-examples/]
