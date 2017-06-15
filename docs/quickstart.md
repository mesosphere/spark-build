---
post_title: Spark Quickstart
menu_order: 10
feature_maturity: stable
enterprise: 'no'
---

This tutorial will get you up and running in minutes with Spark. You will install the DC/OS Spark.

**Prerequisites:**

-  [DC/OS and DC/OS CLI installed](https://docs.mesosphere.com/1.9/installing/) with a minimum of three agent nodes with eight GB of memory and ten GB of disk available on each agent.
-  Depending on your [security mode](https://docs.mesosphere.com/1.9/overview/security/security-modes/), Spark requires a service authentication for access to DC/OS. For more information, see [Configuring DC/OS Access for Spark](https://docs.mesosphere.com/service-docs/spark/spark-auth/).

   | Security mode | Service Account |
   |---------------|-----------------------|
   | Disabled      | Not available   |
   | Permissive    | Optional   |
   | Strict        | Required |


1.  Install the Spark package. This may take a few minutes.

    ```bash
    dcos package install spark
    ```
   
    **Tip:** Type `dcos spark` to view the Spark CLI options.

1.  Run the sample Spark Pi job for DC/OS.

    ```bash
    dcos spark run --submit-args="--class org.apache.spark.examples.SparkPi https://downloads.mesosphere.com/spark/assets/spark-examples_2.10-1.4.0-SNAPSHOT.jar 30"
    ```

1.  Run a Python Spark job.

    ```bash
    dcos spark run --submit-args="https://downloads.mesosphere.com/spark/examples/pi.py 30"
    ``` 

1.  Run an R Spark job.

    ```bash
    dcos spark run --submit-args="https://downloads.mesosphere.com/spark/examples/dataframe.R"
    ```

1.  View your job.

    - To view the status of your job, visit the Spark cluster dispatcher at `http://<dcos-url>/service/spark/` . 
    - To view the logs, click through to the details in the DC/OS GUI. 