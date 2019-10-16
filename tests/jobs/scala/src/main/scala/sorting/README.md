Sorting Applications
---
## Rationale

Testing across multiple executions, configuration, and even cluster managers requires the 
workloads to have the following properties: 
* provide deterministic input to be able to compare results between runs
* the workload/job should be scalable and provide information about resources/performance ratio
* the workload/job should exercise shuffle operations to load the network and test inter-executor communication
* the workload/job should provide CPU utilization, not only allocation

Based on the available approaches used in the industry for benchmarking distributed data processing frameworks 
([TPC-DS](http://www.tpc.org/tpcds/), [Sort Benchmark](http://sortbenchmark.org/), [Tera Sort](https://mapr.com/whitepapers/terasort-benchmark-comparison-yarn/)), 
sorting benchmark looks like a workload which satisfies all the requirements:
* the input dataset is generated upfront and can be reused across runs, versions, and cluster managers
* Spark performs partitioning of the input data by design so the input dataset will be evenly distributed across launched executors
* distributed sorting implies shuffle operations to exchange sorted partitions between executors in order to achieve the final result (fully sorted dataset)
* string sorting is a CPU-intensive operation and with properly designed dataset will provide high CPU utilization

## Generating test datasets
### Using S3 as the target output location
 
Example of using `TemporaryAWSCredentialsProvider`:
```bash
spark-submit \
--conf spark.hadoop.fs.s3a.impl=org.apache.hadoop.fs.s3a.S3AFileSystem \
--conf spark.hadoop.fs.s3a.aws.credentials.provider=org.apache.hadoop.fs.s3a.TemporaryAWSCredentialsProvider \
--conf spark.hadoop.fs.s3a.endpoint=s3.us-west-2.amazonaws.com \
--conf spark.hadoop.fs.s3a.access.key=${AWS_ACCESS_KEY_ID} \
--conf spark.hadoop.fs.s3a.secret.key=${AWS_SECRET_ACCESS_KEY} \
--conf spark.hadoop.fs.s3a.session.token=${AWS_SESSION_TOKEN} \
--class sorting.DatasetGenerator \
/path/to/spark-build/tests/jobs/scala/target/scala-2.11/dcos-spark-scala-tests-assembly-0.2-SNAPSHOT.jar \
--num-files 10 \
--num-records 1000 \
--static-prefix-length 120 \
--random-suffix-length 8 \
--value-size-bytes 1000000 \
--output-path s3a://<your bucket>/path
```

## Sorting

### Using a dataset from S3 as the input

Example of using `TemporaryAWSCredentialsProvider`:
```bash
spark-submit \
--conf spark.hadoop.fs.s3a.impl=org.apache.hadoop.fs.s3a.S3AFileSystem \
--conf spark.hadoop.fs.s3a.aws.credentials.provider=org.apache.hadoop.fs.s3a.TemporaryAWSCredentialsProvider \
--conf spark.hadoop.fs.s3a.endpoint=s3.us-west-2.amazonaws.com \
--conf spark.hadoop.fs.s3a.access.key=${AWS_ACCESS_KEY_ID} \
--conf spark.hadoop.fs.s3a.secret.key=${AWS_SECRET_ACCESS_KEY} \
--conf spark.hadoop.fs.s3a.session.token=${AWS_SESSION_TOKEN} \
--class sorting.SortingApp \
/path/to/spark-build/tests/jobs/scala/target/scala-2.11/dcos-spark-scala-tests_2.11-0.2-SNAPSHOT.jar s3a://<your bucket>/path