#!/bin/bash
set -x

# used by Hadoop
/usr/sbin/sshd

: ${HADOOP_PREFIX:=/usr/local/hadoop}

$HADOOP_PREFIX/etc/hadoop/hadoop-env.sh

rm /tmp/*.pid

# templating of config files
sed s/{{HOSTNAME}}/$HOSTNAME/ /usr/local/hadoop/etc/hadoop/core-site.xml.template > /usr/local/hadoop/etc/hadoop/core-site.xml
sed s/{{HOSTNAME}}/$HOSTNAME/ /usr/local/hadoop/etc/hadoop/yarn-site.xml.template > /usr/local/hadoop/etc/hadoop/yarn-site.xml
sed s/{{HOSTNAME}}/$HOSTNAME/ /usr/local/hadoop/etc/hadoop/hdfs-site.xml.template > /usr/local/hadoop/etc/hadoop/hdfs-site.xml

# format namenode
$HADOOP_PREFIX/bin/hdfs namenode -format

# start hdfs and yarn
$HADOOP_PREFIX/sbin/start-dfs.sh
$HADOOP_PREFIX/sbin/start-yarn.sh

if [[ $1 == "-bash" ]]; then
  /bin/bash
fi
