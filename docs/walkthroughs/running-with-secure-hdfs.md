# Fully secure HDFS and Spark with Kerberos, SASL, and TLS. 
This walkthrough will show how to run a version of the [TeraSort Benchmark](https://github.com/ehiggs/spark-terasort)
with Spark in a fully secure deployment and Kerberos-secured HDFS as the storage backend. Specifically, we will
demonstrate the following:
1.  Use a Kerberos-secured HDFS with Spark.
1.  Use TLS to secure the file-serving channels of your Spark jobs.
1.  Use SASL for authentication of Spark Executors and encryption of the BlockTransferService

Spark can use [Kerberos](https://en.wikipedia.org/wiki/Kerberos_(protocol)) to authenticate and provide SASL with HDFS
running on DC/OS. To start this walkthrough we assume that you have the following:
1.  DC/OS Cluster with 5 agents with >= 4 cores/agent.
1.  A running KDC that you can add principals to. 
1.  A way to download/acquire the `keytab` from the KDC to your local workstation.

## Setting up secure HDFS
The Keberos `keytab` is a binary file and cannot be uploaded to the Secret Store directly. To use binary secrets in
DC/OS 1.10 or lower, the binary file must be base64 encoded and the resultant string will be uploaded with the prefix:
`__dcos_base64__<secretname>`, this tells DC/OS to decode the file before placing it in the Sandbox.
In DC/OS 1.11+, base64 encoding of binary secrets is not necessary. You may skip the encoding
and update the secret names accordingly in the following example.

1.  Establish correct principals for HDFS (assumes you're using the HDFS from the DC/OS Universe and installed with
    service name `hdfs`). **Note** Requires DC/OS EE for file-based secrets. Add the following principals to the KDC
    (It is recommended to use a script or other automation to establish these principals):
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
    HTTP/hdfs.marathon.autoip.dcos.thisdcos.directory@LOCAL
    hdfs@LOCAL
    client@LOCAL
    ```
1.  Download the `keytab` file to a local directory.
1.  Base64 encode the file with `base64 -w 0 {source} > {destination}` (we recommend using `base64` from GNU coreutils.
    If the version on your machine is different the `-w` flag may need to be replaced with the appropriate flag to
    disable wrapping.
1.  Install the DC/OS Enterprise CLI with the command line: `dcos package install --yes dcos-enterprise-cli`   
1.  Upload the base64 encoded file to the secret store: `dcos security secrets create /__dcos_base64__keytab
    --value-file {destination}`.
    *   Notice we have uploaded the secret to the root (will be `/__dcos_base64__keytab`)
1.  You're now ready to install HDFS. This can be done using the UI (DC/OS Catalog) or through the CLI as demonstrated
    here. First make an `options.json` containing at least:
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

## Install Spark
1.  Install Spark including HDFS settings, using the instructions in [installing-secure-spark.md]()

## Running TeraSort
The TeraSort suite has 3 steps: generating the data, sorting the data, and validating the results. We provide a pre-built Spark job (https://downloads.mesosphere.io/spark/examples/spark-terasort-1.1-jar-with-dependencies_2.11.jar) for testing purposes.

1.  Run the `TeraGen` step:
    ```bash
    dcos spark run --submit-args="\
    --kerberos-principal=hdfs@LOCAL \
    --keytab-secret-path=/__dcos_base64___keytab \
    --keystore-secret-path=spark/__dcos_base64__keystore \
    --keystore-password=changeit \
    --private-key-password=changeit \
    --truststore-secret-path=spark/__dcos_base64__truststore \
    --truststore-password=changeit \
    --executor-auth-secret=spark/spark-auth-secret \
    --conf spark.cores.max=16 \
    --class com.github.ehiggs.spark.terasort.TeraGen https://downloads.mesosphere.io/spark/examples/spark-terasort-1.1-jar-with-dependencies_2.11.jar 1g hdfs:///terasort_in_secure"
    ```

    **Note:** The examples on this page assume that you are using the default
    service name for Spark, "spark". If using a different service name, update
    the secret paths accordingly.

1.  Run the `TeraSort` step:
    ```bash
    dcos spark run --submit-args="\
    --kerberos-principal=hdfs@LOCAL \
    --keytab-secret-path=/__dcos_base64___keytab \
    --keystore-secret-path=spark/__dcos_base64__keystore \
    --keystore-password=changeit \
    --private-key-password=changeit \
    --truststore-secret-path=spark/__dcos_base64__truststore \
    --truststore-password=changeit \
    --executor-auth-secret=spark/spark-auth-secret \
    --conf spark.cores.max=16 \
    --class com.github.ehiggs.spark.terasort.TeraSort https://downloads.mesosphere.io/spark/examples/spark-terasort-1.1-jar-with-dependencies_2.11.jar hdfs:///terasort_in_secure hdfs:///terasort_out_secure"
    ```

1.  Run the `TeraValidate` step:
    ```bash
    dcos spark run --submit-args="\
    --kerberos-principal=hdfs@LOCAL \
    --keytab-secret-path=/__dcos_base64___keytab \
    --keystore-secret-path=spark/__dcos_base64__keystore \
    --keystore-password=changeit \
    --private-key-password=changeit \
    --truststore-secret-path=spark/__dcos_base64__truststore \
    --truststore-password=changeit \
    --executor-auth-secret=spark/spark-auth-secret \
    --conf spark.cores.max=16 \
    --class com.github.ehiggs.spark.terasort.TeraValidate https://downloads.mesosphere.io/spark/examples/spark-terasort-1.1-jar-with-dependencies_2.11.jar hdfs:///terasort_out_secure hdfs:///terasort_validate_secure"
    ```
