---
layout: layout.pug
navigationTitle: 
excerpt:
title: Troubleshooting
menuWeight: 125

---

# Dispatcher

*   The Mesos cluster dispatcher is responsible for queuing, tracking, and supervising drivers. Potential problems may
    arise if the dispatcher does not receive the resources offers you expect from Mesos, or if driver submission is
    failing. To debug this class of issue, visit the Mesos UI at `http://<dcos-url>/mesos/` and navigate to the sandbox
    for the dispatcher.

*   Spark has an internal mechanism for detecting the IP of the host. However, in some cases it is not sufficient for 
    a proper hostname resolution e.g. when hostname resolves to multiple addresses or when Spark runs in virtual network.
    For this reason DC/OS-specific `bootstrap` utility is used to detect the IP, which may allow the initialization of 
    the Spark service to complete.

# Jobs

*   DC/OS Apache Spark jobs are submitted through the dispatcher, which displays Spark properties and job state. Start
    here to verify that the job is configured as you expect.

*   The dispatcher further provides a link to the job's entry in the history server, which displays the Spark Job UI.
    This UI shows the for the job. Go here to debug issues with scheduling and performance.

*   Jobs themselves log output to their sandbox, which you can access through the Mesos UI. The Spark logs will be sent
    to `stderr`, while any output you write in your job will be sent to `stdout`.

*   DC/OS Apache Spark supports virtual/overlay networks and once dispatcher deployed it will launch all submitted jobs 
    in  same network it has been launched itself. To override network setting for a specific job a user needs to set the
    following properties:
    ```
    --conf spark.mesos.network.name=<network_name>
    --conf spark.mesos.driverEnv.VIRTUAL_NETWORK_ENABLED=true
    --conf spark.executorEnv.VIRTUAL_NETWORK_ENABLED=true
    ```
    This enables bind address discovery for driver and executors. Setting `VIRTUAL_NETWORK_ENABLED` flags is only needed
    when using Docker containerizer.

# CLI

The Spark CLI is integrated with the dispatcher so that they always use the same version of Spark, and so that certain
defaults are honored. To debug issues with their communication, run your jobs with the `--verbose` flag.

# HDFS Kerberos

To debug authentication in a Spark job, enable Java security debug output:

    dcos spark run --submit-args="--conf sun.security.krb5.debug=true..."
