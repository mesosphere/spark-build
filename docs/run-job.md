---
post_title: Run a Spark Job
menu_order: 80
feature_maturity: stable
enterprise: 'no'
---
1.  Before submitting your job, upload the artifact (e.g., jar file)
    to a location visible to the cluster (e.g., HTTP, S3, or HDFS). [Learn more][13].

1.  Run the job.

        dcos spark run --submit-args=`--class MySampleClass http://external.website/mysparkapp.jar 30`

        dcos spark run --submit-args="--py-files mydependency.py http://external.website/mysparkapp.py 30"

        dcos spark run --submit-args="http://external.website/mysparkapp.R"

    You can submit arbitrary pass-through options to this script via the `--submit-args` options.

	If your job runs successfully, you will get a message with the job’s submission ID:

        Run job succeeded. Submission id: driver-20160126183319-0001

1.  View the Spark scheduler progress by navigating to the Spark dispatcher at `http://<dcos-url>/service/spark/`.

1.  View the job's logs through the Mesos UI at `http://<dcos-url>/mesos/`. Or `dcos task log --follow <submission_id>`

# Setting Spark properties

Spark job settings are controlled by configuring [Spark properties][14].

## Submission

All properties are submitted through the `--submit-args` option to `dcos spark run`. There are a few unique options to DC/OS that are not in Spark Submit (for example `--keytab-secret-path`).  View `dcos spark run --help` for a list of all these options. All `--conf` properties supported by Spark can be passed through the command-line with within the `--submit-args` string. 

    dcos spark run --submit-args="--conf spark.executor.memory=4g --supervise --class MySampleClass http://external.website/mysparkapp.jar 30`

## Setting automatic configuration defaults

To set Spark properties with a configuration file, create a
`spark-defaults.conf` file and set the environment variable
`SPARK_CONF_DIR` to the containing directory. [Learn more][15].

## Secrets
Enterprise DC/OS provides a secrets store to enable access to sensitive data such as database passwords, private keys, and API tokens. DC/OS manages secure transportation of secret data, access control and authorization, and secure storage of secret content. The content of a secret is copied and made available within the pod.  A secret can be exposed to drivers as a file and/or as an environment variable. Secrets in Spark are specified with the following configuration properties:
#### File-based secret
```bash
dcos spark run --submit-args="\
...
--conf spark.mesos.driver.secret.name=/mysecret \
--conf spark.mesos.driver.secret.filename=asecret \
...
```
#### Environment-based secret
```bash
dcos spark run --submit-args="\
...
--conf spark.mesos.driver.secret.name=/mysecret \
--conf spark.mesos.driver.secret.envkey=SECRETKEY \
...
```
Multiple secrets can be injected by using a comma-separated list:
```bash
dcos spark run --submit-args="\
...
--conf spark.mesos.driver.secret.name=/user,/password \
--conf spark.mesos.driver.secret.filename=secretuser,seretpassword \
--conf spark.mesos.driver.secret.envkey=USER,PASSWORD \
...
```

