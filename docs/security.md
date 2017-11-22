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

There are a number of Spark configuration variables relevant to SSL setup. The configuration settings are:

| Variable                         | Description                                     | Default Value |
|----------------------------------|-------------------------------------------------|---------------|
| `spark.ssl.enabledAlgorithms`    | Allowed cyphers                                 | JVM defaults  |
| `spark.ssl.keyPassword`          | The password for the private key                | None          |
| `spark.ssl.keyStorePassword`     | The password used to access the keystore        | None          |
| `spark.ssl.protocol`             | Protocol                                        | TLS           |
| `spark.ssl.trustStorePassword`   | The password used to access the truststore      | None          |


In addition, a Java keystore (and, optionally, truststore) must be provided.
These are created using the [Java keytool][12]. The keystore must contain one private key and its signed public key. The truststore is optional and might contain a self-signed root-ca certificate that is explicitly trusted by Java.

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
dcos security secrets create /__dcos_base64__keystore --value-file server.jks.base64
dcos security secrets create /__dcos_base64__truststore --value-file trust.jks.base64
```

You must add the following configurations to your `dcos spark run ` command.
The ones in parentheses are optional:

```bash

dcos spark run --verbose --submit-args="\
--keystore-secret-path=<path/to/keystore, e.g. __dcos_base64__keystore> \
(—-truststore-secret-path=<path/to/truststore, e.g. __dcos_base64__truststore> \)
(—-conf spark.ssl.enabledAlgorithms=<cipher, e.g., TLS_RSA_WITH_AES_128_CBC_SHA256> \)
--conf spark.ssl.keyPassword=<password to private key in keystore> \
--conf spark.ssl.keyStorePassword=<password to keystore> \
(--conf spark.ssl.trustStorePassword=<password to truststore> \)
--class <Spark Main class> <Spark Application JAR> [application args]"
```

**Note:** If you have specified a space for your secrets other than the default value,
`/spark`, then you must set `spark.mesos.task.labels=DCOS_SPACE:<dcos_space>`
in the command above in order to access the secrets.
See the [Secrets Documentation about spaces][13] for more details about spaces.

**Note:** If you specify environment-based secrets with `spark.mesos.[driver|executor].secret.envkeys`,
the keystore and truststore secrets will also show up as environment-based secrets,
due to the way secrets are implemented. You can ignore these extra environment variables.


 [11]: https://docs.mesosphere.com/1.9/overview/architecture/components/
 [12]: http://docs.oracle.com/javase/8/docs/technotes/tools/unix/keytool.html
 [13]: https://docs.mesosphere.com/1.10/security/#spaces
