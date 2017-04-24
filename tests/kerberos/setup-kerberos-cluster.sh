#!/bin/bash

# Test instructions:
#
# === Build HDFS
# 1. git clone git@github.com:mesosphere/dcos-commons.git
# 2. git checkout 1ca125bcf8147e2146a1162dadaa52892ad181de
# 2.1. Change "1.2.0-SNAPSHOT" in build.gradle to "1.2.0"
# 2.2. cd frameworks/hdfs
# 3. ./build.sh aws
# 4. dcos package repo add ...
#
# === Install KDC/HDFS
# 5. cd spark-build/tests/
# 6. ./setup-kerberos-cluster.sh
#
# === Write file to HDFS
# 7. <ssh to node running HDFS name-0-node>
# 8. <cd to name-0-node sandbox>
# 9. KRB5_CONFIG=jre1.8.0_112/lib/security/krb5.conf kinit -k -t hadoop-2.6.0-cdh5.9.1/
# 9. JAVA_HOME=jre1.8.0_112/ ./hadoop-2.6.0-cdh5.9.1/bin/hdfs dfs -copyFromLocal <file> hdfs:///
# 10. <exit to local>
#
# === Run Spark HDFSWordCount job
# 11. dcos node ssh --master-proxy --leader
# 12. wget http://api.hdfs.marathon.l4lb.thisdcos.directory/v1/endpoints/core-site.xml
# 13. wget http://api.hdfs.marathon.l4lb.thisdcos.directory/v1/endpoints/hdfs-site.xml
# 14. wget http://<S3_BUCKET>.s3.amazonaws.com/<S3_PATH>/keytabs.tar.gz
# 15. tar xvf keytabs.tar.gz
# 14. wget http://<S3_BUCKET>.s3.amazonaws.com/<S3_PATH>/krb5.conf
# 15. wget http://<S3_BUCKET>.s3.amazonaws.com/<S3_PATH>/dcos-spark-scala-tests-assembly-0.1-SNAPSHOT.jar
# 16. docker run --net=host -it -v /home/core/:/vol <DOCKER_IMAGE> /bin/bash
# 17. cp /vol/krb5.conf /etc/ && cp /vol/hdfs-site.xml /etc/hadoop/ && cp /vol/core-site.xml /etc/hadoop/ && kinit -k -t /vol/keytabs/hdfs.name-0-node.hdfs.mesos.keytab hdfs/name-0-node.hdfs.mesos@LOCAL
# 18. SPARK_USER=core ./bin/spark-submit --conf spark.mesos.executor.docker.forcePullImage=true --conf spark.driver.extraJavaOptions="-Dsun.security.krb5.debug=true" --conf spark.mesos.executor.docker.image=mgummelt/spark:test --conf spark.mesos.executor.home=/opt/spark/dist --master mesos://leader.mesos:5050 --class HDFSWordCount /vol/dcos-spark-scala-tests-assembly-0.1-SNAPSHOT.jar hdfs:///<file>

set -e -o pipefail

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
SPARK_BUILD_DIR="${DIR}/../../"

if [[ "${S3_BUCKET}" == "" ]]; then
    echo "Missing required env vars."
fi

echo "Adding kdc marathon app..."
dcos marathon app add kdc.json

echo "Waiting for app to run..."
while true; do
    TASKS_RUNNING=$(dcos marathon app list --json | jq ".[0].tasksRunning")
    if [[ ${TASKS_RUNNING} -eq 1 ]]; then
       break
    fi
done

SLAVE_ID=$(dcos task --json | jq -r ".[0].slave_id")
MASTER_PUBLIC_IP=$(curl --header "Authorization: token=$(dcos config show core.dcos_acs_token)" $(dcos config show core.dcos_url)/metadata | jq -r ".PUBLIC_IPV4")
SLAVE_HOSTNAME=$(dcos node --json | jq -r ".[] | select(.id==\"${SLAVE_ID}\") | .hostname")

echo "Getting docker container id..."
DOCKER_PS_CMD="docker ps | sed -n '2p' | cut -d\" \" -f1"
DOCKER_CONTAINER_ID=$(dcos node ssh --master-proxy --mesos-id=${SLAVE_ID} "${DOCKER_PS_CMD}")

