---
layout: layout.pug
navigationTitle: 
excerpt:
title: Spark Quickstart
menuWeight: 10
featureMaturity:

---

This tutorial will get you up and running in minutes with Spark. You will install the DC/OS Apache Spark service.

**Prerequisites:**

-  [DC/OS and DC/OS CLI installed](https://docs.mesosphere.com/1.9/installing/) with a minimum of three agent nodes with eight GB of memory and ten GB of disk available on each agent.
-  Depending on your [security mode](https://docs.mesosphere.com/1.9/overview/security/security-modes/), Spark requires service authentication for access to DC/OS. For more information, see [Configuring DC/OS Access for Spark](https://docs.mesosphere.com/services/spark/spark-auth/).

   | Security mode | Service Account |
   |---------------|-----------------------|
   | Disabled      | Not available   |
   | Permissive    | Optional   |
   | Strict        | Required |


1.  Install the Spark package. This may take a few minutes. This installs the Spark DC/OS service, Spark CLI, dispatcher, and, optionally, the history server. See [Custom Installation](/services/spark/v1.0.9-2.1.0-1/install/#custom) to install the history server.

    ```bash
    dcos package install spark
    ```
    
    Your output should resemble:
    
    ```bash
    Installing Marathon app for package [spark] version [1.1.0-2.1.1]
    Installing CLI subcommand for package [spark] version [1.1.0-2.1.1]
    New command available: dcos spark
    DC/OS Spark is being installed!
    
    	Documentation: https://docs.mesosphere.com/services/spark/
    	Issues: https://docs.mesosphere.com/support/
    ```
   
    **Tips:** 
    
    -  You can view the status of your Spark installation from the DC/OS GUI **Services** tab.
       
       ![Verify spark installation](/img/spark-gui-install.png)
       
    -  Type `dcos spark` to view the Spark CLI options.
    -  You can install the Spark CLI with this command:
     
       ```bash
       dcos package install spark --cli
       ```

1.  Run the sample SparkPi jar for DC/OS. This runs a Spark job which calculates the value of Pi. You can view the example source [here](https://downloads.mesosphere.com/spark/assets/spark-examples_2.11-2.0.1.jar). 

    1.  Run this command: 

        ```bash
        dcos spark run --submit-args="--class org.apache.spark.examples.SparkPi https://downloads.mesosphere.com/spark/assets/spark-examples_2.11-2.0.1.jar 30"
        ```
        
        Your output should resemble:
        
        ```bash
        2017/08/24 15:42:07 Using docker image mesosphere/spark:2.0.0-2.2.0-1-hadoop-2.6 for drivers
        2017/08/24 15:42:07 Pulling image mesosphere/spark:2.0.0-2.2.0-1-hadoop-2.6 for executors, by default. To bypass set spark.mesos.executor.docker.forcePullImage=false
        2017/08/24 15:42:07 Setting DCOS_SPACE to /spark
        Run job succeeded. Submission id: driver-20170824224209-0001
        ```
        
    1.  View the standard output from your job:
    
        ```bash
        dcos spark log driver-20170824224209-0001
        ```
        
        Your output should resemble:
        
        ```bash
        Pi is roughly 3.141853333333333
        ```

1.  Run a Python SparkPi jar. This runs a Python Spark job which calculates the value of Pi. You can view the example source [here](https://downloads.mesosphere.com/spark/examples/pi.py). 

    1.  Run this command:
    
        ```bash
        dcos spark run --submit-args="https://downloads.mesosphere.com/spark/examples/pi.py 30"
        ``` 
        
        Your output should resemble:
        
        ```bash
        2017/08/24 15:44:20 Parsing application as Python job
        2017/08/24 15:44:23 Using docker image mesosphere/spark:2.0.0-2.2.0-1-hadoop-2.6 for drivers
        2017/08/24 15:44:23 Pulling image mesosphere/spark:2.0.0-2.2.0-1-hadoop-2.6 for executors, by default. To bypass set spark.mesos.executor.docker.forcePullImage=false
        2017/08/24 15:44:23 Setting DCOS_SPACE to /spark
        Run job succeeded. Submission id: driver-20170824224423-0002
        ```
        
    1.  View the standard output from your job:
    
        ```bash
        dcos task log --completed driver-20170616213917-0002
        ```
        
        Your output should resemble:
        
        ```bash
        Pi is roughly 3.142715
        ```

1.  Run an R job. You can view the example source [here](https://downloads.mesosphere.com/spark/examples/dataframe.R). 

    1.  Run this command:
    
        ```bash
        dcos spark run --submit-args="https://downloads.mesosphere.com/spark/examples/dataframe.R"
        ```
        
        Your output should resemble:
        
        ```bash
        2017/08/24 15:45:21 Parsing application as R job
        2017/08/24 15:45:23 Using docker image mesosphere/spark:2.0.0-2.2.0-1-hadoop-2.6 for drivers
        2017/08/24 15:45:23 Pulling image mesosphere/spark:2.0.0-2.2.0-1-hadoop-2.6 for executors, by default. To bypass set spark.mesos.executor.docker.forcePullImage=false
        2017/08/24 15:45:23 Setting DCOS_SPACE to /spark
        Run job succeeded. Submission id: driver-20170824224524-0003
        ```
        
    1.  View the standard output from your job:
    
        ```bash
        dcos spark log --lines_count=10 driver-20170824224524-0003
        ```
        
        Your output should resemble:
        
        ```bash
        In Filter(nzchar, unlist(strsplit(input, ",|\\s"))) :
          bytecode version mismatch; using eval
        root
         |-- name: string (nullable = true)
         |-- age: double (nullable = true)
        root
         |-- age: long (nullable = true)
         |-- name: string (nullable = true)
            name
        1 Justin        
        ```

## Next Steps

- To view the status of your job, run the `dcos spark webui` command and then visit the Spark cluster dispatcher UI at `http://<dcos-url>/service/spark/` .
- To view the logs, the Mesos UI at `http://<your-master-ip>/mesos`.
- To view details about your Spark job, run the `dcos task log --completed <submissionId>` command.