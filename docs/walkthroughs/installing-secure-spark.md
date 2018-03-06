# Installing and Running Spark with TLS and SASL

## Sample configuration for Spark with Kerberos HDFS
1.  Configuring Spark to use a Kerberos-secured HDFS services requires two additional install-time parameters: the
    location of the HDFS configuration files (`hdfs-site.xml`, `core-site.xml`) and the `krb5.conf` file. 
    *   The HDFS configuration files can be aquired from the HDFS scheduler API
        `http://api.hdfs.marathon.l4lb.thisdcos.directory/v1/endpoints` 
    *   We will base64 encode the `krb5.conf` file and add it to the installation config.json. An example `krb5.conf`
        is: ``` [libdefaults] default_realm = LOCAL
        
        [realms]
          LOCAL = {
            kdc = kdc.marathon.autoip.dcos.thisdcos.directory:2500
          }
          
        ```
    *   base64 encode your `krb5.conf` (`base64 -w 0 {krb5.conf}`).
    
1.  Install Spark (`dcos package install spark --yes --options=kerberos-hdfs-options.json`) with at least the following
    options:
    ```json
    {
      "hdfs": {
          "config-url": "http://api.hdfs.marathon.l4lb.thisdcos.directory/v1/endpoints"
      },
      "security": {
          "kerberos": {
              "enabled": true,
              "krb5conf": "<base64_encoded_krb5.conf>"  // just cut and paste it here, can be done form the UI also
        }
      }
    }
    ```

## Spark Communication Security and Authentication *Note* Requires DC/OS EE for file-based secrets.  

Spark has two communication channels used amongst its components:
    *   a TLS-secured HTTP server so Executors (workers) can retrieve files from the Driver (the container running the
        Spark Context) and, 
    *   a SASL-secured RPC channel for sending data and communication between the Driver and Executors. This section
        describes how to set up the TLS artifacts and how to reference them when launching a Spark job from the
        command-line.

### Setup Spark TLS Artifacts
1.  Setup the artifacts locally using the Java `keytool` utility. On your local workstation run the following to
    generate the artifacts:
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
    When prompted use the password `changeit` the rest of the settings can be left to their defaults. This will generate
    a few files but the ones you need are `server.jks` and `trust.jks`, confirm these are in you local working
    directory.
    
1.  Now base64 encode these two artifacts and upload them to the secret store.

    **DC/OS 1.11+:** Base64 encoding of binary secrets is not necessary in DC/OS 1.11+. You may skip the encoding
    and update the secret names accordingly in the following example.

    ```bash
    # encoding
    base64 -w 0 server.jks > server.jks.base64
    base64 -w 0 trust.jks > trust.jks.base64
    # uploading
    dcos security secrets create /spark/__dcos_base64__truststore --value-file trust.jks.base64
    dcos security secrets create /spark/__dcos_base64__keystore --value-file server.jks.base64
    ```
    *Note* that your version of `base64` may need a different flag (other than `-w 0`) to disable line wrapping, we use
    the coreutils version.
    
    **Note:** The examples on this page assume that you are using the default
    service name for Spark, "spark". If using a different service name, update
    the secret paths accordingly.

1.  To enable TLS in a Spark job add the following configuration:
    ```bash
    dcos spark run --verbose --submit-args="\
    --keystore-secret-path=spark/__dcos_base64__keystore \
    --keystore-password=changeit \
    --private-key-password=changeit \
    —-truststore-secret-path=spark/__dcos_base64__truststore \
    --truststore-password=changeit "
    ```

### Setup BlockTransferService SASL and Executor Authentication
1.  The DC/OS Spark CLI will generate a secret "cookie" for sharing between Spark components. Simply:
    ```bash
    dcos spark secret /spark/spark-auth-secret
    ```
    `spark-auth-secret` you may choose a different name and/or path for the secret, but we provide a concrete example here.
    
1.  To enable executor authentication add the following configurations:
    ```bash
    dcos spark run --submit-args="\
    ...
    --executor-auth-secret=spark/spark-auth-secret
    ..."
    ```

