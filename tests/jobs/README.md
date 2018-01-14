# Spark Examples and Test Jobs
This folder contains jobs that Mesosphere uses to exercise Spark functionality and integration with other data services (e.g. HDFS and Kafka). They can also serve as examples of how to setup various more advanced functionality, for example the Kafka pipeine in `KafkaJobs.scala` and `SpamHam.scala`. 

The individual source files contain documentation on their use.

## Building
To build the Scala-based application(s): 
```bash
cd scala
sbt assembly
```
This will produce a `SNAPSHOT` jar within the `target/scala-2.XX` directory that can be run locally or uploaded to a cluster-accessible file system to run on a DC/OS cluster. 

The Python and R example jobs are scripts and do not need to be built. 