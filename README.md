# Spark DC/OS Package

This repo lets you configure, build, and test a new Spark DC/OS package.
It is the source for the Spark package in universe.  If you wish to modify
that package, you should do so here, and generate a new package as
described below.

## Configuring

edit `manifest.sh`.

## Push a docker image

Build and push a docker image using the Spark distribution specified in `manifest.sh`

```
DOCKER_IMAGE=<name> make docker
```

## Create a package

Write a package to `build/package`.  Use the `DOCKER_IMAGE` name you
created above.

```
DOCKER_IMAGE=<name> make package
```

## Create a universe

Write a universe to `build/spark-universe`.  You can then upload this to
e.g. S3, and point your DC/OS cluster at it via `dcos package repo
add`.

```
make universe
```


## Test

```
make test
```

This requires several env variables, and is primarily used in CI.  It
calls `make package` and `make universe`.  Read the comment at the top
of the file for a complete description.
