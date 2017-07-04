# Spark DC/OS Package

This repo lets you configure, build, and test a new Spark DC/OS package.
It is the source for the Spark package in universe.  If you wish to modify
that package, you should do so here, and generate a new package as
described below.

## Configure

edit `manifest.json`.

## Build

### Package

```bash
make universe
```

This will build a "stub" universe (i.e. singleton repo) containing a
Spark package.  It will build the docker image referenced in the
package using the Spark distribution specified in `manifest.json`.

Prefixing with `DIST=prod` will build Spark from source using the
slow, but production-grade `./dev/make-distribution.sh` script in the
spark repo.

Prefixing with `DIST=dev` will build Spark from source using a fast
`sbt` compile.  This is the most common way to build a Spark package
during development.

Prefixing with `DOCKER_IMAGE=<image>` will override the default
behavior of building and uploading a docker image to
`mesosphere/spark-dev:<commit>`

### Docker Image

```bash
make docker
```

This is called when you build a Spark package, but sometimes you might
wish to just create a docker image, such as when you want to test a
new Spark distribution in client mode, rather than in cluster mode
through the Dispatcher.

`make docker` supports the same `DIST` and `DOCKER_IMAGE` environment
variables as does `make universe`.

## Test

You must have a local DC/OS CLI installed and configured against a
running DC/OS cluster.

```bash
make test
```

This command requires several environment variables.  Read the top of
`bin/test.sh` for the full list.
