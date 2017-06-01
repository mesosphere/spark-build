from __future__ import print_function

import os

from dcos import config
from dcos_spark import service

from six.moves import urllib


def get_spark_webui():
    base_url = config.get_config().get('core.dcos_url')
    return base_url + '/service/' + service.app_id() + '/ui'


def get_spark_dispatcher():
    dcos_spark_url = os.getenv("DCOS_SPARK_URL")
    if dcos_spark_url is not None:
        return dcos_spark_url

    base_url = config.get_config().get('core.dcos_url')
    return urllib.parse.urljoin(base_url, '/service/' + service.app_id() + '/')
