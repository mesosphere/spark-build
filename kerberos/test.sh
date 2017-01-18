#!/bin/bash -ex

make deploy

rm -rf build
mkdir build

function wait_for_healthy_app () {
	echo -n "Waiting for $1 to be healthy"
	while ! dcos marathon task list $1 | egrep -q "$1 *True"; do
		echo -n "."
		sleep 5
	done
	echo
}

wait_for_healthy_app /kdc

echo -n "Waiting for hdfs@LOCAL keytab"
KDC_TASK=$(dcos marathon task list /kdc | grep /kdc | awk '{print $5}')
while ! dcos task log ${KDC_TASK} stdout | grep -q "tester.keytab:"; do
	echo -n "."
	sleep 5
done

HDFS_KEYTAB=$(dcos task log ${KDC_TASK} stdout | grep "hdfs.keytab:" | awk -F": " '{print $2}')
TESTER_KEYTAB=$(dcos task log ${KDC_TASK} stdout | grep "tester.keytab:" | awk -F": " '{print $2}')

function distribute_file() {
	FROM="$1"
	TO="$2"
	DCOS_IP=$(curl -f $(dcos config show core.dcos_url)/metadata | jq -r .PUBLIC_IPV4)
	for NODE in $(dcos node --json | jq -r ".[].hostname"); do
		ssh -A -t -oStrictHostKeyChecking=no core@${DCOS_IP} ssh -oStrictHostKeyChecking=no core@${NODE} "true; sudo bash -c \"cat > ${TO}\"" <"${FROM}"
	done
}

echo "$HDFS_KEYTAB" > build/hdfs.keytab
distribute_file build/hdfs.keytab /tmp/hdfs.keytab

sed -e "s=HOST_NAME=kdc.marathon.mesos:88=g" \
	-e "s=DOMAIN_NAME=local=g" \
	-e "s=REALM_NAME=LOCAL=g" \
	krb5.conf.template > build/krb5.conf
distribute_file build/krb5.conf /etc/krb5.conf

MESOS_SITE_PATH=hdfs-mesos-0.1.8/etc/hadoop/hdfs-site.xml
HDFS_URL=$(curl -f https://raw.githubusercontent.com/mesosphere/universe/version-2.x/repo/packages/H/hdfs/1/resource.json | jq -r '.assets.uris."hdfs-mesos-0-1-8-tgz"')
curl -f "${HDFS_URL}" | tar -xvz -C build/ -f -
(
	grep -v "</configuration>" build/${MESOS_SITE_PATH}
	cat kerberos-site.xml
	echo "</configuration>"
) > build/hdfs-site.xml
cp build/hdfs-site.xml build/${MESOS_SITE_PATH}

cd build
tar -czf hdfs-mesos.tgz hdfs-mesos-0.1.8
s3cmd put -P --multipart-chunk-size-mb=5 --continue-put hdfs-mesos.tgz s3://spark-ssl/
cd -

cat >build/options.json <<EOF
{
	"hdfs": {
		"custom-mesos-hdfs-tgz": "http://spark-ssl.s3.amazonaws.com/hdfs-mesos.tgz"
	}
}
EOF

dcos package uninstall hdfs || echo "HDFS package was not installed"
dcos package install --yes --options=build/options.json hdfs

wait_for_healthy_app /hdfs

