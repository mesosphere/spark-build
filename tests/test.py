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


def get_content_type(basename):
    if basename.endswith('.jar'):
        content_type = 'application/java-archive'
    elif basename.endswith('.py'):
        content_type = 'application/x-python'
    elif basename.endswith('.R'):
        content_type = 'application/R'
    else:
        raise ValueError("Unexpected file type: {}. Expected .jar, .py, or .R file.".format(basename))
    return content_type


def upload_file(file_path):
    conn = S3Connection(os.environ['AWS_ACCESS_KEY_ID'], os.environ['AWS_SECRET_ACCESS_KEY'])
    bucket = conn.get_bucket(os.environ['S3_BUCKET'])
    basename = os.path.basename(file_path)

    content_type = get_content_type(basename)

    key = Key(bucket, '{}/{}'.format(os.environ['S3_PREFIX'], basename))
    key.metadata = {'Content-Type': content_type}
    key.set_contents_from_filename(file_path)
    key.make_public()

    jar_url = "http://{0}.s3.amazonaws.com/{1}/{2}".format(
        os.environ['S3_BUCKET'],
        os.environ['S3_PREFIX'],
        basename)

    return jar_url


def submit_job(app_resource_url, app_args, app_class, py_files):
    if app_class is not None:
        app_class_option = '--class {} '.format(app_class)
    else:
        app_class_option = ''
    if py_files is not None:
        py_files_option = '--py-files {} '.format(py_files)
    else:
        py_files_option = ''

    submit_args = "-Dspark.driver.memory=2g {0}{1}{2} {3}".format(
        app_class_option, py_files_option, app_resource_url, app_args)
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


def run_tests(app_path, app_args, expected_output, app_class=None, py_file_path=None):
    app_resource_url = upload_file(app_path)
    if py_file_path is not None:
      py_file_url = upload_file(py_file_path)
    else:
      py_file_url = None
    task_id = submit_job(app_resource_url, app_args, app_class, py_file_url)
    print('Waiting for task id={} to complete'.format(task_id))
    shakedown.wait_for_task_completion(task_id)
    log = task_log(task_id)
    print(log)
    assert expected_output in log


def main():
    spark_job_runner_args = 'http://leader.mesos:5050 dcos \\"*\\" spark:only 2'
    run_tests(os.getenv('TEST_JAR_PATH'),
        spark_job_runner_args,
        "All tests passed",
        app_class='com.typesafe.spark.test.mesos.framework.runners.SparkJobRunner')

    script_dir = os.path.dirname(os.path.abspath(__file__))
    python_script_path = os.path.join(script_dir, 'jobs', 'pi_with_include.py')
    py_file_path = os.path.join(script_dir, 'jobs', 'PySparkTestInclude.py')
    run_tests(python_script_path,
        '30',
        "Pi is roughly 3",
        py_file_path=py_file_path)

    # TODO: enable R test when R is enabled in Spark (2.1)
    #r_script_path = os.path.join(script_dir, 'jobs', 'dataframe.R')
    #run_tests(r_script_path,
    #    '',
    #    "1 Justin")


if __name__ == '__main__':
    main()
