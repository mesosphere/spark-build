# Spark DC/OS Package

This repo lets you configure, build, and test a new Spark DC/OS package.
It is the source for the Spark package in universe.  If you wish to modify
that package, you should do so here, and generate a new package as
described below.

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
image built in the `docker-dist` target below.
There are three flavors of distribution that can be made:
```bash
make manifest-dist
```
This command will simply retrieve the spark dist URI set in the manifest.
`SPARK_DIST_URI` can be overridden to pull an arbitrary URI

The following two methods builds from source. By default the mesosphere/spark
repository will be used but one can use the `SPARK_DIR` override to use any
arbitrary spark source directory. Additionally, `HADOOP_VERSION` may be
provided as an override as only the default in the manifest is built.

```bash
make prod-dist
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

## Test

```bash
make test-jars
```
This command will build the payload jars used in the integration tests. Running this command separately is optional, only needed when it's desirable to perform all build operations separately from the test run itself.

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
