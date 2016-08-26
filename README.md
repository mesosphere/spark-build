# Spark DC/OS Package

This repo lets you configure, build, and test a new Spark DC/OS package.
It is the source for the Spark package in universe.  If you wish to modify
that package, you should do so here, and generate a new package as
described below.

## Configuring

edit `manifest.json`.

## Push a docker image

Build and push a docker image using the Spark distribution specified in `manifest.json`. This is also executed automatically via `make build`, below.

```
DOCKER_IMAGE=<name> make docker
```

## Create a CLI package, docker image, and universe

The `DOCKER_IMAGE` value may either be a provided custom value, or may be left unset to automatically use the current git commit SHA. The created universe and CLI will be uploaded to a default S3 bucket, or may be customized as in the example below:

```
DOCKER_IMAGE=<name> \
S3_BUCKET=<your-bucket> \
S3_DIR_PATH=<base-path-in-bucket> \
    make build
```

## Test

```
make test
```

This requires several env variables, and is primarily used in CI. Read the comment at the top of the file for a complete description.
