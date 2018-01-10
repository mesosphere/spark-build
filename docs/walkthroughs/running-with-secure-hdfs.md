# Fully secure HDFS and Spark with Kerberos, SASL, and TLS. 
This walkthrough will show how to run a version of the [TeraSort Benchmark](https://github.com/ehiggs/spark-terasort) with Spark in a fully secure deployment and Kerberos-secured HDFS as the storage backend.

Spark can use [Kerberos](https://en.wikipedia.org/wiki/Kerberos_(protocol)) to authenticate and provide SASL with HDFS running on DC/OS. To start this walkthrough we assume that you have the following:
1.  DC/OS Cluster with 5 agents with >= 4 cores/agent.
1.  A running KDC that you can add principals to. 
1.  A way to download/acquire the keytab from the KDC to your local workstation.

## Establishing correct principals for HDFS. **Note** Requires DC/OS EE for file-based secrets.
The Keberos `keytab` is a binary file and cannot be uploaded to the Secret Store directly. To use binary secrets in DC/OS 1.10 and 1.11 the binary file must be base64 encoded and the resultant string will be uploaded with the prefix: `__dcos_base64__<secretname>`, this tells DC/OS to decode the file before placing it in the Sandbox (more on that later).

1.  Add the following principals to the KDC (Obviously it is recommended to use a script or other automation to establish these principals):
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
1.  Base64 encode the file with `base64 -w 0 {source} > {destination}` (we recommend using `base64` from GNU coreutils, if the version on your machine is different the `-w` flag may need to be replaced with the appropriate flag to disable wrapping.
1.  Install the DC/OS Enterprise CLI with the command line: `dcos package install --yes dcos-enterprise-cli`   
1.  Upload the base64 encoded file to the secret store: `dcos security secrets create __dcos_base64__keytab --value-file {destination}`.
    *   Notice we have uploaded the secret to the root (will be `/__dcos_base64__keytab`)
1.  You're now ready to install HDFS. This can be done using the UI (DC/OS Catalog) or through the CLI as demonstrated here. First make an options.json containing at least:
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
1.  Configuring Spark to use a Kerberos-secured HDFS services requires two additional install-time parameters: the location of the HDFS configuration files `hdfs-site.xml` and `core-site.xml` and the `krb5.conf` file. 
    *   The HDFS configuration files can be aquired from the HDFS scheduler API `http://api.hdfs.marathon.l4lb.thisdcos.directory/v1/endpoints` 
    *   Similar to the `keytab` file above we will base64 encode the `krb5.conf` file and add it to the installation config.json. An example `krb5.conf` is:
        ```bash
        [libdefaults]
        default_realm = LOCAL
        dns_lookup_realm = true
        dns_lookup_kdc = true
        udp_preference_limit = 1
        
        [realms]
          LOCAL = {
            kdc = <kdc_hostname>:<kdc_port>
          }
        
        [domain_realm]
          .hdfs.dcos = LOCAL
          hdfs.dcos = LOCAL
        ```
    *   base64 encode your `krb5.conf` as above.
    
1.  Install Spark (`dcos package install spark --yes --options=kerberos-hdfs-options.json`) with at least the following options:
    ```json
    {
      "hdfs": {
          "config-url": "http://api.hdfs.marathon.l4lb.thisdcos.directory/v1/endpoints"
      },
      "security": {
          "kerberos": {
              "krb5conf": "<base64_encoded_krb5.conf>"
        }
      }
    }
    ```
## Spark Communication Security and Authentication *Note* Requires DC/OS EE for file-based secrets.
Spark has two communication channels used amongst its components, a TLS-secured HTTP server so Executors (workers) can retrieve files from the Driver (the container running the Spark Context) and a SASL-secured RPC channel for sending data and communication between the Driver and Executors. This section describes how to set up the TLS artifacts and how to reference them when launching a Spark job from the command-line.

### Setup Spark TLS Artifacts
1.  Setup the artifacts locally using the Java `keyool` utility. Go on your local workstation run the following to generate the artifacts:
    ```bash
    # server key
    keytool -keystore server.jks -alias localhost -validity 365 -genkey

    # CA key, cert
    openssl req -new -x509 -keyout ca.key -out ca.crt -days 365

    # trust store
    keytool -keystore trust.jks -alias CARoot -import -file ca.crt

    # unsigned server cert
    keytool -keystore server.jks -alias localhost -certreq -file server.crt-unsigned

    # signed server cert
    openssl x509 -req -CA ca.crt -CAkey ca.key -in server.crt-unsigned -out server.crt -days 365 -CAcreateserial -passin pass:changeit

    # add CA cert, server cert to keystore
    keytool -keystore server.jks -alias CARoot -import -file ca.crt
    keytool -keystore server.jks -alias localhost -import -file server.crt
    ```
    When prompted use the password `changeit` the rest of the settings can be left to their defaults. This will generate a few files but the ones you need are `server.jks` and `trust.jks`, confirm these are in you local working directory.
    
1.  Now base64 encode these two artifacts and upload them to the secret store.
    ```bash
    # encoding
    base64 server.jks > server.jks.base64
    base64 trust.jks > trust.jks.base64
    # uploading
    dcos security secrets create /__dcos_base64__truststore --value-file trust.jks.base64
    dcos security secrets create /__dcos_base64__keystore --value-file server.jks.base64
    ```
    
1.  To enable TLS in a Spark job add the following configuration:
    ```bash
    dcos spark run --verbose --submit-args="\
    --keystore-secret-path=__dcos_base64__keystore \
    --keystore-password=changeit \
    --private-key-password=changeit \
    —-truststore-secret-path=__dcos_base64__truststore \
    --truststore-password=changeit "
    ```

### Setup BlockTransferService SASL and Executor Authentication
1.  The DC/OS Spark CLI will generate a secret "cookie" for sharing between Spark components. Simply:
    ```bash
    dcos spark secret /spark-auth-secret
    ```
    `spark-auth-secret` you may choose a different name and/or path for the secret, but we provide a concrete example here.
    
1.  To enable add the following configurations:
    ```bash
    dcos spark run --submit-args="\
    --conf spark.mesos.containerizer=mesos \
    --conf spark.authenticate=true \
    --conf spark.authenticate.enableSaslEncryption=true \
    --conf spark.authenticate.secret=sparkauthsecret.secret \
    --conf spark.executorEnv._SPARK_AUTH_SECRET=sparkauthsecret.secret \
    --conf spark.mesos.driver.secret.names=<secret_path> \
    --conf spark.mesos.driver.secret.filenames=sparkauthsecret.secret \
    --conf spark.mesos.executor.secret.names=<secret_path> \
    --conf spark.mesos.executor.secret.filenames=sparkauthsecret.secret"
    ```

## Running TeraSort
The TeraSort suite has 3 steps, generating the data, sorting the data, and validating the results. We provide a pre-built Spark job (https://downloads.mesosphere.io/spark/examples/spark-terasort-1.1-jar-with-dependencies_2.11.jar) for testing purposes.

1.  Run the `TeraGen` step:
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
    --conf spark.cores.max=16 \
    --class com.github.ehiggs.spark.terasort.TeraGen https://downloads.mesosphere.io/spark/examples/spark-terasort-1.1-jar-with-dependencies_2.11.jar 1g hdfs:///terasort_in_secure"
    ```
1.  Run the `TeraSort` step:
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
    --conf spark.cores.max=16 \
    --class com.github.ehiggs.spark.terasort.TeraSort https://downloads.mesosphere.io/spark/examples/spark-terasort-1.1-jar-with-dependencies_2.11.jar hdfs:///terasort_in_secure hdfs:///terasort_out_secure"
    ```

1.  Run the `TeraValidate` step:
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
    --conf spark.cores.max=16 \
    --class com.github.ehiggs.spark.terasort.TeraValidate https://downloads.mesosphere.io/spark/examples/spark-terasort-1.1-jar-with-dependencies_2.11.jar hdfs:///terasort_out_secure hdfs:///terasort_validate_secure"
    ```