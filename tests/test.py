# Env:
#   AWS_ACCESS_KEY_ID
#   AWS_SECRET_ACCESS_KEY
#   S3_BUCKET
#   S3_PREFIX
#   TEST_JAR_PATH
#   DOCKER_IMAGE

from boto.s3.connection import S3Connection
from boto.s3.key import Key
import json
import os
import re
import subprocess
import shakedown

CWD = os.path.dirname(os.path.abspath(__file__))


def test_jar():
    jar_url = _upload_file(os.getenv('TEST_JAR_PATH'))
    job_path = os.path.join(CWD, 'jobs', 'metronome', 'spark_job_runner.json')

    with open(job_path) as f:
        template_vars = {'docker_image': os.getenv('DOCKER_IMAGE'),
                         'test_jar_path': jar_url}
        job_str = _render_template(f.read(), template_vars)
        job_spec = json.loads(job_str)

    shakedown.run_job(job_spec)


def test_python():
    pi_with_include_path = os.path.join(CWD, 'jobs', 'pi_with_include.py')
    pi_with_include_uri = _upload_file(pi_with_include_path)
    py_spark_test_include_path = os.path.join(CWD, 'jobs', 'PySparkTestInclude.py')
    py_spark_test_include_uri = _upload_file(py_spark_test_include_path)

    with open('jobs/metronome/python.json') as f:
        template_vars = {'docker_image': os.getenv('DOCKER_IMAGE'),
                         'pi_with_include_uri': pi_with_include_uri,
                         'py_spark_test_include_uri': py_spark_test_include_uri}
        job_str = _render_template(f.read(), template_vars)
        job_spec = json.loads(job_str)

    shakedown.run_job(job_spec)

# def test_r():
#     # TODO: enable R test when R is enabled in Spark (2.1)
#     #r_script_path = os.path.join(script_dir, 'jobs', 'dataframe.R')
#     #run_tests(r_script_path,
#     #    '',
#     #    "1 Justin")
#     pass


# TODO: implement this when metronome supports CNI
# def test_cni():
#     SPARK_EXAMPLES="http://downloads.mesosphere.com/spark/assets/spark-examples_2.11-2.0.1.jar"
#     _run_tests(SPARK_EXAMPLES,
#                "",
#                "Pi is roughly 3",
#                {"--class": "org.apache.spark.examples.SparkPi"},
#                {"spark.mesos.network.name": "dcos"})


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


def _render_template(content, template_vars):
    for k, v in template_vars.items():
        content = content.replace('{{' + k + '}}', v)
    return content
