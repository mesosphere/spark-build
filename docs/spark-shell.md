<a name="pysparkshell"></a>
# Interactive Spark Shell

You can run Spark commands interactively in the Spark shell. The Spark shell is available
in either Scala or Python.

1. SSH into a node in the DC/OS cluster. [Learn how to SSH into your cluster and get the agent node ID](https://dcos.io/docs/latest/administration/access-node/sshcluster/).

        $ dcos node ssh --master-proxy --mesos-id=<agent-node-id>

1. Run a Spark Docker image.

        $ docker pull mesosphere/spark:1.0.4-2.0.1

        $ docker run -it --net=host mesosphere/spark:1.0.4-2.0.1 /bin/bash

1. Run the Scala Spark shell from within the Docker image.

        $ ./bin/spark-shell --master mesos://<internal-master-ip>:5050 --conf spark.mesos.executor.docker.image=mesosphere/spark:1.0.4-2.0.1 --conf spark.mesos.executor.home=/opt/spark/dist

    Or, run the Python Spark shell.

        $ ./bin/pyspark --master mesos://<internal-master-ip>:5050 --conf spark.mesos.executor.docker.image=mesosphere/spark:1.0.4-2.0.1 --conf spark.mesos.executor.home=/opt/spark/dist

1. Run Spark commands interactively.

    In the Scala shell:

        $ val textFile = sc.textFile("/opt/spark/dist/README.md")
        $ textFile.count()

    In the Python shell:

        $ textFile = sc.textFile("/opt/spark/dist/README.md")
        $ textFile.count()