echo "Adding Kerberos principals..."
dcos node ssh --master-proxy --mesos-id=${SLAVE_ID} "docker exec ${DOCKER_CONTAINER_ID} kadmin -l add --use-defaults --random-password hdfs/name-0-node.hdfs.mesos@LOCAL"
dcos node ssh --master-proxy --mesos-id=${SLAVE_ID} "docker exec ${DOCKER_CONTAINER_ID} kadmin -l add --use-defaults --random-password HTTP/name-0-node.hdfs.mesos@LOCAL"
dcos node ssh --master-proxy --mesos-id=${SLAVE_ID} "docker exec ${DOCKER_CONTAINER_ID} kadmin -l add --use-defaults --random-password hdfs/name-1-node.hdfs.mesos@LOCAL"
dcos node ssh --master-proxy --mesos-id=${SLAVE_ID} "docker exec ${DOCKER_CONTAINER_ID} kadmin -l add --use-defaults --random-password HTTP/name-1-node.hdfs.mesos@LOCAL"
dcos node ssh --master-proxy --mesos-id=${SLAVE_ID} "docker exec ${DOCKER_CONTAINER_ID} kadmin -l add --use-defaults --random-password hdfs/journal-0-node.hdfs.mesos@LOCAL"
dcos node ssh --master-proxy --mesos-id=${SLAVE_ID} "docker exec ${DOCKER_CONTAINER_ID} kadmin -l add --use-defaults --random-password HTTP/journal-0-node.hdfs.mesos@LOCAL"
dcos node ssh --master-proxy --mesos-id=${SLAVE_ID} "docker exec ${DOCKER_CONTAINER_ID} kadmin -l add --use-defaults --random-password hdfs/journal-1-node.hdfs.mesos@LOCAL"
dcos node ssh --master-proxy --mesos-id=${SLAVE_ID} "docker exec ${DOCKER_CONTAINER_ID} kadmin -l add --use-defaults --random-password HTTP/journal-1-node.hdfs.mesos@LOCAL"
dcos node ssh --master-proxy --mesos-id=${SLAVE_ID} "docker exec ${DOCKER_CONTAINER_ID} kadmin -l add --use-defaults --random-password hdfs/journal-2-node.hdfs.mesos@LOCAL"
dcos node ssh --master-proxy --mesos-id=${SLAVE_ID} "docker exec ${DOCKER_CONTAINER_ID} kadmin -l add --use-defaults --random-password HTTP/journal-2-node.hdfs.mesos@LOCAL"
dcos node ssh --master-proxy --mesos-id=${SLAVE_ID} "docker exec ${DOCKER_CONTAINER_ID} kadmin -l add --use-defaults --random-password hdfs/data-0-node.hdfs.mesos@LOCAL"
dcos node ssh --master-proxy --mesos-id=${SLAVE_ID} "docker exec ${DOCKER_CONTAINER_ID} kadmin -l add --use-defaults --random-password HTTP/data-0-node.hdfs.mesos@LOCAL"
dcos node ssh --master-proxy --mesos-id=${SLAVE_ID} "docker exec ${DOCKER_CONTAINER_ID} kadmin -l add --use-defaults --random-password hdfs/data-1-node.hdfs.mesos@LOCAL"
dcos node ssh --master-proxy --mesos-id=${SLAVE_ID} "docker exec ${DOCKER_CONTAINER_ID} kadmin -l add --use-defaults --random-password HTTP/data-1-node.hdfs.mesos@LOCAL"
dcos node ssh --master-proxy --mesos-id=${SLAVE_ID} "docker exec ${DOCKER_CONTAINER_ID} kadmin -l add --use-defaults --random-password hdfs/data-2-node.hdfs.mesos@LOCAL"
dcos node ssh --master-proxy --mesos-id=${SLAVE_ID} "docker exec ${DOCKER_CONTAINER_ID} kadmin -l add --use-defaults --random-password HTTP/data-2-node.hdfs.mesos@LOCAL"
dcos node ssh --master-proxy --mesos-id=${SLAVE_ID} "docker exec ${DOCKER_CONTAINER_ID} kadmin -l add --use-defaults --random-password hdfs/zkfc-0-node.hdfs.mesos@LOCAL"
dcos node ssh --master-proxy --mesos-id=${SLAVE_ID} "docker exec ${DOCKER_CONTAINER_ID} kadmin -l add --use-defaults --random-password hdfs/zkfc-1-node.hdfs.mesos@LOCAL"

