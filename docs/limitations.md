---
layout: layout.pug
navigationTitle: 
excerpt:
title: Limitations
menuWeight: 135
featureMaturity:

---

*   Mesosphere does not provide support for Spark app development, such as writing a Python app to process data from
    Kafka or writing Scala code to process data from HDFS.

*   Spark jobs run in Docker containers. The first time you run a Spark job on a node, it might take longer than you
    expect because of the `docker pull`.

*   DC/OS Apache Spark only supports running the Spark shell from within a DC/OS cluster. See the Spark Shell section
    for more information. For interactive analytics, we recommend Zeppelin, which supports visualizations and dynamic
    dependency management.

*   With Spark SSL/TLS enabled, if you specify environment-based secrets with
    `spark.mesos.[driver|executor].secret.envkeys, the keystore and truststore secrets will also show up as
    environment-based secrets, due to the way secrets are implemented. You can ignore these extra environment variables.

*   Anyone who has access to the Spark (Dispatcher) service instance has access to all secrets available to it. Do not
    grant users access to the Spark Dispatcher instance unless they are also permitted to access all secrets available
    to the Spark Dispatcher instance.

*   When using Kerberos and HDFS, the Spark Driver generates delegation tokens and distributes them to it's Executors
    via RPC.  Authentication of the Executors with the Driver is done with a [shared
    secret][https://spark.apache.org/docs/latest/security.html#spark-security]. Without authentication, it is possible
    for executor containers to register with the Driver and retrieve the delegation tokens. To secure delegation token
    distribution, use the `--executor-auth-secret` option. 

*   Spark runs all of its components in Docker containers. Since the Docker image contains a full Linux userspace with
    its own `/etc/users` file, it is possible for the user `nobody` to have a different UID inside the
    container than on the host system. Although user `nobody` has UID 65534 by convention on many systems, this is not
    always the case. As Mesos does not perform UID mapping between Linux user namespaces, specifying a service user of
    `nobody` in this case will cause access failures when the container user attempts to open or execute a filesystem
    resource owned by a user with a different UID, preventing the service from launching. If the hosts in your cluster
    have a UID for `nobody` other than 65534, you will need to maintain the default user (`root`) to run DC/OS Spark
    successfully.
