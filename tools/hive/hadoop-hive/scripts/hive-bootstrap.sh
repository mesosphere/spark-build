#!/bin/bash
set -x
#save all env vars .bashrc for ssh sessions
printenv | cat >> /root/.bashrc

# hadoop bootstrap
/etc/hadoop-bootstrap.sh -d

# restart postgresql
/etc/init.d/postgresql restart

# kinit for kerberos mode
if command -v kinit 2>/dev/null; then
    kinit -k -t /usr/local/hadoop/etc/hadoop/hdfs.keytab hdfs@LOCAL
fi

until hdfs dfs -ls /
do
    echo "waiting for hdfs to be ready"; sleep 10;
done

# create hdfs directories
$HADOOP_PREFIX/bin/hdfs dfs -mkdir -p /user/root
hdfs dfs -chown -R hdfs:supergroup /user

$HADOOP_PREFIX/bin/hdfs dfs -mkdir -p /apps/hive/warehouse
hdfs dfs -chown -R hive:supergroup /apps/hive
hdfs dfs -chmod 777 /apps/hive/warehouse

# altering the hive-site configuration
sed s/{{HOSTNAME}}/$HOSTNAME/ /usr/local/hive/conf/hive-site.xml.template > /usr/local/hive/conf/hive-site.xml
sed s/{{HOSTNAME}}/$HOSTNAME/ /opt/files/hive-site.xml.template > /opt/files/hive-site.xml

# start hive metastore server
$HIVE_HOME/bin/hive --service metastore &

sleep 20

# start hive server
$HIVE_HOME/bin/hive --service hiveserver2 &


if [[ $1 == "-bash" ]]; then
  /bin/bash
fi

if [[ $1 == "-d" ]]; then
  while true; do sleep 10000; done
fi
