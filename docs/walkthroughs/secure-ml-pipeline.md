# Fully secure ML pipeline using Spark, HDFS, and Kafka
This walkthrough will show how to setup a Spark ML model for classification of data streaming from a Kafka topic. The Kafka and HDFS clusters will use Kerberos for authentication and SASL. All Spark communication channels will also be secured. Specifically the following:
1.  Use Kerberos-secured HDFS and Kafka with Spark
1.  Use TLS and SASL in Spark
1.  Use Spark Streaming
1.  Use Spark ML Pipelines

Completing this walkthrough requires the following.
1.  DC/OS Cluster with 5 agents with >= 4 cores/agent.
1.  A running KDC that you can add principals to. 
1.  A way to download/acquire the `keytab` from the KDC to your local workstation.
1.  An S3 bucket to host a Spark application
1.  `sbt` to build the example application

## Setting up secure HDFS and Kafka
The Keberos `keytab` is a binary file and cannot be uploaded to the Secret Store directly. To use binary secrets in DC/OS 1.10 and 1.11 the binary file must be base64 encoded and the resultant string will be uploaded with the prefix: `__dcos_base64__<secretname>`, this tells DC/OS to decode the file before placing it in the Sandbox.

1.  Establishing correct principals for HDFS and Kafka, assuming you're using the packages from the DC/OS universe. **Note** Requires DC/OS EE for file-based secrets. Add the following principals to the KDC (Obviously it is recommended to use a script or other automation to establish these principals):
    ```bash
    hdfs/name-0-node.hdfs.autoip.dcos.thisdcos.directory@LOCAL
    HTTP/name-0-node.hdfs.autoip.dcos.thisdcos.directory@LOCAL
    hdfs/name-0-zkfc.hdfs.autoip.dcos.thisdcos.directory@LOCAL
    HTTP/name-0-zkfc.hdfs.autoip.dcos.thisdcos.directory@LOCAL
    hdfs/name-1-node.hdfs.autoip.dcos.thisdcos.directory@LOCAL
    HTTP/name-1-node.hdfs.autoip.dcos.thisdcos.directory@LOCAL
    hdfs/name-1-zkfc.hdfs.autoip.dcos.thisdcos.directory@LOCAL
    HTTP/name-1-zkfc.hdfs.autoip.dcos.thisdcos.directory@LOCAL
    hdfs/journal-0-node.hdfs.autoip.dcos.thisdcos.directory@LOCAL
    HTTP/journal-0-node.hdfs.autoip.dcos.thisdcos.directory@LOCAL
    hdfs/journal-1-node.hdfs.autoip.dcos.thisdcos.directory@LOCAL
    HTTP/journal-1-node.hdfs.autoip.dcos.thisdcos.directory@LOCAL
    hdfs/journal-2-node.hdfs.autoip.dcos.thisdcos.directory@LOCAL
    HTTP/journal-2-node.hdfs.autoip.dcos.thisdcos.directory@LOCAL
    hdfs/data-0-node.hdfs.autoip.dcos.thisdcos.directory@LOCAL
    HTTP/data-0-node.hdfs.autoip.dcos.thisdcos.directory@LOCAL
    hdfs/data-1-node.hdfs.autoip.dcos.thisdcos.directory@LOCAL
    HTTP/data-1-node.hdfs.autoip.dcos.thisdcos.directory@LOCAL
    hdfs/data-2-node.hdfs.autoip.dcos.thisdcos.directory@LOCAL
    HTTP/data-2-node.hdfs.autoip.dcos.thisdcos.directory@LOCAL
    kafka/kafka-0-broker.secure-kafka.autoip.dcos.thisdcos.directory@LOCAL
    kafka/kafka-1-broker.secure-kafka.autoip.dcos.thisdcos.directory@LOCAL
    kafka/kafka-2-broker.secure-kafka.autoip.dcos.thisdcos.directory@LOCAL
    hdfs@LOCAL
    client@LOCAL
    ```
