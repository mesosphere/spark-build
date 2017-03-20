---
post_title: Troubleshooting
menu_order: 120
enterprise: 'no'
---

# Dispatcher

The Mesos cluster dispatcher is responsible for queuing, tracking, and
supervising drivers. Potential problems may arise if the dispatcher
does not receive the resources offers you expect from Mesos, or if
driver submission is failing. To debug this class of issue, visit the
Mesos UI at `http://<dcos-url>/mesos/` and navigate to the sandbox for
the dispatcher.

# Jobs

*   DC/OS Spark jobs are submitted through the dispatcher, which
displays Spark properties and job state. Start here to verify that the
job is configured as you expect.

*   The dispatcher further provides a link to the job's entry in the
history server, which displays the Spark Job UI. This UI shows the for
the job. Go here to debug issues with scheduling and performance.

*   Jobs themselves log output to their sandbox, which you can access
through the Mesos UI. The Spark logs will be sent to `stderr`, while
any output you write in your job will be sent to `stdout`.

# CLI

The Spark CLI is integrated with the dispatcher so that they always
use the same version of Spark, and so that certain defaults are
honored. To debug issues with their communication, run your jobs with
the `--verbose` flag.

# HDFS Kerberos

To debug authentication in a Spark job, enable Java security debug
output:

    $ dcos spark run --submit-args="--conf sun.security.krb5.debug=true..."
