# Spark DCOS Package

This repo lets you configure, build, and test a new Spark DCOS package.
It is the source for the Spark package in universe.  If you wish to modify
that package, you should do so here, and generate a new package as
described below.

## Configuring

edit `manifest.json`.

## Push a docker image

This will make a docker image from the distribution specified in `manifest.json`

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

Write a universe to `build/universe`.  You can then upload this to
e.g. S3, and point your DCOS cluster at it via `dcos package repo
add`.

```
make universe
```


## Test

```
./bin/test.sh
```

This requires several env variables, and is primarily used in CI.
Read the comment at the top of the file for a complete description.
