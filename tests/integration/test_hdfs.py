from tests.integration.fixture_hdfs import HDFS_DATA_DIR, HDFS_HISTORY_DIR
from tests.integration.fixture_hdfs import SPARK_SUBMIT_HDFS_KERBEROS_ARGS

import json
import logging
import pytest
import retrying
import sdk_cmd
import sdk_tasks
import sdk_utils
import shakedown
import spark_utils as utils

log = logging.getLogger(__name__)


def _run_terasort_job(terasort_class, app_args, expected_output):
    jar_url = 'https://downloads.mesosphere.io/spark/examples/spark-terasort-1.1-jar-with-dependencies_2.11.jar'
    submit_args = ["--class", terasort_class] + SPARK_SUBMIT_HDFS_KERBEROS_ARGS
    utils.run_tests(app_url=jar_url,
                    app_args=" ".join(app_args),
                    expected_output=expected_output,
                    args=submit_args)


@sdk_utils.dcos_ee_only
@pytest.mark.skipif(not utils.hdfs_enabled(), reason='HDFS_ENABLED is false')
@pytest.mark.sanity
def test_terasort_suite(kerberized_spark, hdfs_with_kerberos):
    data_dir = "hdfs://{}".format(HDFS_DATA_DIR)
    terasort_in = "{}/{}".format(data_dir, "terasort_in")
    terasort_out = "{}/{}".format(data_dir, "terasort_out")
    terasort_validate = "{}/{}".format(data_dir, "terasort_validate")

    _run_terasort_job(terasort_class="com.github.ehiggs.spark.terasort.TeraGen",
                      app_args=["1g", terasort_in],
                      expected_output="Number of records written")

    _run_terasort_job(terasort_class="com.github.ehiggs.spark.terasort.TeraSort",
                      app_args=[terasort_in, terasort_out],
                      expected_output="")

    _run_terasort_job(terasort_class="com.github.ehiggs.spark.terasort.TeraValidate",
                      app_args=[terasort_out, terasort_validate],
                      expected_output="partitions are properly sorted")


@sdk_utils.dcos_ee_only
@pytest.mark.skipif(not utils.hdfs_enabled(), reason='HDFS_ENABLED is false')
@pytest.mark.sanity
def test_supervise(kerberized_spark, hdfs_with_kerberos):
    job_service_name = "RecoverableNetworkWordCount"

    @retrying.retry(
        wait_fixed=1000,
        stop_max_delay=600 * 1000,
        retry_on_result=lambda res: not res)
    def wait_job_present(present):
        svc = shakedown.get_service(job_service_name)
        if present:
            return svc is not None
        else:
            return svc is None

    job_args = ["--supervise",
                "--class", "org.apache.spark.examples.streaming.RecoverableNetworkWordCount",
                "--conf", "spark.cores.max=8",
                "--conf", "spark.executors.cores=4"]

    data_dir = "hdfs://{}".format(HDFS_DATA_DIR)
    driver_id = utils.submit_job(app_url=utils.SPARK_EXAMPLES,
                                 app_args="10.0.0.1 9090 {dir}/netcheck {dir}/outfile".format(dir=data_dir),
                                 service_name=utils.SPARK_SERVICE_NAME,
                                 args=(SPARK_SUBMIT_HDFS_KERBEROS_ARGS + job_args))
    log.info("Started supervised driver {}".format(driver_id))
    wait_job_present(True)
    log.info("Job has registered")
    sdk_tasks.check_running(job_service_name, 1)
    log.info("Job has running executors")

    service_info = shakedown.get_service(job_service_name).dict()
    driver_regex = "spark.mesos.driver.frameworkId={}".format(service_info['id'])

    status, stdout = shakedown.run_command_on_agent(service_info['hostname'],
                                                    "ps aux | grep -v grep | grep '{}'".format(driver_regex),
                                                    username=sdk_cmd.LINUX_USER)

    pids = [p.strip().split()[1] for p in stdout.splitlines()]

    for pid in pids:
        status, stdout = shakedown.run_command_on_agent(service_info['hostname'],
                                                        "sudo kill -9 {}".format(pid),
                                                        username=sdk_cmd.LINUX_USER)

        if status:
            print("Killed pid: {}".format(pid))
        else:
            print("Unable to killed pid: {}".format(pid))

    wait_job_present(True)
    log.info("Job has re-registered")
    sdk_tasks.check_running(job_service_name, 1)
    log.info("Job has re-started")
    out = utils.kill_driver(driver_id, utils.SPARK_SERVICE_NAME)
    log.info("{}".format(out))
    out = json.loads(out)
    assert out["success"], "Failed to kill spark streaming job"
    wait_job_present(False)


@sdk_utils.dcos_ee_only
@pytest.mark.skipif(not utils.hdfs_enabled(), reason='HDFS_ENABLED is false')
@pytest.mark.sanity
def test_history(kerberized_spark, hdfs_with_kerberos, setup_history_server):
    job_args = ["--class", "org.apache.spark.examples.SparkPi",
                "--conf", "spark.eventLog.enabled=true",
                "--conf", "spark.eventLog.dir=hdfs://hdfs{}".format(HDFS_HISTORY_DIR)]
    utils.run_tests(app_url=utils.SPARK_EXAMPLES,
                    app_args="100",
                    expected_output="Pi is roughly 3",
                    service_name="spark",
                    args=(job_args + SPARK_SUBMIT_HDFS_KERBEROS_ARGS))