echo "Writing keytab files..."
dcos node ssh --master-proxy --mesos-id=${SLAVE_ID} "docker exec ${DOCKER_CONTAINER_ID} kadmin -l ext -k hdfs.name-0-node.hdfs.mesos.keytab hdfs/name-0-node.hdfs.mesos@LOCAL HTTP/name-0-node.hdfs.mesos@LOCAL"
dcos node ssh --master-proxy --mesos-id=${SLAVE_ID} "docker exec ${DOCKER_CONTAINER_ID} kadmin -l ext -k hdfs.name-1-node.hdfs.mesos.keytab hdfs/name-1-node.hdfs.mesos@LOCAL HTTP/name-1-node.hdfs.mesos@LOCAL"
dcos node ssh --master-proxy --mesos-id=${SLAVE_ID} "docker exec ${DOCKER_CONTAINER_ID} kadmin -l ext -k hdfs.journal-0-node.hdfs.mesos.keytab hdfs/journal-0-node.hdfs.mesos@LOCAL HTTP/journal-0-node.hdfs.mesos@LOCAL"
dcos node ssh --master-proxy --mesos-id=${SLAVE_ID} "docker exec ${DOCKER_CONTAINER_ID} kadmin -l ext -k hdfs.journal-1-node.hdfs.mesos.keytab hdfs/journal-1-node.hdfs.mesos@LOCAL HTTP/journal-1-node.hdfs.mesos@LOCAL"
dcos node ssh --master-proxy --mesos-id=${SLAVE_ID} "docker exec ${DOCKER_CONTAINER_ID} kadmin -l ext -k hdfs.journal-2-node.hdfs.mesos.keytab hdfs/journal-2-node.hdfs.mesos@LOCAL HTTP/journal-2-node.hdfs.mesos@LOCAL"
dcos node ssh --master-proxy --mesos-id=${SLAVE_ID} "docker exec ${DOCKER_CONTAINER_ID} kadmin -l ext -k hdfs.data-0-node.hdfs.mesos.keytab hdfs/data-0-node.hdfs.mesos@LOCAL HTTP/data-0-node.hdfs.mesos@LOCAL"
dcos node ssh --master-proxy --mesos-id=${SLAVE_ID} "docker exec ${DOCKER_CONTAINER_ID} kadmin -l ext -k hdfs.data-1-node.hdfs.mesos.keytab hdfs/data-1-node.hdfs.mesos@LOCAL HTTP/data-1-node.hdfs.mesos@LOCAL"
dcos node ssh --master-proxy --mesos-id=${SLAVE_ID} "docker exec ${DOCKER_CONTAINER_ID} kadmin -l ext -k hdfs.data-2-node.hdfs.mesos.keytab hdfs/data-2-node.hdfs.mesos@LOCAL HTTP/data-2-node.hdfs.mesos@LOCAL"
dcos node ssh --master-proxy --mesos-id=${SLAVE_ID} "docker exec ${DOCKER_CONTAINER_ID} kadmin -l ext -k hdfs.zkfc-0-node.hdfs.mesos.keytab hdfs/zkfc-0-node.hdfs.mesos@LOCAL"
dcos node ssh --master-proxy --mesos-id=${SLAVE_ID} "docker exec ${DOCKER_CONTAINER_ID} kadmin -l ext -k hdfs.zkfc-1-node.hdfs.mesos.keytab hdfs/zkfc-1-node.hdfs.mesos@LOCAL"

