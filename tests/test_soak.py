import os
import logging
import pytest

import shakedown

import sdk_cmd
import sdk_jobs

import spark_utils as utils
from tests.test_kafka import KAFKA_PACKAGE_NAME, test_pipeline

LOGGER = logging.getLogger(__name__)

SOAK_SPARK_SERVICE_NAME = os.getenv('SOAK_SPARK_SERVICE_NAME', 'spark')

SOAK_HDFS_SERVICE_NAME = os.getenv('SOAK_HDFS_SERVICE_NAME', 'hdfs')
HDFS_PRINCIPAL="hdfs/name-0-node.{}.autoip.dcos.thisdcos.directory@LOCAL".format(
    SOAK_HDFS_SERVICE_NAME.replace("/", ""))

HDFSCLIENT_KERBEROS_SERVICE_NAME = os.getenv('HDFSCLIENT_KERBEROS_SERVICE_NAME', 'hdfsclient-kerberos')
HDFSCLIENT_KERBEROS_TASK = HDFSCLIENT_KERBEROS_SERVICE_NAME.replace("/", "_")

HDFS_KERBEROS_ENABLED=os.getenv('HDFS_KERBEROS_ENABLED', 'true').lower() != 'false'

HDFS_KEYTAB_SECRET=os.getenv('HDFS_KEYTAB_SECRET', '__dcos_base64__hdfs_keytab')
KAFKA_KEYTAB_SECRET = os.getenv("KAFKA_KEYTAB_SECRET", "__dcos_base64__kafka_keytab")

DCOS_UID = os.getenv('DCOS_UID')
DCOS_PASSWORD = os.getenv('DCOS_PASSWORD')

KAFKA_JAAS_URI = "https://s3-us-west-2.amazonaws.com/infinity-artifacts/soak/spark/spark-kafka-client-jaas.conf"
JAR_URI = "https://s3-us-west-2.amazonaws.com/infinity-artifacts/soak/spark/dcos-spark-scala-tests-assembly-0.2-SNAPSHOT.jar"
TERASORT_JAR='https://downloads.mesosphere.io/spark/examples/spark-terasort-1.1-jar-with-dependencies_2.11.jar'
TERASORT_MAX_CORES=6

KERBEROS_ARGS = ["--kerberos-principal", HDFS_PRINCIPAL,
                 "--keytab-secret-path", "/{}".format(HDFS_KEYTAB_SECRET),
                 "--conf", "spark.mesos.driverEnv.SPARK_USER=root"] # run as root on soak (centos)
COMMON_ARGS = ["--conf", "spark.driver.port=1024",
               "--conf", "spark.cores.max={}".format(TERASORT_MAX_CORES)]
if HDFS_KERBEROS_ENABLED:
    COMMON_ARGS += KERBEROS_ARGS

TERASORT_DELETE_JOB = {
    "description": "Job that deletes Terasort files from HDFS",
    "id": "hdfs-delete-terasort-files",
    "run": {
        "cpus": 0.1,
        "mem": 512,
        "disk": 0,
        "user": "root",
        "cmd": " && ".join([
            "/bin/bash",
            "HDFS_SERVICE_NAME=data-serviceshdfs /configure-hdfs.sh",
            "bin/hdfs dfs -rm -r -f /terasort_in /terasort_out /terasort_validate"
        ]),
        "docker": {
            "image": "mesosphere/hdfs-client:2.6.4"
        },
        "restart": {
            "policy": "NEVER"
        }
    }
}
TERASORT_DELETE_JOB_KERBEROS = {
    "description": "Job that deletes Terasort files from Kerberized HDFS",
    "id": "hdfs-kerberos-delete-terasort-files",
    "run": {
        "cpus": 0.1,
        "mem": 512,
        "disk": 0,
        "cmd": " && ".join([
            "/bin/bash",
            "cd $MESOS_SANDBOX",
            "python3 dcos-cli-auth.py --username=$DCOS_UID --password=$DCOS_PASSWORD",
            "dcos task exec {hdfsclient_kerberos} kinit -k -t hdfs.keytab {principal}",
            "dcos task exec {hdfsclient_kerberos} bin/hdfs dfs -rm -r -f /terasort_in /terasort_out"
        ]).format(principal=HDFS_PRINCIPAL, hdfsclient_kerberos=HDFSCLIENT_KERBEROS_TASK),
        "env": {
            "DCOS_UID": DCOS_UID,
            "DCOS_PASSWORD": DCOS_PASSWORD,
        },
        "user": "root",
        "artifacts": [
            {
                "uri": "https://s3.amazonaws.com/soak-clusters/artifacts/soak110/dcos-cli-auth.py",
                "extract": True,
                "executable": False,
                "cache": False
            }
        ],
        "docker": {
            "image": "mesosphere/dcos-commons:latest"
        },
        "restart": {
            "policy": "NEVER"
        }
    }
}


