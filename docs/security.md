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
*   From the dispatcher to the drivers.
*   From the drivers to their executors.

There are a number of configuration variables relevant to SSL setup. List them with the following command:

    dcos package describe spark --config

Here are the required variables:

| Variable                   | Description                                     |
|----------------------------|-------------------------------------------------|
| `spark.ssl.enabled`        | Whether to enable SSL (default: `false`).       |
| `spark.ssl.keyStoreBase64` | Base64 encoded blob containing a Java keystore. |

The Java keystore (and, optionally, truststore) are created using the [Java keytool][12]. The keystore must contain one private key and its signed public key. The truststore is optional and might contain a self-signed root-ca certificate that is explicitly trusted by Java.

Both stores must be base64 encoded, for example:

    cat keystore | base64 /u3+7QAAAAIAAAACAAAAAgA...

**Note:** The base64 string of the keystore will probably be much longer than the snippet above, spanning 50 lines or so.

With this and the password `secret` for the keystore and the private key, your JSON options file will look like this:

    {
      "security": {
        "ssl": {
          "enabled": true,
          "keyStoreBase64": "/u3+7QAAAAIAAAACAAAAAgA...”,
          "keyStorePassword": "secret",
          "keyPassword": "secret"
        }
      }
    }

Install Spark with your custom configuration:

    dcos package install --options=options.json spark

Make sure to connect the DC/OS cluster only using an SSL connection (i.e. by using an `https://<dcos-url>`). Use the following command to set your DC/OS URL:

    dcos config set core.dcos_url https://<dcos-url>

 [11]: https://docs.mesosphere.com/1.9/overview/architecture/components/
 [12]: http://docs.oracle.com/javase/8/docs/technotes/tools/unix/keytool.html
