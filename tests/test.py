# Env:
#   AWS_ACCESS_KEY_ID
#   AWS_SECRET_ACCESS_KEY
#   S3_BUCKET
#   S3_PREFIX
#   TEST_JAR_PATH
#   TEST_PYTHON_APP_PATH
#   TEST_PYTHON_APP_ARGS

from boto.s3.connection import S3Connection
from boto.s3.key import Key
import re
import os
import subprocess
import shakedown


def upload_jar(jar):
    conn = S3Connection(os.environ['AWS_ACCESS_KEY_ID'], os.environ['AWS_SECRET_ACCESS_KEY'])
    bucket = conn.get_bucket(os.environ['S3_BUCKET'])
    basename = os.path.basename(jar)

    key = Key(bucket, '{}/{}'.format(os.environ['S3_PREFIX'], basename))
    key.metadata = {'Content-Type': 'application/java-archive'}
    key.set_contents_from_filename(jar)
    key.make_public()

    jar_url = "http://{0}.s3.amazonaws.com/{1}/{2}".format(
        os.environ['S3_BUCKET'],
        os.environ['S3_PREFIX'],
        basename)

    return jar_url


def submit_job(app_class, app_resource_url, app_args):
    if (app_class):
        app_class_option = '--class {} '.format(app_class)
    else:
        app_class_option = ''
    submit_args = "-Dspark.driver.memory=2g {0}{1} {2}".format(
        app_class_option, app_resource_url, app_args)
    cmd = 'dcos --log-level=DEBUG spark --verbose run --submit-args="{0}"'.format(submit_args)
    print('Running {}'.format(cmd))
    stdout = subprocess.check_output(cmd, shell=True).decode('utf-8')
    print(stdout)

    regex = r"Submission id: (\S+)"
    match = re.search(regex, stdout)
    return match.group(1)


def task_log(task_id):
    cmd = "dcos task log --completed --lines=1000 {}".format(task_id)
    print('Running {}'.format(cmd))
    stdout = subprocess.check_output(cmd, shell=True).decode('utf-8')
    return stdout


def run_tests(app_class, app_path, app_args, expected_output):
    app_resource_url = upload_jar(app_path)
    task_id = submit_job(app_class, app_resource_url, app_args)
    print('Waiting for task id={} to complete'.format(task_id))
    shakedown.wait_for_task_completion(task_id)
    log = task_log(task_id)
    print(log)
    assert expected_output in log


def main():
    spark_job_runner_args = 'http://leader.mesos:5050 dcos \\"*\\" spark:only 2'
    run_tests('com.typesafe.spark.test.mesos.framework.runners.SparkJobRunner',
        os.getenv('TEST_JAR_PATH'), spark_job_runner_args,
        "All tests passed")

    script_dir = os.path.dirname(os.path.abspath(__file__))
    python_script_path = os.path.join(script_dir, 'pi.py')
    run_tests('', 
        python_script_path, '30',
        "Pi is roughly 3")


if __name__ == '__main__':
    main()
