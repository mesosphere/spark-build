# Cloudera Hadoop and Hive Docker Image with Kerberos


This is a Hadoop Docker image running CDH5 versions of Hadoop and Hive, all in one container. There is a separate Kerberos image in which Hadoop and Hive use Kerberos for authentication. Adapted from https://github.com/tilakpatidar/cdh5_hive_postgres and based on Ubuntu (trusty).

Postgres is also installed so that Hive can use it for its Metastore backend and run in remote mode.

## Current Version
* Hadoop 2.6.0
* Hive 1.1.0

## Dependencies
The Kerberos image assumes that a KDC has been launched by the dcos-commons kdc.py script.

## Build the image

Build the Hadoop + Hive image:
```
cd hadoop-hive
docker build -t cdh5-hive .
```

Build the Kerberized Hadoop + Hive image:
```
cd ../kerberos
docker build -t cdh5-hive-kerberos .
```

## Run the Hive image interactively
```
docker run -it cdh5-hive:latest /etc/hive-bootstrap.sh -bash
```

## Run the Kerberized Hive image in DC/OS
First, deploy a KDC via the dcos-commons kdc.py utility. See [the kdc README](https://github.com/mesosphere/dcos-commons/tree/master/tools/kdc) for details.

From the dcos-commons repo:
```
PYTHONPATH=testing ./tools/kdc/kdc.py deploy principals.txt
```

At a minimum, `principals.txt` should include the following principals (for the Hadoop container hostname, pick any private agent in the cluster):

```
hdfs/<hostname of Hadoop container>@LOCAL
HTTP/<hostname of Hadoop container>@LOCAL
yarn/<hostname of Hadoop container>@LOCAL
hive/<hostname of Hadoop container>@LOCAL
```

Deploy the Kerberized Hadoop / Hive container via Marathon. (Update the Marathon config's `constraint` field first with the host selected above.)

```
dcos marathon app add kerberos/marathon/hdfs-hive-kerberos.json
```
