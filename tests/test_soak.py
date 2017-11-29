import dcos.metronome
import dcos.package
import json
import os
import logging
import pytest
import shakedown

from tests import utils


LOGGER = logging.getLogger(__name__)
SOAK_SPARK_SERVICE_NAME = os.getenv('SOAK_SPARK_SERVICE_NAME', '/spark')
TERASORT_JAR='https://downloads.mesosphere.io/spark/examples/spark-terasort-1.1-jar-with-dependencies_2.11.jar'
TERASORT_MAX_CORES=6
HDFS_KERBEROS_ENABLED=os.getenv('HDFS_KERBEROS_ENABLED', 'true')
KERBEROS_ARGS = ["--kerberos-principal", "hdfs/name-0-node.hdfs.autoip.dcos.thisdcos.directory@LOCAL",
                 "--keytab-secret-path", "/__dcos_base64___keytab"]
COMMON_ARGS = ["--conf", "spark.driver.port=1024",
               "--conf", "spark.cores.max={}".format(TERASORT_MAX_CORES)]
if HDFS_KERBEROS_ENABLED != 'false':
    COMMON_ARGS += KERBEROS_ARGS
DCOS_UID = os.getenv('DCOS_UID')
DCOS_PASSWORD = os.getenv('DCOS_PASSWORD')


def setup_module(module):
    utils.require_spark(service_name=SOAK_SPARK_SERVICE_NAME, use_hdfs=True)


@pytest.mark.soak
def test_terasort():
    if utils.hdfs_enabled():
        _delete_hdfs_terasort_files()
        _run_teragen()
        _run_terasort()
        _run_teravalidate()


def _run_teragen():
    jar_url = TERASORT_JAR
    input_size = os.getenv('TERASORT_INPUT_SIZE', '1g')
    utils.run_tests(app_url=jar_url,
                    app_args="{} hdfs:///terasort_in".format(input_size),
                    expected_output="Number of records written",
                    app_name=SOAK_SPARK_SERVICE_NAME,
                    args=(["--class", "com.github.ehiggs.spark.terasort.TeraGen"] + COMMON_ARGS))


def _run_terasort():
    jar_url = TERASORT_JAR
    utils.run_tests(app_url=jar_url,
                    app_args="hdfs:///terasort_in hdfs:///terasort_out",
                    expected_output="",
                    app_name=SOAK_SPARK_SERVICE_NAME,
                    args=(["--class", "com.github.ehiggs.spark.terasort.TeraSort"] + COMMON_ARGS))


def _run_teravalidate():
    jar_url = TERASORT_JAR
    utils.run_tests(app_url=jar_url,
                    app_args="hdfs:///terasort_out hdfs:///terasort_validate",
                    expected_output="partitions are properly sorted",
                    app_name=SOAK_SPARK_SERVICE_NAME,
                    args=(["--class", "com.github.ehiggs.spark.terasort.TeraValidate"] + COMMON_ARGS))


def _delete_hdfs_terasort_files():
    if HDFS_KERBEROS_ENABLED != 'false':
        job_name = 'hdfs-kerberos-delete-terasort-files'
    else:
        job_name = 'hdfs-delete-terasort-files'
    LOGGER.info("Deleting hdfs terasort files by running job {}".format(job_name))
    metronome_client = dcos.metronome.create_client()
    if not _job_exists(metronome_client, job_name):
        _add_job(metronome_client, job_name)
    _run_job_and_wait(metronome_client, job_name, timeout_seconds=300)
    metronome_client.remove_job(job_name)
    LOGGER.info("Job {} completed".format(job_name))


def _job_exists(metronome_client, job_name):
    jobs = metronome_client.get_jobs()
    return any(job['id'] == job_name for job in jobs)


def _add_job(metronome_client, job_name):
    jobs_folder = os.path.join(
        os.path.dirname(os.path.realpath(__file__)), 'jobs', 'json'
    )
    job_path = os.path.join(jobs_folder, '{}.json'.format(job_name))
    with open(job_path) as job_file:
        job = json.load(job_file)
    job["run"] = job.get("run", {})
    job["run"]["env"] = job["run"].get("env", {})
    job["run"]["env"]["DCOS_UID"] = DCOS_UID
    job["run"]["env"]["DCOS_PASSWORD"] = DCOS_PASSWORD
    metronome_client.add_job(job)


def _run_job_and_wait(metronome_client, job_name, timeout_seconds):
    metronome_client.run_job(job_name)

    shakedown.wait_for(
        lambda: (
            'Successful runs: 1' in
            _run_cli('job history {}'.format(job_name))
        ),
        timeout_seconds=timeout_seconds,
        ignore_exceptions=False
    )


def _run_cli(cmd):
    (stdout, stderr, ret) = shakedown.run_dcos_command(cmd)
    if ret != 0:
        err = 'Got error code {} when running command "dcos {}":\nstdout: "{}"\nstderr: "{}"'.format(
            ret, cmd, stdout, stderr)
        raise Exception(err)
    return stdout
