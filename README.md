Spark DCOS Package
===

This repo lets you configure, build, and test a new Spark DCOS package.
It is the source for the Spark package in universe.  If you wish to modify
that package, you should do so here, and generate a new package as
described below.

Configuring
---

edit `manifest.json`.

Create a package
---

```
./bin/make-package.py
```

This produces a new package in `build/package`

Create a universe
---

```
./bin/make-universe.sh
```

This produces a new universe in `build/universe`.  You can then point your
local `dcos` to this location via `dcos config set package.sources`.

Create a docker image
---

```
./bin/make-docker.sh <spark-dist> <image>
```

* `<spark-dist>`: path to spark distribution
* `<image>`: name of docker image

This creates a new docker image from the given spark distribution.


Test
---

```
./bin/test.sh
```

This performs every build step, including tests.  It builds spark, the docker image,
the package, and the universe.  It spins up a CCM cluster and tests spark against that
cluster.

It requires several env variables.  Read the comment at the top of the file for a
complete description.
