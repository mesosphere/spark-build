---
post_title: Usage Example 
menu_order: 10
feature_maturity: stable
enterprise: 'no'
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
