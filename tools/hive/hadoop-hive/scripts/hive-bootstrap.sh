#!/bin/bash
set -x
#save all env vars .bashrc for ssh sessions
printenv | cat >> /root/.bashrc

# hadoop bootstrap
/etc/hadoop-bootstrap.sh

# init and start sentry
SENTRY_CONF_TEMPLATE=$SENTRY_HOME/conf/sentry-site.xml.template
SENTRY_CONF_FILE=$SENTRY_HOME/conf/sentry-site.xml
if [ -f "$SENTRY_CONF_TEMPLATE" ]; then
    sed s/{{HOSTNAME}}/$HOSTNAME/ $SENTRY_HOME/conf/sentry-site.xml.template > $SENTRY_HOME/conf/sentry-site.xml
    sed s/{{HOSTNAME}}/$HOSTNAME/ $HIVE_CONF/sentry-site.xml.template > $HIVE_CONF/sentry-site.xml
    $SENTRY_HOME/bin/sentry --command schema-tool --conffile $SENTRY_CONF_FILE --dbType derby --initSchema
    $SENTRY_HOME/bin/sentry --command service --conffile $SENTRY_CONF_FILE &
fi

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

# create hive user
useradd hive

# create hdfs directories
hdfs dfs -mkdir -p /user/root
hdfs dfs -chown -R hdfs:supergroup /user

hdfs dfs -mkdir -p /apps/hive/warehouse
hdfs dfs -chown -R hive:supergroup /apps/hive
hdfs dfs -chmod 777 /apps/hive/warehouse

hdfs dfs -mkdir -p /tmp/hive
hdfs dfs -chmod 777 /tmp/hive

# altering the hive-site configuration
sed s/{{HOSTNAME}}/$HOSTNAME/ $HIVE_CONF/hive-site.xml.template > $HIVE_CONF/hive-site.xml
sed s/{{HOSTNAME}}/$HOSTNAME/ /opt/files/hive-site.xml.template > /opt/files/hive-site.xml

# start hive metastore server
$HIVE_HOME/bin/hive --service metastore &

sleep 20

# start hive server
$HIVE_HOME/bin/hive --service hiveserver2 &


if [[ $1 == "-bash" ]]; then
  /bin/bash
elif [[ $1 == "-d" ]]; then
  while true; do sleep 10000; done
else
  echo "Unknown argument $1"
  echo "Usage: ./hive-bootstrap.sh [ -bash | -d ]"
fi
