---
post_title: Security
menu_order: 40
enterprise: 'no'
---

This topic describes how to configure DC/OS service accounts for Spark.

When running in [DC/OS strict security mode](https://docs.mesosphere.com/1.9/security/), both the dispatcher and jobs must authenticate to Mesos using a [DC/OS Service Account](https://docs.mesosphere.com/1.9/security/service-auth/).

Follow these instructions to [authenticate in strict mode](https://docs.mesosphere.com/services/spark/spark-auth/).

# Spark SSL

SSL support in DC/OS Apache Spark encrypts the following channels:

*   From the [DC/OS admin router][11] to the dispatcher.
*   Files served from the drivers to their executors.

To enable SSL, a Java keystore (and, optionally, truststore) must be provided, along
with their passwords. The first three settings below are **required** during job
submission. If using a truststore, the last two are also **required**:

| Variable                         | Description                                     |
|----------------------------------|-------------------------------------------------|
| `--keystore-secret-path`         | Path to keystore in secret store                |
| `--keystore-password`            | The password used to access the keystore        |
| `--private-key-password`         | The password for the private key                |
| `--truststore-secret-path`       | Path to truststore in secret store              |
| `--truststore-password`          | The password used to access the truststore      |


In addition, there are a number of Spark configuration variables relevant to SSL setup.
These configuration settings are **optional**:

| Variable                         | Description           | Default Value |
|----------------------------------|-----------------------|---------------|
| `spark.ssl.enabledAlgorithms`    | Allowed cyphers       | JVM defaults  |
| `spark.ssl.protocol`             | Protocol              | TLS           |


The keystore and truststore are created using the [Java keytool][12]. The keystore
must contain one private key and its signed public key. The truststore is optional
and might contain a self-signed root-ca certificate that is explicitly trusted by Java.

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
--keystore-password=<password to keystore> \
--private-key-password=<password to private key in keystore> \
(—-truststore-secret-path=<path/to/truststore, e.g. __dcos_base64__truststore> \)
(--truststore-password=<password to truststore> \)
(—-conf spark.ssl.enabledAlgorithms=<cipher, e.g., TLS_RSA_WITH_AES_128_CBC_SHA256> \)
--class <Spark Main class> <Spark Application JAR> [application args]"
```

**Note:** If you have specified a space for your secrets other than the default value,
`/spark`, then you must set `spark.mesos.task.labels=DCOS_SPACE:<dcos_space>`
in the command above in order to access the secrets.
See the [Secrets Documentation about spaces][13] for more details about spaces.

**Note:** If you specify environment-based secrets with `spark.mesos.[driver|executor].secret.envkeys`,
the keystore and truststore secrets will also show up as environment-based secrets,
due to the way secrets are implemented. You can ignore these extra environment variables.

# Spark SASL (RPC endpoint authentication)
Spark uses Simple Authentication Security Layer (SASL) to authenticate Executors with the Driver and for encrypting messages sent between components. This functionality relies on a shared secret between all components you expect to communicate with each other. A secret can be generated with the DC/OS Spark CLI 
```bash
dcos spark secret <secret_path>
# for example
dcos spark secret /sparkAuthSecret
```
This will generate a random secret and upload it to the DC/OS secrets store [14] at the designated path. To use this secret for RPC authentication add the following configutations to your CLI command:
```bash
dcos spark run --submit-args="\
...
--conf spark.mesos.containerizer=mesos \  # Mesos UCR is required for secrets
--conf spark.authenticate=true \  # tell Spark to use authentication
--conf spark.authenticate.enableSaslEncryption=true \  # tell Spark to encrypt with Sasl
--conf spark.authenticate.secret=sparkauthsecret.secret \  # name of file-based secret for Driver, you may change the name
--conf spark.executorEnv._SPARK_AUTH_SECRET=sparkauthsecret.secret \  # name of file-based secret for the Executors
--conf spark.mesos.driver.secret.names=<secret_path> \   # secret path generated in the previous step, for Driver
--conf spark.mesos.driver.secret.filenames=sparkauthsecret.secret \  # tell Mesos to put the secret in this file in the Driver
--conf spark.mesos.executor.secret.names=<secret_path> \  # secret path generated in previous step for Executor
--conf spark.mesos.executor.secret.filenames=sparkauthsecret.secret \  # tell Mesos to put the secret in this File for the Executors
...
"

```



 [11]: https://docs.mesosphere.com/1.9/overview/architecture/components/
 [12]: http://docs.oracle.com/javase/8/docs/technotes/tools/unix/keytool.html
 [13]: https://docs.mesosphere.com/1.10/security/#spaces
 [14]: https://docs.mesosphere.com/latest/security/secrets/