**Note:** Secrets are available only in Enterprise DC/OS 1.9 onwards. [Learn more about the secrets store](https://docs.mesosphere.com/1.9/security/secrets/).

### Authorization for Secrets

The path of a secret defines which service IDs can have access to it. You can think of secret paths as namespaces. _Only_ services that are under the same namespace can read the content of the secret.


| Secret                               | Service ID                          | Can service access secret? |
|--------------------------------------|-------------------------------------|----------------------------|
| `secret-svc/Secret_Path1`            | `/user`                             | No                         |
| `secret-svc/Secret_Path1`            | `/user/dev1`                        | No                         |
| `secret-svc/Secret_Path1`            | `/secret-svc`                       | Yes                        |
| `secret-svc/Secret_Path1`            | `/secret-svc/dev1`                  | Yes                        |
| `secret-svc/Secret_Path1`            | `/secret-svc/instance2/dev2`        | Yes                        |
| `secret-svc/Secret_Path1`            | `/secret-svc/a/b/c/dev3`            | Yes                        |
| `secret-svc/instance1/Secret_Path2`  | `/secret-svc/dev1`                  | No                         |
| `secret-svc/instance1/Secret_Path2`  | `/secret-svc/instance2/dev3`        | No                         |
| `secret-svc/instance1/Secret_Path2`  | `/secret-svc/instance1`             | Yes                        |
| `secret-svc/instance1/Secret_Path2`  | `/secret-svc/instance1/dev3`        | Yes                        |
| `secret-svc/instance1/Secret_Path2`  | `/secret-svc/instance1/someDir/dev3`| Yes                        |



**Note:** Absolute paths (paths with a leading slash) to secrets are not supported. The file path for a secret must be relative to the sandbox.

### Binary Secrets

When you need to store binary files into DC/OS secrets store, for example a Kerberos keytab file, your file needs to be base64-encoded as specified in RFC 4648. 

You can use standard `base64` command line utility. Take a look at the following example that is using BSD `base64` command.
``` 
$  base64 -i krb5.keytab -o kerb5.keytab.base64-encoded 
```

`base64` command line utility in Linux inserts line-feeds in the encoded data by default. Disable line-wrapping via  `-w 0` argument.  Here is a sample base64 command in Linux.
``` 
$  base64 -w 0 -i krb5.keytab > kerb5.keytab.base64-encoded 
```

Give the secret basename prefixed with `__dcos_base64__`. For example, `some/path/__dcos_base64__mysecret` and `__dcos_base64__mysecret` will be base64-decoded automatically.

``` 
$  dcos security secrets  create -f kerb5.keytab.base64-encoded  some/path/__dcos_base64__mysecret
```
When you reference the `__dcos_base64__mysecret` secret in your service, the content of the secret will be first base64-decoded, and then copied and made available to your Spark application. Refer to a binary secret only as a file such that it will be automatically decoded and made available as a temporary in-memory file mounted within your container (file-based secrets). 

# DC/OS Overlay Network

To submit a Spark job inside the [DC/OS Overlay Network][16]:

    dcos spark run --submit-args="--conf spark.mesos.containerizer=mesos --conf spark.mesos.network.name=dcos --class MySampleClass http://external.website/mysparkapp.jar"

Note that DC/OS Overlay support requires the [UCR][17], rather than
the default Docker Containerizer, so you must set `--conf spark.mesos.containerizer=mesos`.

# Driver Failover Timeout

The `--conf spark.mesos.driver.failoverTimeout` option specifies the amount of time 
(in seconds) that the master will wait for the driver to reconnect, after being 
temporarily disconnected, before it tears down the driver framework by killing 
all its executors. The default value is zero, meaning no timeout: if the 
driver disconnects, the master immediately tears down the framework.

To submit a job with a nonzero failover timeout:

    dcos spark run --submit-args="--conf spark.mesos.driver.failoverTimeout=60 --class MySampleClass http://external.website/mysparkapp.jar"

**Note:** If you kill a job before it finishes, the framework will persist 
as an `inactive` framework in Mesos for a period equal to the failover timeout. 
You can manually tear down the framework before that period is over by hitting
the [Mesos teardown endpoint][18].

# Versioning

The DC/OS Apache Spark Docker image contains OpenJDK 8 and Python 2.7.6.

DC/OS Apache Spark distributions 1.X are compiled with Scala 2.10.  DC/OS Apache Spark distributions 2.X are compiled with Scala 2.11.  Scala is not binary compatible across minor verions, so your Spark job must be compiled with the same Scala version as your version of DC/OS Apache Spark.

The default DC/OS Apache Spark distribution is compiled against Hadoop 2.6 libraries.  However, you may choose a different version by following the instructions in the "Customize Spark Distribution" section of the Installation page.


[13]: http://spark.apache.org/docs/latest/submitting-applications.html
[14]: http://spark.apache.org/docs/latest/configuration.html#spark-properties
[15]: http://spark.apache.org/docs/latest/configuration.html#overriding-configuration-directory
[16]: https://dcos.io/docs/overview/design/overlay/
[17]: https://dcos.io/docs/1.9/deploying-services/containerizers/ucr/
[18]: http://mesos.apache.org/documentation/latest/endpoints/master/teardown/
[19]: https://docs.mesosphere.com/service-docs/spark/v2.2.0-2.2.0-1/hdfs/