1.  Download the `keytab` file to a local directory.
1.  Base64 encode the file with `base64 -w 0 {source} > {destination}` (we recommend using `base64` from GNU coreutils, if the version on your machine is different the `-w` flag may need to be replaced with the appropriate flag to disable wrapping.
1.  Install the DC/OS Enterprise CLI with the command line: `dcos package install --yes dcos-enterprise-cli`   
1.  Upload the base64 encoded file to the secret store: `dcos security secrets create __dcos_base64__keytab --value-file {destination}`.
    *   Notice we have uploaded the secret to the root (will be `/__dcos_base64__keytab`)
1.  You're now ready to install HDFS and Kafka. This can be done using the UI (DC/OS Catalog) or through the CLI as demonstrated here. First make an options.json containing at least (these are the same for both services):
    ```json
    {
      "service": {
        "kerberos": {
          "enabled": "true",
          "kdc": {
            "hostname":  "<agent_hosting_kdc_or_dns>",
            "port": "<port_to_communicate_with_kdc>"
          },
          "realm": "LOCAL",
          "keytab_secret": "__dcos_base64__keytab"
        },
        "transport_encryption": {
          "enabled": "true",
          "allow_plaintext": "false"
        }
      }
    }
    ```
    
## Install Spark and prepare Java Authentication and Authorization Service (JAAS) file for Kafka
1.  Install Spark including HDFS settings, using the instructions in [installing-secure-spark.md](). Using Kafka from Spark does not require any special installation.
1.  Using Kerberos-secured Kafka from Spark requires a JAAS file to be available to the job, we use S3 to host the artifact. In this example use the following: 
    ```
    KafkaClient {
        com.sun.security.auth.module.Krb5LoginModule required
        useKeyTab=true
        storeKey=true
        keyTab="/mnt/mesos/sandbox/kafka-client.keytab"
        useTicketCache=false
        serviceName="kafka"
        principal="client@LOCAL";
    }; 
    ```
    This is also available in the [resources]() of the test repo. Add these contents to a local file and copy it to S3 and make it publicly accessible. For the reminder of the tutorial we'll reference this location as `http://JAAS_ARTIFACT.conf` 

## Run the example
1.  We need to upload the training data to S3, we use the file `SMSSpamCollection.txt` that can be found in the [resources]() of the test repo. This artifact needs to be publicly available to your cluster, we will refer to this artifact as `http://SMS_DATA.txt`.
1.  Build the example jar by following the instructions in the [README](). Upload that to S3 so that it can be publicly accessible, we will refer to this artifact as `http://SPAM_HAM.jar` 
1.  Run the model training step, notice here we only use HDFS:
    ```bash
    dcos spark run --submit-args="\
    --kerberos-principal=hdfs@LOCAL \
    --keytab-secret-path=/__dcos_base64___keytab \
    --keystore-secret-path=__dcos_base64__keystore \
    --keystore-password=changeit \
    --private-key-password=changeit \
    --truststore-secret-path=__dcos_base64__truststore \
    --truststore-password=changeit \
    --conf spark.mesos.containerizer=mesos \
    --conf spark.authenticate=true \
    --conf spark.authenticate.enableSaslEncryption=true \
    --conf spark.authenticate.secret=sparkauthsecret.secret \
    --conf spark.executorEnv._SPARK_AUTH_SECRET=sparkauthsecret.secret \
    --conf spark.mesos.driver.secret.names=/spark-auth-secret \
    --conf spark.mesos.driver.secret.filenames=sparkauthsecret.secret \
    --conf spark.mesos.executor.secret.names=spark-auth-secret \
    --conf spark.mesos.executor.secret.filenames=sparkauthsecret.secret \
    --conf spark.cores.max=8 \
    --conf spark.mesos.uris=https://s3-us-west-2.amazonaws.com/arand-sandbox-mesosphere/SMSSpamCollection.txt \
    --class SpamHamModelFactory https://s3-us-west-2.amazonaws.com/arand-sandbox-mesosphere/dcos-spark-scala-tests-assembly-0.1-SNAPSHOT.jar file:///mnt/mesos/sandbox/SMSSpamCollection.txt 0.8 hdfs:///nb_model"
    ```
1.  Setup the Spammer, this small job will just push messages to the topic:
    ```bash
    
    ```

