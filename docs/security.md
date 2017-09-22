---
post_title: Security
menu_order: 40
enterprise: 'no'
---

This topic describes how to configure DC/OS service accounts for Spark.

When running in [DC/OS strict security mode](https://docs.mesosphere.com/1.9/security/), both the dispatcher and jobs must authenticate to Mesos using a [DC/OS Service Account](https://docs.mesosphere.com/1.9/security/service-auth/).

Follow these instructions to [authenticate in strict mode](https://docs.mesosphere.com/service-docs/spark/spark-auth/).

# Spark SSL

SSL support in DC/OS Apache Spark encrypts the following channels:

*   From the [DC/OS admin router][11] to the dispatcher.
*   From the drivers to their executors.

There are a number of configuration variables relevant to SSL setup. The required configuration settings are:

| Variable                         | Description                                     |
|----------------------------------|-------------------------------------------------|
| `spark.ssl.enabled`              | Whether to enable SSL (default: `false`).       |
| `spark.ssl.keyStoreBase64`       | Base64 encoded blob containing a Java keystore. |
| `spark.ssl.enabledAlgorithms`    | Allowed cyphers                                 |
| `spark.ssl.keyPassword`          | The password for the private key                |
| `spark.ssl.keyStore`             | must be server.jks                              |
| `spark.ssl.keyStorePassword`     | The password used to access the keystore        |
| `spark.ssl.protocol`             |  Protocol (e.g. TLS)                            |
| `spark.ssl.trustStore`           | must be trust.jks                               |
| `spark.ssl.trustStorePassword`   | The password used to access the truststore      |


The Java keystore (and, optionally, truststore) are created using the [Java keytool][12]. The keystore must contain one private key and its signed public key. The truststore is optional and might contain a self-signed root-ca certificate that is explicitly trusted by Java.

Both stores must be base64 encoded, for example:

    cat keystore | base64 /u3+7QAAAAIAAAACAAAAAgA...

**Note:** The base64 string of the keystore will probably be much longer than the snippet above, spanning 50 lines or so.

Add the stores to your secrets in the DC/OS Secret store, for example if your base64 encoded keystores and truststores are server.jks.base64 and trust.jks.base64, respectively then do the following: 

```bash
dcos security secrets create /truststore --value-file trust.jks.base64
dcos security secrets create /keystore --value-file server.jks.base64
```

In this case you're adding two secrets `/truststore` and `/keystore` that you will need to pass to the Spark Driver and Executors. You will need to add the following configurations to your `dcos spark run ` command:

```bash

dcos spark run --verbose --submit-args="\
--conf spark.mesos.containerizer=mesos \  # use mesos containerizer
--conf spark.ssl.enabled=true \
--conf spark.ssl.enabledAlgorithms=TLS_RSA_WITH_AES_128_CBC_SHA,TLS_RSA_WITH_AES_256_CBC_SHA \
--conf spark.ssl.keyPassword=<key password> \
--conf spark.ssl.keyStore=server.jks \  # This MUST be set this way
--conf spark.ssl.keyStorePassword=<keystore access password> \
--conf spark.ssl.protocol=TLS \
--conf spark.ssl.trustStore=trust.jks \  # this MUST be set this way
--conf spark.ssl.trustStorePassword=<truststore password> \
--conf spark.mesos.driver.labels=DCOS_SECRETS_DIRECTIVE:[{\"name\"\:\"/keystore\"\,\"type\"\:\"ENVIRONMENT\"\,\"environment\"\:{\"name\"\:\"KEYSTORE_BASE64\"}}\,{\"name\"\:\"/truststore\"\,\"type\"\:\"ENVIRONMENT\"\,\"environment\"\:{\"name\"\:\"TRUSTSTORE_BASE64\"}}] \
--conf spark.mesos.task.labels=DCOS_SECRETS_DIRECTIVE:[{\"name\"\:\"/keystore\"\,\"type\"\:\"ENVIRONMENT\"\,\"environment\"\:{\"name\"\:\"KEYSTORE_BASE64\"}}\,{\"name\"\:\"/truststore\"\,\"type\"\:\"ENVIRONMENT\"\,\"environment\"\:{\"name\"\:\"TRUSTSTORE_BASE64\"}}],DCOS_SPACE:/spark, \
--class <Spark Main class> <Spark Application JAR> [application args]"
```

Importantly the `spark.mesos.driver.labels` and `spark.mesos.task.labels` must be set as shown. If you upload your secret with another path (e.g. not `/keystore` and `/truststore`) then change the `name` in the value accordingly. Lastly, `spark.mesos.task.lables` must have the `DCOS_SPACE:<dcos_space>` label as well, to have access to the secret. See the [Secrets Documentation about SPACES][13] for more details about Spaces, but usually you want `/spark` as shown.


 [11]: https://docs.mesosphere.com/1.9/overview/architecture/components/
 [12]: http://docs.oracle.com/javase/8/docs/technotes/tools/unix/keytool.html
 [13]: https://docs.mesosphere.com/service-docs/spark/v2.0.1-2.2.0-1/run-job/
