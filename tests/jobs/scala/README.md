Spark Applications for Testing and Troubleshooting
---

# Building
To start using Spark test applications on a cluster the project assembly jar needs to be built and uploaded to a publicly
available location e.g. S3 bucket with public access to the resulting jar. To build a jar run:

```
sbt clean assembly
```

It will create an assembly jar `target/scala_2.11/dcos-spark-scala-tests-assembly-<version>.jar` which is ready for upload and use.

# Applications
## MockTaskRunner

[MockTaskRunner](src/main/scala/MockTaskRunner.scala) creates a number of noop Spark tasks specified by `numTasks` each of 
which sleeps for `taskDurationSec`. The main goal of this class is to mimic long-running Spark applications 
(i.e. Spark Streaming) for the testing and troubleshooting purposes.

Usage: 

```
dcos spark run --submit-args="--class MockTaskRunner \
https://s3.us-east-2.amazonaws.com/<S3 bucket>/dcos-spark-scala-tests-assembly-<version>.jar numTasks taskDurationSec"
```

Example:

```
dcos spark run --verbose --submit-args=" \
--conf spark.executor.cores=1 \
--conf spark.cores.max=4 \
--class MockTaskRunner \
https://s3.us-east-2.amazonaws.com/<S3 bucket>/dcos-spark-scala-tests-assembly-<version>.jar 4 1800"
```

In the example above Spark Driver will launch 4 single-core executors (controlled by `spark.executor.cores` and 
`spark.cores.max` settings), and TaskRunnerApp will run 4 Spark Tasks each sleeping for 30 minutes. Each of the executors
will run only one task and the whole application should complete after 30 minutes (in case executors aren't crashed 
externally during the execution)

## ShuffleApp
[ShuffleApp](src/main/scala/ShuffleApp.scala) performs a naive shuffle and is aimed at testing communications between 
executors e.g. within a virtual/overlay network. It's a slight modification of GroupByTest from Spark Examples but with 
a deterministic sequential key generation which doesn't rely on random number generator.
 

Usage: 

```
dcos spark run --submit-args="--class MockTaskRunner \
https://s3.us-east-2.amazonaws.com/<S3 bucket>/dcos-spark-scala-tests-assembly-<version>.jar numMappers totalUniqueKeys valueSize numReducers sleepBeforeShutdown"
```

Example:

```
dcos spark run --verbose --submit-args=" \
--conf spark.executor.cores=1 \
--conf spark.cores.max=4 \
--conf=spark.scheduler.minRegisteredResourcesRatio=1 \
--conf=spark.scheduler.maxRegisteredResourcesWaitingTime=3m \
--class ShuffleApp \
https://s3.us-east-2.amazonaws.com/<S3 bucket>/dcos-spark-scala-tests-assembly-<version>.jar 4 12000 100 4 300"

```

In the example above Spark Driver will launch 4 single-core executors (controlled by `spark.executor.cores` and 
`spark.cores.max` settings), and wait for all of them get to the running state (ratio is controlled by 
`spark.scheduler.minRegisteredResourcesRatio` and wait time by `spark.scheduler.maxRegisteredResourcesWaitingTime` 
properties). When all executors are up, 12000 unique keys will be generated 4 times i.e. each of 4 partitions will contain 
the same set of keys which will then be grouped by 4 reducers. `sleepBeforeShutdown` parameter is needed in order to
verify tasks' properties while they're running and avoid quick application termination. 

## ProvidedPackages
[ProvidedPackages](src/main/scala/ProvidedPackages.scala) adds number from 1 to `inputNum`, where the default value of `inputNum` is 10, and prints the sum. To perform the addition it is using the `guava` library, which would be marked as provided in the [build.sbt](build.sbt). The main aim of this class is to test the availability of the `guava` library in the classpath of driver as well as executors, without shifting it with the main application jar. This can be achieved by specifying `guava` package's maven coordinates in the `--packages` flag.

Usage:

```
dcos spark run --submit-args="--class ProvidedPackages \
https://s3.us-east-2.amazonaws.com/<S3 Bucket>/dcos-spark-scala-tests-assembly-<version>.jar inputNum"
```

Example:

```
dcos spark run --verbose --submit-args=" \
--packages=com.google.guava:guava:23.0 \
--class ProvidedPackages \
https://s3.us-east-2.amazonaws.com/<S3 bucket>/dcos-spark-scala-tests-assembly-<version>.jar 20"

```

In the example above Spark will download the `guava` package in the classpath of driver as well as executors. The classpath will be decided by the `spark.jars.ivy` setting.

## SecretConfs
[SecretConfs](src/main/scala/SecretConfs.scala) reads the configurations related to Mesos Secret and prints the secret value. If it is a reference based secret, read the secret name using `spark.mesos.driver.secret.names` and fetch the corresponding secret value from DC/OS Secret Store. If it is a value based secret, read the value using `spark.mesos.driver.secret.values` and prints it. It handles file based as well as environment based secrets. It accepts one argument `authToken`.

Usage:

```
dcos spark run --submit-args="--class SecretConfs \
https://s3.us-east-2.amazonaws.com/<S3 Bucket>/dcos-spark-scala-tests-assembly-<version>.jar authToken"
```

Examples:

```
dcos spark run --verbose --submit-args=" \
--conf spark.mesos.driver.secret.names='/path/to/secret' \
--conf spark.mesos.driver.secret.envkeys='SECRET_ENV_KEY' \
--class SecretConfs \
https://s3.us-east-2.amazonaws.com/<S3 bucket>/dcos-spark-scala-tests-assembly-<version>.jar xyz123"
```

OR

```
dcos spark run --verbose --submit-args=" \
--conf spark.mesos.driver.secret.values='secret-value' \
--conf spark.mesos.driver.secret.envkeys='SECRET_ENV_KEY' \
--class SecretConfs \
https://s3.us-east-2.amazonaws.com/<S3 bucket>/dcos-spark-scala-tests-assembly-<version>.jar xyz123"
```

OR

```
dcos spark run --verbose --submit-args=" \
--conf spark.mesos.driver.secret.names='/path/to/secret' \
--conf spark.mesos.driver.secret.filenames='/topsecret' \
--class SecretConfs \
https://s3.us-east-2.amazonaws.com/<S3 bucket>/dcos-spark-scala-tests-assembly-<version>.jar xyz123"
```

OR

```
dcos spark run --verbose --submit-args=" \
--conf spark.mesos.driver.secret.values='username' \
--conf spark.mesos.driver.secret.filenames='/whoami' \
--class SecretConfs \
https://s3.us-east-2.amazonaws.com/<S3 bucket>/dcos-spark-scala-tests-assembly-<version>.jar xyz123"
```

