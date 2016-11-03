Building a Custom Spark Image
=============================

Overview
--------
To build a custom Spark image, with a custom version of Spark or other libraries, 
such as Hadoop, Python, or R, follow the steps below. This build does the following:
1. Builds a Docker image containing Spark and other libraries.
1. Builds a DC/OS package (also called a "universe") based on this Docker image.
1. Uploads this package to Amazon S3.

Prerequisites
-------------
* [AWS Command Line Interface](https://aws.amazon.com/cli/) (CLI)
* The [jq](https://github.com/stedolan/jq) JSON parser

Custom Spark Version, Hadoop Version
------------------------------------
Edit `manifest.json`, and set `spark_uri` to point to a custom Spark build. This custom build may 
contain a custom version of Spark or Hadoop.
To build a custom version of Spark, run
`./dev/make-distribution.sh` in your Spark project directory, according to the instructions
[here](http://spark.apache.org/docs/latest/building-spark.html#building-a-runnable-distribution). 
Make sure to set the sparkr flag if you will be using SparkR.

Custom Python, R Versions
-------------------------
Edit `docker/Dockerfile` to install custom versions of Python or R in the Docker image.

To install a custom version of Python: the base Docker image already comes with a 
version of Python. [Add instructions to replace with another Python version ...]

To install a custom version of R, replace the lines 
```
RUN apt-get update && \
    apt-get install -y r-base
```
with the instructions to install a custom version of R.

Run the Custom Build
--------------------
```
DOCKER_IMAGE=<docker-name> S3_BUCKET=<bucket> S3_DIR_PATH=<dir> make universe 
```

At the end of the build output, you will see the URL to the newly built stub universe.

Environment Variables
---------------------
Here are more details about the environment variables in the command above:

DOCKER_IMAGE: Name of the docker image to be uploaded, with the
Docker user name and image name and version. For example: 
`DOCKER_IMAGE=johnsmith/myspark:v1`

S3_BUCKET, S3_DIR_PATH: The Amazon S3 bucket and path where the final build is uploaded.
For example, `S3_BUCKET=mybucket S3_DIR_PATH=mydir`

For more environment variables, see the comments in `bin/universe.sh` and
`bin/dcos-commons-tools`.

Install the Custom Build in DC/OS
---------------------------------
```
dcos package repo add <stub-universe-url> --index=0
```
where `<stub-universe-url>` is the URL to the newly built universe. For example:
```
dcos package repo add <https://mybucket.s3.amazonaws.com/mydir/stub-universe-spark.zip> --index=0
```

Then install Spark as usual:
```
dcos package install spark
```

