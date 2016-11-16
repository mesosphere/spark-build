# Env:
#   AWS_ACCESS_KEY_ID
#   AWS_SECRET_ACCESS_KEY
#   S3_BUCKET
#   S3_PREFIX
#   TEST_JAR_PATH

from boto.s3.connection import S3Connection
from boto.s3.key import Key
import re
import os
import subprocess
import shakedown


def test_jar():
    spark_job_runner_args = 'http://leader.mesos:5050 dcos \\"*\\" spark:only 2'
    jar_url = _upload_file(os.getenv('TEST_JAR_PATH'))
    _run_tests(jar_url,
               spark_job_runner_args,
               "All tests passed",
               {"--class": 'com.typesafe.spark.test.mesos.framework.runners.SparkJobRunner'})


def test_python():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    python_script_path = os.path.join(script_dir, 'jobs', 'pi_with_include.py')
    python_script_url = _upload_file(python_script_path)
    py_file_path = os.path.join(script_dir, 'jobs', 'PySparkTestInclude.py')
    py_file_url = _upload_file(py_file_path)
    _run_tests(python_script_url,
               "30",
               "Pi is roughly 3",
               {"--py-files": py_file_url})

def test_r():
    # TODO: enable R test when R is enabled in Spark (2.1)
    #r_script_path = os.path.join(script_dir, 'jobs', 'dataframe.R')
    #run_tests(r_script_path,
    #    '',
    #    "1 Justin")
    pass


def test_cni():
    SPARK_EXAMPLES="http://downloads.mesosphere.com/spark/assets/spark-examples_2.11-2.0.1.jar"
    _run_tests(SPARK_EXAMPLES,
               "",
               "Pi is roughly 3",
               {"--class": "org.apache.spark.examples.SparkPi"},
               {"spark.mesos.network.name": "dcos"})


def _run_tests(app_url, app_args, expected_output, args={}, config={}):
    task_id = _submit_job(app_url, app_args, args, config)
    print('Waiting for task id={} to complete'.format(task_id))
    shakedown.wait_for_task_completion(task_id)
    log = _task_log(task_id)
    print(log)
    assert expected_output in log


def _submit_job(app_url, app_args, args={}, config={}):
    args_str = ' '.join('{0} {1}'.format(k, v) for k,v in args.items())
    config_str = ' '.join('-D{0}={1}'.format(k, v) for k,v in config.items())
    submit_args = ' '.join(arg for arg in ["-Dspark.driver.memory=2g", args_str, app_url, app_args, config_str] if arg != "")
    cmd = 'dcos --log-level=DEBUG spark --verbose run --submit-args="{0}"'.format(submit_args)
    print('Running {}'.format(cmd))
    stdout = subprocess.check_output(cmd, shell=True).decode('utf-8')
    print(stdout)

    regex = r"Submission id: (\S+)"
    match = re.search(regex, stdout)
    return match.group(1)


def _upload_file(file_path):
    conn = S3Connection(os.environ['AWS_ACCESS_KEY_ID'], os.environ['AWS_SECRET_ACCESS_KEY'])
    bucket = conn.get_bucket(os.environ['S3_BUCKET'])
    basename = os.path.basename(file_path)

    content_type = _get_content_type(basename)

    key = Key(bucket, '{}/{}'.format(os.environ['S3_PREFIX'], basename))
    key.metadata = {'Content-Type': content_type}
    key.set_contents_from_filename(file_path)
    key.make_public()

    jar_url = "http://{0}.s3.amazonaws.com/{1}/{2}".format(
        os.environ['S3_BUCKET'],
        os.environ['S3_PREFIX'],
        basename)

    return jar_url


def _get_content_type(basename):
    if basename.endswith('.jar'):
        content_type = 'application/java-archive'
    elif basename.endswith('.py'):
        content_type = 'application/x-python'
    elif basename.endswith('.R'):
        content_type = 'application/R'
    else:
        raise ValueError("Unexpected file type: {}. Expected .jar, .py, or .R file.".format(basename))
    return content_type


def _task_log(task_id):
    cmd = "dcos task log --completed --lines=1000 {}".format(task_id)
    print('Running {}'.format(cmd))
    stdout = subprocess.check_output(cmd, shell=True).decode('utf-8')
    return stdout
