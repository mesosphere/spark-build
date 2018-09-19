#!/bin/bash
set -x

export HADOOP_HOME=/usr/local/hadoop

# Create a user "alice" since Sentry authorization relies on the Linux user and group information
/usr/sbin/useradd alice

# Grant permissions to user “alice”
echo "Grant permissions to user alice ..."
kdestroy
kinit -k -t /usr/local/hadoop/etc/hadoop/hdfs.keytab hive/${HOSTNAME}@LOCAL
cat <<EOF >grant_alice.sql
CREATE ROLE test_role;
GRANT ROLE test_role to GROUP alice;
GRANT ROLE test_role to GROUP root;
GRANT ALL on DATABASE default to ROLE test_role WITH GRANT OPTION;
EOF
/usr/local/hive/bin/beeline -u "jdbc:hive2://localhost:10000/default;principal=hive/${HOSTNAME}@LOCAL" -f grant_alice.sql

# Log back in as hdfs
kdestroy
kinit -k -t /usr/local/hadoop/etc/hadoop/hdfs.keytab hdfs@LOCAL
