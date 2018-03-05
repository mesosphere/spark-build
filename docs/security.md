---
layout: layout.pug
navigationTitle: 
excerpt:
title: Security
menuWeight: 40

---

This topic describes how to configure DC/OS service accounts for Spark.

When running in [DC/OS strict security mode](https://docs.mesosphere.com/1.9/security/), both the dispatcher and jobs
must authenticate to Mesos using a [DC/OS Service Account](https://docs.mesosphere.com/1.9/security/service-auth/).

Follow these instructions to [authenticate in strict mode](https://docs.mesosphere.com/services/spark/spark-auth/).

# Using the Secret Store

DC/OS Enterprise allows users to add privileged information in the form of a file to the DC/OS secret store. These files
can be referenced in Spark jobs and used for authentication and authorization with various external services (e.g.
HDFS). For example, we use this functionality to pass the Kerberos Keytab. Details about how to use Secrets can be found
at [official documentation](https://docs.mesosphere.com/latest/security/ent/secrets/).

### Where to Place Secrets
In order for a secret to be available to Spark, it must be placed in a path
that can be accessed by the Spark service.
If only Spark requires access to a secret, store the secret in a path
that matches the name of the Spark service (e.g. `spark/secret`).  See the [Secrets
Documentation about Spaces][13] for details about how secret paths restrict
service access to secrets.

### Limitations
Anyone who has access to the Spark (Dispatcher) service instance has access to all secrets available to it. Do not
grant users access to the Spark Dispatchers instance unless they are also permitted to access all secrets available
to the Spark Dispatcher instance.

### Binary Secrets

When you need to store binary files into DC/OS secrets store, for example a Kerberos keytab file, your file needs to be base64-encoded as specified in RFC 4648.

You can use standard `base64` command line utility. Take a look at the following example that is using BSD `base64` command.
```bash
$ base64 -i krb5.keytab -o kerb5.keytab.base64-encoded
```

`base64` command line utility in Linux inserts line-feeds in the encoded data by default. Disable line-wrapping via  `-w 0` argument.  Here is a sample base64 command in Linux.
```bash
$ base64 -w 0 -i krb5.keytab > kerb5.keytab.base64-encoded
```

Give the secret basename prefixed with `__dcos_base64__`. For example, `some/path/__dcos_base64__mysecret` and `__dcos_base64__mysecret` will be base64-decoded automatically.

```bash
$ dcos security secrets  create -f kerb5.keytab.base64-encoded  some/path/__dcos_base64__mysecret
```
When you reference the `__dcos_base64__mysecret` secret in your service, the content of the secret will be first base64-decoded, and then copied and made available to your Spark application. Refer to a binary secret only as a file such that it will be automatically decoded and made available as a temporary in-memory file mounted within your container (file-based secrets).


# Using Mesos Secrets

Once a secret has been added in the secret store,
you can pass them to Spark with the `spark.mesos.<task-name>.secret.names` and
`spark.mesos.<task-name>.secret.<filenames|envkeys>` configuration parameters where `<task-name>` is either `driver` or
`executor`. Specifying `filenames` or `envkeys` will materialize the secret as either a file-based secret or an
environment variable. These configuration parameters take comma-separated lists that are "zipped" together to make the
final secret file or environment variable. We recommend using file-based secrets whenever possible as they are more
secure than environment variables.

**NOTE**: Secrets are only supported for Mesos containerizer and not for the Docker containerizer.
To use the Mesos containerizer, add this configuration:
```
--conf spark.mesos.containerizer=mesos
```

For example to use a secret named `spark/my-secret-file` as a file in the driver _and_ the executors add these configuration
parameters:
```
--conf spark.mesos.containerizer=mesos
--conf spark.mesos.driver.secret.names=spark/my-secret-file
--conf spark.mesos.driver.secret.filenames=target-secret-file
--conf spark.mesos.executor.secret.names=spark/my-secret-file
--conf spark.mesos.executor.secret.filenames=target-secret-file
```
this will put the contents of the secret `spark/my-secret-file` in a secure RAM-FS mounted secret file named
`target-secret-file` in the driver and executors sandboxes. If you want to use a secret as an environment variable (e.g.
AWS credentials) you change the configurations to be the following: 
```
--conf spark.mesos.containerizer=mesos
--conf spark.mesos.driver.secret.names=/spark/my-aws-secret,/spark/my-aws-key
--conf spark.mesos.driver.secret.envkeys=AWS_SECRET_ACCESS_KEY,AWS_ACCESS_KEY_ID
```
This assumes that your secret access key is stored in a secret named `spark/my-aws-secret` and your secret key ID in
`spark/my-aws-key`.

### Limitations
When using a combination of environment and file-based secrets there needs to be an equal number of sinks and secret
sources (i.e. files and environment variables). For example
```
--conf spark.mesos.containerizer=mesos
--conf spark.mesos.driver.secret.names=/spark/my-secret-file,/spark/my-secret-envvar
--conf spark.mesos.driver.secret.filenames=target-secret-file,placeholder-file
--conf spark.mesos.driver.secret.envkeys=PLACEHOLDER,SECRET_ENVVAR
```
will place the content of `spark/my-secret-file` into the `PLACEHOLDER` environment variable and the `target-secret-file` file
as well as the content of `spark/my-secret-envvar` into the `SECRET_ENVVAR` and `placeholder-file`. In the case of binary
secrets (tagged with `__dcos_base64__`, for example) the environment variable will still be empty because environment
variables cannot be assigned to binary values.

# Spark SSL

SSL support in DC/OS Apache Spark encrypts the following channels:

*   From the [DC/OS admin router][11] to the dispatcher.
*   Files served from the drivers to their executors.

To enable SSL, a Java keystore (and, optionally, truststore) must be provided, along with their passwords. The first
three settings below are **required** during job submission. If using a truststore, the last two are also **required**:

| Variable                         | Description                                     |
|----------------------------------|-------------------------------------------------|
| `--keystore-secret-path`         | Path to keystore in secret store                |
| `--keystore-password`            | The password used to access the keystore        |
| `--private-key-password`         | The password for the private key                |
| `--truststore-secret-path`       | Path to truststore in secret store              |
| `--truststore-password`          | The password used to access the truststore      |


In addition, there are a number of Spark configuration variables relevant to SSL setup.  These configuration settings
are **optional**:

| Variable                         | Description           | Default Value |
|----------------------------------|-----------------------|---------------|
| `spark.ssl.enabledAlgorithms`    | Allowed cyphers       | JVM defaults  |
| `spark.ssl.protocol`             | Protocol              | TLS           |


The keystore and truststore are created using the [Java keytool][12]. The keystore must contain one private key and its
signed public key. The truststore is optional and might contain a self-signed root-ca certificate that is explicitly
trusted by Java.

Both stores must be base64 encoded without newlines, for example:

```bash
cat keystore | base64 -w 0 > keystore.base64
cat keystore.base64
/u3+7QAAAAIAAAACAAAAAgA...
```

**Note:** The base64 string of the keystore will probably be much longer than the snippet above, spanning 50 lines or
so.

Add the stores to your secrets in the DC/OS secret store. For example, if your base64-encoded keystores and truststores
are server.jks.base64 and trust.jks.base64, respectively, then use the following commands to add them to the secret
store: 

```bash
dcos security secrets create /spark/__dcos_base64__keystore --value-file server.jks.base64
dcos security secrets create /spark/__dcos_base64__truststore --value-file trust.jks.base64
```

You must add the following configurations to your `dcos spark run ` command.
The ones in parentheses are optional:

```bash

dcos spark run --verbose --submit-args="\
--keystore-secret-path=<path/to/keystore, e.g. spark/__dcos_base64__keystore> \
--keystore-password=<password to keystore> \
--private-key-password=<password to private key in keystore> \
(—-truststore-secret-path=<path/to/truststore, e.g. spark/__dcos_base64__truststore> \)
(--truststore-password=<password to truststore> \)
(—-conf spark.ssl.enabledAlgorithms=<cipher, e.g., TLS_RSA_WITH_AES_128_CBC_SHA256> \)
--class <Spark Main class> <Spark Application JAR> [application args]"
```

**Note:** If you specify environment-based secrets with `spark.mesos.[driver|executor].secret.envkeys`, the keystore and
truststore secrets will also show up as environment-based secrets, due to the way secrets are implemented. You can
ignore these extra environment variables.

# Spark SASL (Executor authentication and BlockTransferService encryption)
Spark uses Simple Authentication Security Layer (SASL) to authenticate Executors with the Driver and for encrypting
messages sent between components. This functionality relies on a shared secret between all components you expect to
communicate with each other. A secret can be generated with the DC/OS Spark CLI 
```bash
dcos spark secret <secret_path>
# for example
dcos spark secret /spark/sparkAuthSecret
```
This will generate a random secret and upload it to the DC/OS secrets store [14] at the designated path. To use this
secret for RPC authentication add the following configutations to your CLI command:
```bash
dcos spark run --submit-args="\
...
--executor-auth-secret=/spark/sparkAuthSecret
...
"

```



 [11]: https://docs.mesosphere.com/latest/overview/architecture/components/
 [12]: http://docs.oracle.com/javase/8/docs/technotes/tools/unix/keytool.html
 [13]: https://docs.mesosphere.com/latest/security/ent/#spaces-for-secrets
 [14]: https://docs.mesosphere.com/latest/security/secrets/
