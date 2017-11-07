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
This will build Spark from source using the slow, but production-grade
`./dev/make-distribution.sh` script in the spark repo.

```bash
make dev-dist
```
This will build Spark from source using a fast `sbt` compile.  This is the
most common way to build a Spark package during development.


### Package
The above distribution needs to be bundled into a Docker image and paried with
a CLI in order to complete the package.

```bash
make cli
```
Triggers the build for the binary go CLI

```bash
make docker-login
make docker-dist
```
This command will build and push the Docker image that will be used by
the package template. Use `DOCKER_DIST_IMAGE` override to set an alternative
dockerhub repo. Addtionally, the tag for this container will be the git SHA
unless overridden with `GIT_COMMIT`. Note: the login is a separate command
to allow using the current Docker user session without providing parameters

```bash
make stub-universe-url
```
This will build a "stub" universe (i.e. singleton repo) containing a
Spark package and upload it. The aforementioned build targets of docker-dist
and cli are required by this step and will be built according to defaults if not
explicitly built before this step is run.

## Test

```bash
make cluster-url
```
This command will spin up a cluster unless `CLUSTER_URL` is set in the current
environment. A cluster is required to satisfy the testing target. The URL of
this cluster will be left in a file called `cluster-url`.

```bash
make test-env
```
This command will setup a virtual environment that will contain the CLI and
other requirements for running the pytest integration suite

```bash
make test
```
This command will run a complete build and then run the integration test suite.
This includes:
```bash
make manifest-dist
make docker-dist
make cli
make stub-universe-url
make test-env
make cluster_info.json
make test-cluster
```
Note: these steps can all be individually triggered to allow specifying
parameters like dist type and Docker image repo

Note: the `make docker-dist` step will use Docker build and the current build
image does not support docker-in-docker so if you are building from within
the included docker-build image, then the `make docker-dist` step must be done
outside the container
