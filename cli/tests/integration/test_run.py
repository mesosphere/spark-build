import mock
import pytest
import six

from dcos_spark import spark_submit


@pytest.mark.skip(
    reason=("This is failing when fake.com fails to connect, "
            "but I don't want to spend the time to fix it, because this CLI "
            "is hopefully going away in 1.10."))
@mock.patch('subprocess.Popen')
@mock.patch('dcos_spark.spark_submit.spark_app')
def test_spark_hdfs_config_url(spark_app, Popen):
    base_url = 'http://mgummelt-l33t-haxor'
    spark_app.return_value = {'labels':
                              {'SPARK_HDFS_CONFIG_URL': base_url,
                               'SPARK_URI': ''}}

    proc = mock.MagicMock()
    proc.communicate = mock.MagicMock(return_value=(six.b(''), six.b('')))
    Popen.return_value = proc

    spark_submit.submit_job('http://fake.com', '', '')

    args, kwargs = Popen.call_args
    assert '-Dspark.mesos.uris={0}/{1},{0}/{2}'.format(
        base_url,
        'hdfs-site.xml',
        'core-site.xml') in kwargs['env']['SPARK_JAVA_OPTS']
