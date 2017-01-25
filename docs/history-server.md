---
post_title: History Server
menu_order: 30
enterprise: 'no'
---

DC/OS Spark includes the [Spark history server][3]. Because the history
server requires HDFS, you must explicitly enable it.

1.  Install HDFS first:

        $ dcos package install hdfs

    **Note:** HDFS requires 5 private nodes.

1.  Create a history HDFS directory (default is `/history`). [SSH into
your cluster][10] and run:

        $ hdfs dfs -mkdir /history

1.  Enable the history server when you install Spark. Create a JSON
configuration file. Here we call it `options.json`:

        {
           "history-server": {
             "enabled": true
           }
        }

1.  Install Spark:

        $ dcos package install spark --options=options.json

1.  Run jobs with the event log enabled:

        $ dcos spark run --submit-args="-Dspark.eventLog.enabled=true -Dspark.eventLog.dir=hdfs://hdfs/history ... --class MySampleClass  http://external.website/mysparkapp.jar"

1.  Visit your job in the dispatcher at
`http://<dcos_url>/service/spark/Dispatcher/`. It will include a link
to the history server entry for that job.

 [3]: http://spark.apache.org/docs/latest/monitoring.html#viewing-after-the-fact
 [10]: https://docs.mesosphere.com/1.9/administration/access-node/sshcluster/