echo "Moving keytabs into a keytabs/ directory"
dcos node ssh --master-proxy --mesos-id=${SLAVE_ID} "docker exec ${DOCKER_CONTAINER_ID} mkdir -p keytabs"
dcos node ssh --master-proxy --mesos-id=${SLAVE_ID} "docker exec ${DOCKER_CONTAINER_ID} mv hdfs.name-0-node.hdfs.mesos.keytab keytabs/"
dcos node ssh --master-proxy --mesos-id=${SLAVE_ID} "docker exec ${DOCKER_CONTAINER_ID} mv hdfs.name-1-node.hdfs.mesos.keytab keytabs/"
dcos node ssh --master-proxy --mesos-id=${SLAVE_ID} "docker exec ${DOCKER_CONTAINER_ID} mv hdfs.journal-0-node.hdfs.mesos.keytab keytabs/"
dcos node ssh --master-proxy --mesos-id=${SLAVE_ID} "docker exec ${DOCKER_CONTAINER_ID} mv hdfs.journal-1-node.hdfs.mesos.keytab keytabs/"
dcos node ssh --master-proxy --mesos-id=${SLAVE_ID} "docker exec ${DOCKER_CONTAINER_ID} mv hdfs.journal-2-node.hdfs.mesos.keytab keytabs/"
dcos node ssh --master-proxy --mesos-id=${SLAVE_ID} "docker exec ${DOCKER_CONTAINER_ID} mv hdfs.data-0-node.hdfs.mesos.keytab keytabs/"
dcos node ssh --master-proxy --mesos-id=${SLAVE_ID} "docker exec ${DOCKER_CONTAINER_ID} mv hdfs.data-1-node.hdfs.mesos.keytab keytabs/"
dcos node ssh --master-proxy --mesos-id=${SLAVE_ID} "docker exec ${DOCKER_CONTAINER_ID} mv hdfs.data-2-node.hdfs.mesos.keytab keytabs/"
dcos node ssh --master-proxy --mesos-id=${SLAVE_ID} "docker exec ${DOCKER_CONTAINER_ID} mv hdfs.zkfc-0-node.hdfs.mesos.keytab keytabs/"
dcos node ssh --master-proxy --mesos-id=${SLAVE_ID} "docker exec ${DOCKER_CONTAINER_ID} mv hdfs.zkfc-1-node.hdfs.mesos.keytab keytabs/"
dcos node ssh --master-proxy --mesos-id=${SLAVE_ID} "docker exec ${DOCKER_CONTAINER_ID} tar czf keytabs.tar.gz keytabs"

echo "Copying keytabs.tar.gz to the current working directory..."
dcos node ssh --master-proxy --mesos-id=${SLAVE_ID} "docker cp ${DOCKER_CONTAINER_ID}:/keytabs.tar.gz /home/core/keytabs.tar.gz"
dcos node ssh --master-proxy --leader "scp core@${SLAVE_HOSTNAME}:/home/core/keytabs.tar.gz /home/core/keytabs.tar.gz"
scp core@${MASTER_PUBLIC_IP}:/home/core/keytabs.tar.gz .

echo "Uploading keytabs.tar.gz to s3://${S3_BUCKET}/${S3_PATH}"
aws s3 cp ./keytabs.tar.gz s3://${S3_BUCKET}/${S3_PATH} --acl public-read

echo "Uploading krb5.conf to s3://${S3_BUCKET}/${S3_PATH}"
aws s3 cp ./krb5.conf s3://${S3_BUCKET}/${S3_PATH} --acl public-read

echo "Uploading spark job"
(cd "${SPARK_BUILD_DIR}/tests/jobs/scala" && sbt assembly)
aws s3 cp "${SPARK_BUILD_DIR}/tests/jobs/scala/target/scala-2.11/dcos-spark-scala-tests-assembly-0.1-SNAPSHOT.jar" s3://${S3_BUCKET}/${S3_PATH} --acl public-read

cat <<EOF > /tmp/hdfs-kerberos-options.json
{
  "service": {
    "user": "core",
    "kerberos": {
      "enabled": true,
      "keytabs_uri": "https://${S3_BUCKET}.s3.amazonaws.com/${S3_PATH}keytabs.tar.gz",
      "krb5_conf_uri": "https://${S3_BUCKET}.s3.amazonaws.com/${S3_PATH}krb5.conf"
    }
  }
}
EOF

echo "Installing Kerberized HDFS..."
dcos package install --yes hdfs --options=/tmp/hdfs-kerberos-options.json
