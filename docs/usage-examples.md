---
layout: layout.pug
navigationTitle: 
excerpt:
title: Usage Example 
menuWeight: 10
featureMaturity:

---

1.  Perform a default installation by following the instructions in the Install and Customize section of this topic.

1.  Run a Spark job:

        dcos spark run --submit-args="--class org.apache.spark.examples.SparkPi https://downloads.mesosphere.com/spark/assets/spark-examples_2.11-2.0.1.jar 30"

1.  Run a Python Spark job:

        dcos spark run --submit-args="https://downloads.mesosphere.com/spark/examples/pi.py 30"

1.  Run an R Spark job:

        dcos spark run --submit-args="https://downloads.mesosphere.com/spark/examples/dataframe.R"

1.  View your job:

Visit the Spark cluster dispatcher at `http://<dcos-url>/service/spark/` to view the status of your job. Also visit the Mesos UI at `http://<dcos-url>/mesos/` to see job logs.

## Advanced

*   Run an Spark Streaming job with Kafka: Examples of Spark Streaming applications that connect to a secure Kafka cluster can be found at [spark-build][https://github.com/mesosphere/spark-build/blob/beta-2.1.1-2.2.0-2/tests/jobs/scala/src/main/scala/KafkaJobs.scala]. As mentioned in the [kerberos][https://docs.mesosphere.com/services/spark/2.1.0-2.2.0-2/kerberos/] section, Spark requires a JAAS file, the `krb5.conf`, and the keytab. An example of the JAAS file is: 
        
        KafkaClient {
            com.sun.security.auth.module.Krb5LoginModule required
            useKeyTab=true
            storeKey=true
            keyTab="/mnt/mesos/sandbox/kafka-client.keytab"
            useTicketCache=false
            serviceName="kafka"
            principal="client@LOCAL";
        };
    
    The corresponding `dcos spark` command would be: 

        dcos spark run --submit-args="\
        --conf spark.mesos.containerizer=mesos \  # required for secrets
        --conf spark.mesos.uris=<URI_of_jaas.conf> \
        --conf spark.mesos.driver.secret.names=spark/__dcos_base64___keytab \  # base64 encoding of binary secrets required in DC/OS 1.10 or lower
        --conf spark.mesos.driver.secret.filenames=kafka-client.keytab \
        --conf spark.mesos.executor.secret.names=spark/__dcos_base64___keytab \
        --conf spark.mesos.executor.secret.filenames=kafka-client.keytab \
        --conf spark.mesos.task.labels=DCOS_SPACE:/spark \ 
        --conf spark.scheduler.minRegisteredResourcesRatio=1.0 \
        --conf spark.executorEnv.KRB5_CONFIG_BASE64=W2xpYmRlZmF1bHRzXQpkZWZhdWx0X3JlYWxtID0gTE9DQUwKCltyZWFsbXNdCiAgTE9DQUwgPSB7CiAgICBrZGMgPSBrZGMubWFyYXRob24uYXV0b2lwLmRjb3MudGhpc2Rjb3MuZGlyZWN0b3J5OjI1MDAKICB9Cg== \
        --conf spark.mesos.driverEnv.KRB5_CONFIG_BASE64=W2xpYmRlZmF1bHRzXQpkZWZhdWx0X3JlYWxtID0gTE9DQUwKCltyZWFsbXNdCiAgTE9DQUwgPSB7CiAgICBrZGMgPSBrZGMubWFyYXRob24uYXV0b2lwLmRjb3MudGhpc2Rjb3MuZGlyZWN0b3J5OjI1MDAKICB9Cg== \
        --class MyAppClass <URL_of_jar> [application args]"



*Note* There are additional walkthroughs available in the `docs/walkthroughs/` directory of Mesosphere's `spark-build` [repo](https://github.com/mesosphere/spark-build/docs/walkthroughs/)
