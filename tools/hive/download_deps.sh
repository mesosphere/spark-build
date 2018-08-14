#!/usr/bin/env bash
set -x
set -e
source ubuntu/base.env

mkdir hadoop-2.6.0/deps
mkdir hive_pg/deps

#download cdh
echo "wget http://archive.cloudera.com/cdh${CDH_VERSION}/cdh/${CDH_VERSION}/hadoop-${HADOOP_VERSION}-cdh${CDH_EXACT_VERSION}.tar.gz | tar -xz -C /usr/local/"
wget http://archive.cloudera.com/cdh${CDH_VERSION}/cdh/${CDH_VERSION}/hadoop-${HADOOP_VERSION}-cdh${CDH_EXACT_VERSION}.tar.gz
mv hadoop-${HADOOP_VERSION}-cdh${CDH_EXACT_VERSION}.tar.gz hadoop-2.6.0/deps/

#download native hadoop libs
echo "wget http://dl.bintray.com/sequenceiq/sequenceiq-bin/hadoop-native-64-2.6.0.tar"
wget http://dl.bintray.com/sequenceiq/sequenceiq-bin/hadoop-native-64-2.6.0.tar
mv hadoop-native-64-2.6.0.tar hadoop-2.6.0/deps/

echo "wget http://archive.cloudera.com/cdh${CDH_VERSION}/cdh/${CDH_VERSION}/hive-1.1.0-cdh${CDH_EXACT_VERSION}.tar.gz"
wget http://archive.cloudera.com/cdh${CDH_VERSION}/cdh/${CDH_VERSION}/hive-1.1.0-cdh${CDH_EXACT_VERSION}.tar.gz
mv hive-1.1.0-cdh${CDH_EXACT_VERSION}.tar.gz hive_pg/deps/
