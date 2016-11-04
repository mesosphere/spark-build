---
post_title: Security
menu_order: 40
enterprise: 'yes'
---

# Mesos Security

## SSL

<table class="table">
  <tr>
    <td>
      `security.mesos.ssl.enabled`
    </td>

    <td>
      Set to true to enable SSL on Mesos communication (default: false).
    </td>
  </tr>
</table>


## Authentication

When running in
[DC/OS strict security mode](https://docs.mesosphere.com/latest/administration/id-and-access-mgt/),
Both the dispatcher and jobs must authenticate to Mesos using a [DC/OS
Service Account](https://docs.mesosphere.com/1.8/administration/id-and-access-mgt/service-auth/).
Follow these instructions to authenticate in strict mode:

1. Create a Service Account

Instructions
[here](https://docs.mesosphere.com/1.8/administration/id-and-access-mgt/service-auth/universe-service-auth/).

2. Assign Permissions

First, allow Spark to run tasks as root:

```
$ curl -k -L -X PUT \
       -H "Authorization: token=$(dcos config show core.dcos_acs_token)" \
       "$(dcos config show core.dcos_url)/acs/api/v1/acls/dcos:mesos:master:task:user:root" \
       -d '{"description":"Allows root to execute tasks"}' \
       -H 'Content-Type: application/json'

$ curl -k -L -X PUT \
     -H "Authorization: token=$(dcos config show core.dcos_acs_token)" \
     "$(dcos config show core.dcos_url)/acs/api/v1/acls/dcos:mesos:master:task:user:root/users/${SERVICE_ACCOUNT_NAME}/create"
```

Now you must allow Spark to register under the desired role.  This is
the value used for `service.role` when installing Spark (default:
`*`):

```
$ export ROLE=<service.role value>
$ curl -k -L -X PUT \
       -H "Authorization: token=$(dcos config show core.dcos_acs_token)" \
       "$(dcos config show core.dcos_url)/acs/api/v1/acls/dcos:mesos:master:framework:role:${ROLE}" \
       -d '{"description":"Allows ${ROLE} to register as a framework with the Mesos master"}' \
       -H 'Content-Type: application/json'

$ curl -k -L -X PUT \
       -H "Authorization: token=$(dcos config show core.dcos_acs_token)" \
       "$(dcos config show core.dcos_url)/acs/api/v1/acls/dcos:mesos:master:framework:role:${ROLE}/users/${SERVICE_ACCOUNT_NAME}/create"
```

3. Install Spark

```
$ dcos package install spark --options=config.json
```

Where `config.json` contains the following JSON.  Replace
`<principal>` with the name of your service account, and
`<secret_name>` with the name of the DC/OS secret containing your
service account's private key.  These values were created in Step #1
above.

```
{
    "service": {
        "principal": "<principal>",
        "user": "nobody"
    },
    "security": {
        "mesos": {
            "authentication": {
                "secret_name": "<secret_name>"
            }
        }
    }
}
```

4. Submit a Job

We've now installed the Spark Dispatcher, which is authenticating
itself to the Mesos master.  Spark jobs are also frameworks which must
authenticate.  The dispatcher will pass the secret along to the jobs,
so all that's left to do is configure our jobs to use DC/OS authentication:

```
$ PROPS="-Dspark.mesos.driverEnv.MESOS_MODULES=file:///opt/mesosphere/etc/mesos-scheduler-modules/dcos_authenticatee_module.json "
$ PROPS+="-Dspark.mesos.driverEnv.MESOS_AUTHENTICATEE=com_mesosphere_dcos_ClassicRPCAuthenticatee "
$ PROPS+="-Dspark.mesos.principal=<principal>"
$ dcos spark run --submit-args="${PROPS} ..."
```

# Spark SSL

SSL support in DC/OS Spark encrypts the following channels:

*   From the [DC/OS admin router][11] to the dispatcher
*   From the dispatcher to the drivers
*   From the drivers to their executors

There are a number of configuration variables relevant to SSL setup.
List them with the following command:

    $ dcos package describe spark --config

There are only two required variables:

<table class="table">
  <tr>
    <th>
      Variable
    </th>

    <th>
      Description
    </th>
  </tr>

  <tr>
    <td>
      `spark.ssl.enabled`
    </td>

    <td>
      Set to true to enable SSL (default: false).
    </td>
  </tr>

  <tr>
    <td>
      spark.ssl.keyStoreBase64
    </td>

    <td>
      Base64 encoded blob containing a Java keystore.
    </td>
  </tr>
</table>

The Java keystore (and, optionally, truststore) are created using the
[Java keytool][12]. The keystore must contain one private key and its
signed public key. The truststore is optional and might contain a
self-signed root-ca certificate that is explicitly trusted by Java.

Both stores must be base64 encoded, e.g. by:

    $ cat keystore | base64 /u3+7QAAAAIAAAACAAAAAgA...

**Note:** The base64 string of the keystore will probably be much
longer than the snippet above, spanning 50 lines or so.

With this and the password `secret` for the keystore and the private
key, your JSON options file will look like this:

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

    $ dcos package install --options=options.json spark

In addition to the described configuration, make sure to connect the
DC/OS cluster only using an SSL connection, i.e. by using an
`https://<dcos-url>`. Use the following command to set your DC/OS URL:

    $ dcos config set core.dcos_url https://<dcos-url>

 [11]: https://docs.mesosphere.com/administration/dcosarchitecture/components/
 [12]: http://docs.oracle.com/javase/8/docs/technotes/tools/unix/keytool.html