def setup_module(module):
    if not shakedown.package_installed('spark', SOAK_SPARK_SERVICE_NAME):
        additional_options = {
            "hdfs": {
                "config-url": "http://api.hdfs.marathon.l4lb.thisdcos.directory/v1/endpoints"
            },
            "security": {
                "kerberos": {
                    "enabled": True,
                    "realm": "LOCAL",
                    "kdc": {
                        "hostname": "kdc.marathon.autoip.dcos.thisdcos.directory",
                        "port": 2500
                    }
                }
            }
        }
        utils.require_spark(service_name=SOAK_SPARK_SERVICE_NAME, additional_options=additional_options)


@pytest.mark.soak
def test_terasort():
    if utils.hdfs_enabled():
        _delete_hdfs_terasort_files()
        _run_teragen()
        _run_terasort()
        _run_teravalidate()


@pytest.mark.soak
def test_spark_kafka_interservice():
    if utils.kafka_enabled():
        rc, stdout, stderr = sdk_cmd.run_raw_cli("package install {} --yes --cli".format(KAFKA_PACKAGE_NAME))
        if rc != 0:
            LOGGER.warn("Got return code {rc} when trying to install {package} cli\nstdout:{out}\n{err}"
                        .format(rc=rc, package=KAFKA_PACKAGE_NAME, out=stdout, err=stderr))
        stop_count = os.getenv("STOP_COUNT", "1000")
        test_pipeline(
            kerberos_flag="true",
            stop_count=stop_count,
            jar_uri=JAR_URI,
            keytab_secret=KAFKA_KEYTAB_SECRET,
            spark_service_name=SOAK_SPARK_SERVICE_NAME,
            jaas_uri=KAFKA_JAAS_URI)


def _run_teragen():
    jar_url = TERASORT_JAR
    input_size = os.getenv('TERASORT_INPUT_SIZE', '1g')
    utils.run_tests(app_url=jar_url,
                    app_args="{} hdfs:///terasort_in".format(input_size),
                    expected_output="Number of records written",
                    service_name=SOAK_SPARK_SERVICE_NAME,
                    args=(["--class", "com.github.ehiggs.spark.terasort.TeraGen"] + COMMON_ARGS))


def _run_terasort():
    jar_url = TERASORT_JAR
    utils.run_tests(app_url=jar_url,
                    app_args="hdfs:///terasort_in hdfs:///terasort_out",
                    expected_output="",
                    service_name=SOAK_SPARK_SERVICE_NAME,
                    args=(["--class", "com.github.ehiggs.spark.terasort.TeraSort"] + COMMON_ARGS))


def _run_teravalidate():
    jar_url = TERASORT_JAR
    utils.run_tests(app_url=jar_url,
                    app_args="hdfs:///terasort_out hdfs:///terasort_validate",
                    expected_output="partitions are properly sorted",
                    service_name=SOAK_SPARK_SERVICE_NAME,
                    args=(["--class", "com.github.ehiggs.spark.terasort.TeraValidate"] + COMMON_ARGS))


def _delete_hdfs_terasort_files():
    if HDFS_KERBEROS_ENABLED:
        job_dict = TERASORT_DELETE_JOB_KERBEROS
    else:
        job_dict = TERASORT_DELETE_JOB
    LOGGER.info("Deleting hdfs terasort files by running job {}".format(job_dict['id']))
    sdk_jobs.install_job(job_dict)
    sdk_jobs.run_job(job_dict, timeout_seconds=300)
    sdk_jobs.remove_job(job_dict)
