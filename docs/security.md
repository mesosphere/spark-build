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
| `spark.ssl.enabledAlgorithms`    | Allowed cyphers                                 |
| `spark.ssl.keyPassword`          | The password for the private key                |
| `spark.ssl.keyStore`             | must be server.jks                              |
| `spark.ssl.keyStorePassword`     | The password used to access the keystore        |
| `spark.ssl.protocol`             |  Protocol (e.g. TLS)                            |
| `spark.ssl.trustStore`           | must be trust.jks                               |
| `spark.ssl.trustStorePassword`   | The password used to access the truststore      |


The Java keystore (and, optionally, truststore) are created using the [Java keytool][12]. The keystore must contain one private key and its signed public key. The truststore is optional and might contain a self-signed root-ca certificate that is explicitly trusted by Java.

Both stores must be base64 encoded without newlines, for example:

```bash
cat keystore | base64 -w 0 > keystore.base64
cat keystore.base64
/u3+7QAAAAIAAAACAAAAAgA...
```

**Note:** The base64 string of the keystore will probably be much longer than the snippet above, spanning 50 lines or so.

Add the stores to your secrets in the DC/OS secret store. For example, if your base64-encoded keystores 
and truststores are server.jks.base64 and trust.jks.base64, respectively, then use the following 
commands to add them to the secret store: 

```bash
dcos security secrets create /__dcos_base64__truststore --value-file trust.jks.base64
dcos security secrets create /__dcos_base64__keystore --value-file server.jks.base64
```

In this case, you are adding two secrets `/truststore` and `/keystore`. 
You must add the following configurations to your `dcos spark run ` command.
The ones in parentheses are optional.:

```bash

dcos spark run --verbose --submit-args="\
--tls-keystore-secret-path=<path/to/keystore, e.g. /keystore> \
(—tls-truststore-secret-path=<path/to/truststore, e.g. /truststore> \)
--conf spark.ssl.enabled=true \
(—conf spark.ssl.enabledAlgorithms=<cipher, e.g., TLS_RSA_WITH_AES_128_CBC_SHA256> \)
--conf spark.ssl.protocol=<protocol, e.g., TLS, TLSv1.1, or SSLv3> \
--conf spark.ssl.keyPassword=<password to private key in keystore> \
--conf spark.ssl.keyStorePassword=<password to keystore> \
--conf spark.ssl.trustStorePassword=<password to truststore> \
--class <Spark Main class> <Spark Application JAR> [application args]"
```

**Note:** If you have specified a space for your secrets other than the default value,
`/spark`, then you must set `spark.mesos.task.labels=DCOS_SPACE:<dcos_space>`
in the command above in order to access the secrets.
See the [Secrets Documentation about spaces][13] for more details about spaces.


 [11]: https://docs.mesosphere.com/1.9/overview/architecture/components/
 [12]: http://docs.oracle.com/javase/8/docs/technotes/tools/unix/keytool.html
 [13]: https://docs.mesosphere.com/1.10/security/#spaces
