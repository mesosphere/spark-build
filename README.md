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

You must have a local DC/OS CLI installed and configured against a
running DC/OS cluster.

```bash
$ cd tests
$ virtualenv -p python3 env
$ source env/bin/activate
$ pip install -r requirements.txt
$ py.test test.py
```

The tests require several env variables.  Read the comment at the top
of the `test.py` for a complete description.
