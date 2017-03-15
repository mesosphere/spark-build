---
post_title: History Server
menu_order: 30
enterprise: 'no'
---

DC/OS Spark includes The [Spark History Server][3]. Because the history
server requires HDFS, you must explicitly enable it.

1.  Install HDFS:

        $ dcos package install hdfs

    **Note:** HDFS requires 5 private nodes.

1.  Create a history HDFS directory (default is `/history`). [SSH into
your cluster][10] and run:

        $ hdfs dfs -mkdir /history

1. Create `spark-history-options.json`:

        {
          "hdfs-config-url": "http://api.hdfs.marathon.l4lb.thisdcos.directory/v1/endpoints"
        }

1. Install The Spark History Server:

        $ dcos package install spark-history --options=spark-history-options.json

1. Create `spark-dispatcher-options.json`;

        {
          "service": {
            "spark-history-server-url": "http://<dcos_url>/service/spark-history
          },
          "hdfs": {
            "config-url": "http://api.hdfs.marathon.l4lb.thisdcos.directory/v1/endpoints"
          }
        }

1.  Install The Spark Dispatcher:

        $ dcos package install spark --options=spark-dispatcher-options.json

1.  Run jobs with the event log enabled:

        $ dcos spark run --submit-args="-Dspark.eventLog.enabled=true -Dspark.eventLog.dir=hdfs://hdfs/history ... --class MySampleClass  http://external.website/mysparkapp.jar"

1.  Visit your job in the dispatcher at
`http://<dcos_url>/service/spark/`. It will include a link to the
history server entry for that job.

 [3]: http://spark.apache.org/docs/latest/monitoring.html#viewing-after-the-fact
 [10]: https://docs.mesosphere.com/1.9/administration/access-node/sshcluster/
