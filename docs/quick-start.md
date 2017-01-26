---
post_title: Quick Start
menu_order: 0
feature_maturity: stable
enterprise: 'no'
---

1.  Install DC/OS Spark via the DC/OS CLI. **Note:** If you are using Enterprise DC/OS, you may need to follow additional instructions. See the Install and Customize section for more information.

        $ dcos package install spark

1.  Run a Spark job:

        $ dcos spark run --submit-args="--class org.apache.spark.examples.SparkPi https://downloads.mesosphere.com/spark/assets/spark-examples_2.10-1.4.0-SNAPSHOT.jar 30"

1.  Run a Python Spark job:

        $ dcos spark run --submit-args="https://downloads.mesosphere.com/spark/examples/pi.py 30"

1.  View your job:

    Visit the Spark cluster dispatcher at
`http://<dcos-url>/service/spark/` to view the status of your job.
Also visit the Mesos UI at `http://<dcos-url>/mesos/` to see job logs.
