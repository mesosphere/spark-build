# Spark DC/OS Package

This repo lets you configure, build, and test a new Spark DC/OS package.
It is the source for the Spark package in universe.  If you wish to modify
that package, you should do so here, and generate a new package as
described below.

Service documentation can be found here : [DC/OS Apache Spark Documentation](https://docs.mesosphere.com/services/spark/)


## Integration Test Builds Matrix


|  | DC/OS 1.13 | DC/OS 2.0 | DC/OS 2.1 | DC/OS Master |
|------------|------------|------------|------------|------------|
| Permissive | <a href="https://teamcity.mesosphere.io/viewType.html?buildTypeId=DataServices_Spark_Nightly_DCOS_113_SparkBuild_113_Permissive&guest=1"> <img src="https://teamcity.mesosphere.io/app/rest/builds/buildType:(id:DataServices_Spark_Nightly_DCOS_113_SparkBuild_113_Permissive)/statusIcon" /></a > | <a href="https://teamcity.mesosphere.io/viewType.html?buildTypeId=DataServices_Spark_Nightly_DCOS_20_SparkBuild_20_Permissive&guest=1"><img src="https://teamcity.mesosphere.io/app/rest/builds/buildType:(id:DataServices_Spark_Nightly_DCOS_20_SparkBuild_20_Permissive)/statusIcon" /></a > | <a href="https://teamcity.mesosphere.io/viewType.html?buildTypeId=DataServices_Spark_Nightly_DCOS_21_SparkBuild_21_Permissive&guest=1" ><img src="https://teamcity.mesosphere.io/app/rest/builds/buildType:(id:DataServices_Spark_Nightly_DCOS_21_SparkBuild_21_Permissive)/statusIcon" /></a > | <a href="https://teamcity.mesosphere.io/viewType.html?buildTypeId=DataServices_Spark_Nightly_DCOS_master_SparkBuild_master_Permissive&guest=1" ><img src="https://teamcity.mesosphere.io/app/rest/builds/buildType:(id:DataServices_Spark_Nightly_DCOS_master_SparkBuild_master_Permissive)/statusIcon" /> </a > |
| Strict     | <a href="https://teamcity.mesosphere.io/viewType.html?buildTypeId=DataServices_Spark_Nightly_DCOS_113_SparkBuild_113_Strict&guest=1">     <img src="https://teamcity.mesosphere.io/app/rest/builds/buildType:(id:DataServices_Spark_Nightly_DCOS_113_SparkBuild_113_Strict)/statusIcon" /></a >     | <a href="https://teamcity.mesosphere.io/viewType.html?buildTypeId=DataServices_Spark_Nightly_DCOS_20_SparkBuild_20_Strict&guest=1">    <img src="https://teamcity.mesosphere.io/app/rest/builds/buildType:(id:DataServices_Spark_Nightly_DCOS_20_SparkBuild_20_Strict)/statusIcon"  /></a>     | <a href="https://teamcity.mesosphere.io/viewType.html?buildTypeId=DataServices_Spark_Nightly_DCOS_21_SparkBuild_21_Strict&guest=1"  >   <img src="https://teamcity.mesosphere.io/app/rest/builds/buildType:(id:DataServices_Spark_Nightly_DCOS_21_SparkBuild_21_Strict)/statusIcon"  /></a>     | <a href="https://teamcity.mesosphere.io/viewType.html?buildTypeId=DataServices_Spark_Nightly_DCOS_master_SparkBuild_master_Strict&guest=1" >    <img src="https://teamcity.mesosphere.io/app/rest/builds/buildType:(id:DataServices_Spark_Nightly_DCOS_master_SparkBuild_master_Strict)/statusIcon" /></a > |

## Development Dependencies

- GNU Make 3.82+ (the version is important due to usage of multiline bash commands)
- Docker
- Git
- sbt

## Configure

edit `manifest.json`.

## Makefile Targets

### Build environment
```bash
make docker-build
```
This will setup a docker image that can be used to build the spark
distribution, the stub universe, and run the integration tests.

This image will not be invoked by any tests explicitly and is not
required. Rather, it provides a consistent and portable environment for
`make` to be run in.


### Spark Distribution
A spark distribution is required to create a spark framework package.
These distributions (packaged as tarballs) are bundled with a Docker
image.

The following method builds from source. By default the mesosphere/spark
repository will be used but one can use the `SPARK_DIR` override to use any
arbitrary spark source directory. Additionally, `HADOOP_VERSION` may be
provided as an override as only the default in the manifest is built.

```bash
make spark-dist-build
```
This will build Spark from source located in `./spark/` and put the result in `./build/dist/`.
This is useful when you are testing a custom build of Spark.


### Package
The above distribution needs to be bundled into a Docker image and paired with
a CLI in order to complete the package.

```bash
make stub-universe-url
```
This will build and upload a "stub" universe (i.e. singleton repo) containing a Spark package.

### Publishing a local Spark distribution to stub universe
In case a custom Spark distribution needs to be tested on DC/OS and Spark sources are located
in a different directory [publish_local_spark.sh](publish_local_spark.sh) helper script can be used.
The script conditionally builds Spark distribution (either if it is not built yet or if a flag specified) and
runs Makefile's `stub-universe-url` target.

Example output:
```bash
publish_local_spark.sh --help

Usage: publish_local_spark.sh [<options>...]
Options:
--spark-dist-dir <absolute path>  Mandatory. Absolute path to Spark project sources used to build and/or upload Spark archive
--hadoop-version <version>        Optional. Hadoop version to build Spark with. Default: 2.7
--docker-dist-image <image tag>   Optional. Target Docker image to publish. Default: mesosphere/spark-dev:<git commit sha>
--rebuild-docker                  If Docker image should be rebuilt. Default: false
--rebuild-spark                   If Spark distribution should be rebuilt. Default: false
--help                            Print this message
```

Assuming Spark source code is located at `/usr/projects/mesosphere/spark` script invocation will look like:
```bash
publish_local_spark.sh --spark-dist-dir /usr/projects/mesosphere/spark --docker-dist-image user/spark-dev:test
```
`--docker-dist-image` flag is useful when one doesn't have access to default private registry and wants to publish
target image to an available open repository.

## Test

```bash
make test-jars
```
This command will build the payload jar used in the integration tests. Running this command separately is optional, only needed when it's desirable to perform all build operations separately from the test run itself.

```bash
make test
```
This command will run a complete build (if needed) and then run the integration test suite.

It supports the following optional environment variables:
```bash
STUB_UNIVERSE_URL=<space-separated URLs to stub universe.json>
CLUSTER_URL=<URL to existing cluster, otherwise one is created using dcos-launch>
AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY=<AWS credentials, used if ~/.aws/credentials doesn't exist>
```
For more optional settings, take a look at `test.sh`.
