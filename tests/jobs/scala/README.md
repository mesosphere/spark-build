Spark Applications for Testing and Troubleshooting
---

# Building
To start using Spark test applications on a cluster the project assembly jar needs to be built and uploaded to a publicly
available location e.g. S3 bucket with public access to the resulting jar. To build a jar run:

```
sbt clean assembly
```

It will create an assembly jar `target/scala_2.11/dcos-spark-scala-tests-assembly-<version>.jar` which is ready for upload and use.

# Applications
## MockTaskRunner

[MockTaskRunner](src/main/scala/MockTaskRunner.scala) creates a number of noop Spark tasks specified by `numTasks` each of 
which sleeps for `taskDurationSec`. The main goal of this class is to mimic long-running Spark applications 
(i.e. Spark Streaming) for the testing and troubleshooting purposes.

Usage: 

```
dcos spark run --submit-args="--class MockTaskRunner https://s3.us-east-2.amazonaws.com/<S3 bucket>/dcos-spark-scala-tests-assembly-<version>.jar 4 1800"
```

Example:

```
dcos spark run --verbose --submit-args=" \
--conf spark.executor.cores=1 \
--conf spark.cores.max=4 \
--class MockTaskRunner \
https://s3.us-east-2.amazonaws.com/<S3 bucket>/dcos-spark-scala-tests-assembly-<version>.jar 4 1800"
```

In the example above Spark Driver will launch 4 single-core executors (controlled by `spark.executor.cores` and 
`spark.cores.max` settings), and TaskRunnerApp will run 4 Spark Tasks each sleeping for 30 minutes. Each of the executors
will run only one task and the whole application should complete after 30 minutes (in case executors aren't crashed 
externally during the execution)
