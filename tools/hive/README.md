# Cloudera Hadoop and Hive Docker Image with Kerberos


This is a Hadoop Docker image running CDH5 versions of Hadoop and Hive, all in one container. There is a separate Kerberos image in which Hadoop and Hive use Kerberos for authentication. Adapted from https://github.com/tilakpatidar/cdh5_hive_postgres and based on Ubuntu (trusty).

## Current Version
* Hadoop 2.6.0

## Dependencies
The Kerberos image assumes that a KDC has been launched by the dcos-commons kdc.py script.

## Build the image
Download dependencies:
```
./download_deps.sh
```

Build the Ubuntu base image:
```
cd ubuntu
docker build -t cdh5-ubuntu .
```

Build the Hadoop image:
```
cd ../hadoop-2.6.0
docker build -t cdh5-hadoop .
```

Build the Hadoop + Hive image:
```
cd ../hive_pg
docker build -t cdh5-hive .
```

Build the Kerberized Hadoop + Hive image:
```
cd ../kerberos
docker build -t cdh5-hive-kerberos .
```

## Run the Kerberos image in DC/OS
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
