from __future__ import print_function

import json
import logging
import os
import os.path
import posixpath
import re
import shutil
import ssl
import subprocess
import sys
import tarfile
import threading

import requests
import six
from dcos import config, http, marathon, util
from dcos_spark import constants, service

from six.moves import urllib
from six.moves.BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
from six.moves.http_client import HTTPMessage

# singleton storing the spark marathon app
app = None


logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def spark_app():
    global app
    if app:
        return app

    client = marathon.create_client()
    apps = client.get_apps()
    for marathon_app in apps:
        if marathon_app.get('labels', {}).get('DCOS_PACKAGE_FRAMEWORK_NAME') \
           == service.app_id():
            app = marathon_app
            return app

    if not app:
        sys.stderr.write('No spark app found in marathon.  Quitting...\n')
        sys.exit(1)


def partition(args, pred):
    ain = []
    aout = []
    for x in args:
        if pred(x):
            ain.append(x)
        else:
            aout.append(x)
    return (ain, aout)


def spark_docker_image():
    return spark_app()['container']['docker']['image']


def _spark_dist_dir():
    dist_dir = config.get_config().get('spark.distribution_directory',
                                       '~/.dcos/spark/dist')
    return os.path.expanduser(dist_dir)


def spark_dist():
    """Returns the directory location of the local spark distribution.
    Fetches it if it doesn't exist."""

    app = spark_app()
    spark_uri = app['labels']['SPARK_URI']

    # <spark>.tgz
    basename = posixpath.basename(spark_uri)

    # <spark>
    root = posixpath.splitext(basename)[0]

    # data/
    data_dir = _spark_dist_dir()
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)

    # data/<spark.tgz>
    spark_archive = os.path.join(data_dir, basename)

    # data/<spark>
    spark_dir = os.path.join(data_dir, root)

    # data/tmp
    data_tmp_dir = os.path.join(data_dir, 'tmp')

    # only download spark if data/<spark> doesn't yet exist
    if not os.path.exists(spark_dir):
        # download archive
        print('Spark distribution {} not found locally.'.format(root))
        print('It looks like this is your first time running Spark!')
        print('Downloading {}...'.format(spark_uri))

        resp = http.request('GET', spark_uri, stream=True)
        resp.raise_for_status()

        # write to data/<spark.tgz>
        with open(spark_archive, 'wb') as spark_archive_file:
            for block in resp:
                spark_archive_file.write(block)

        # extract to data/tmp/<spark>
        print('Extracting spark distribution {}...'.format(spark_archive))
        tf = tarfile.open(spark_archive)
        tf.extractall(data_tmp_dir)
        tf.close()

        # move from data/tmp/<spark> to data/<spark>
        spark_tmp = os.path.join(data_tmp_dir, root)
        shutil.copytree(spark_tmp, spark_dir)

        # clean up data/tmp/<spark> and data/<spark.tgz>
        shutil.rmtree(spark_tmp)
        os.remove(spark_archive)
        print('Successfully fetched spark distribution {}!'.format(spark_uri))

    return spark_dir


def spark_file(path):
    return os.path.join(spark_dist(), path)


def show_help():
    submit_file = spark_file(os.path.join('bin', 'spark-submit'))

    command = [submit_file, "--help"]

    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE)

    stdout, stderr = process.communicate()

    for line in stderr.decode("utf-8").split("\n"):
        if line.startswith("Usage:"):
            continue
        print(line)

    return 0


def submit_job(dispatcher, submit_args, docker_image, verbose=False):
    """
    Run spark-submit.

    :param dispatcher: Spark Dispatcher URL.  Used to construct --master.
    :type dispatcher: string
    :param args: --submit-args value from `dcos spark run`
    :type args: string
    :param docker_image: Docker image to run the driver and executors in.
    :type docker_image: string
    :param verbose: If true, prints verbose information to stdout.
    :type verbose: boolean
    """
    args = ["--conf",
            "spark.mesos.executor.docker.image={}".format(docker_image)] + \
        submit_args.split()

    hdfs_url = _get_spark_hdfs_url()
    if hdfs_url is not None:
        # urljoin only works as expected if the base URL ends with '/'
        if hdfs_url[-1] != '/':
            hdfs_url += '/'
        hdfs_config_url = urllib.parse.urljoin(hdfs_url, 'hdfs-site.xml')
        site_config_url = urllib.parse.urljoin(hdfs_url, 'core-site.xml')
        args = ["--conf", "spark.mesos.uris={0},{1}".format(
            hdfs_config_url,
            site_config_url)] + \
            args

    response = run(dispatcher, args, verbose)
    if response[0] is not None:
        print("Run job succeeded. Submission id: " +
              response[0]['submissionId'])
    return response[1]


def job_status(dispatcher, submissionId, verbose=False):
    response = run(dispatcher, ["--status", submissionId], verbose)
    if response[0] is not None:
        print("Submission ID: " + response[0]['submissionId'])
        print("Driver state: " + response[0]['driverState'])
        if 'message' in response[0]:
            print("Last status: " + response[0]['message'])
    elif response[1] == 0:
        print("Job id '" + submissionId + "' is not found")
    return response[1]


def kill_job(dispatcher, submissionId, verbose=False):
    response = run(dispatcher, ["--kill", submissionId], verbose)
    if response[0] is not None:
        if bool(response[0]['success']):
            success = "succeeded."
        else:
            success = "failed."
        print("Kill job " + success)
        print("Message: " + response[0]['message'])
    return response[1]


def which(program):
    """Returns the path to the named executable program.

    :param program: The program to locate:
    :type program: str
    :rtype: str
    """

    def is_exe(file_path):
        return os.path.isfile(file_path) and os.access(file_path, os.X_OK)

    file_path, filename = os.path.split(program)
    if file_path:
        if is_exe(program):
            return program
    elif constants.PATH_ENV in os.environ:
        for path in os.environ[constants.PATH_ENV].split(os.pathsep):
            path = path.strip('"')
            exe_file = os.path.join(path, program)
            if is_exe(exe_file):
                return exe_file

    return None


def check_java_version(java_path):
    process = subprocess.Popen(
        [java_path, "-version"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE)

    stdout, stderr = process.communicate()

    lines = stderr.decode('utf8').split(os.linesep)
    if len(lines) == 0:
        print("Unable to check java version, error: no output detected "
              "from " + java_path + " -version")
        return False

    match = re.search("1\.(\d+)", lines[0])
    if match and int(match.group(1)) < 7:
        print("DCOS Spark requires Java 1.7.x or greater to be installed, "
              "found " + lines[0])
        return False

    return True


def check_java():
    java_executable = 'java.exe' if util.is_windows_platform() else 'java'
    # Check if JAVA is in the PATH
    if which(java_executable) is not None:
        return check_java_version(java_executable)

    # Check if JAVA_HOME is set and find java
    java_home = os.environ.get('JAVA_HOME')

    if java_home is not None:
        java_path = os.path.join(java_home, "bin", java_executable)
        if os.path.isfile(java_path):
            return check_java_version(java_path)

    print("DCOS Spark requires Java 1.7.x to be installed, please install JRE")
    return False


def run(dispatcher, args, verbose):
    """
    Runs spark-submit.

    :param dispatcher: Spark Dispatcher URL.  Used to construct --master.
    :type dispatcher: string
    :param args: Extra arguments to spark-submit
    :type args: list[string]
    :param verbose: If true, prints verbose information to stdout.
    :type verbose: boolean
    """
    if not check_java():
        return (None, 1)

    proxying = _should_proxy(dispatcher)
    proxy_thread = ProxyThread(_get_token() if proxying else None, dispatcher)
    if proxying:
        proxy_thread.start()
        dispatcher = 'http://localhost:{}'.format(proxy_thread.port())

    command = _get_command(dispatcher, args)

    # On Windows, python 2 complains about unicode in env.
    env = dict([str(key), str(value)]
               for key, value in os.environ.iteritems()) \
        if util.is_windows_platform() and sys.version_info[0] < 3 \
        else os.environ

    process = subprocess.Popen(
        command,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE)

    stdout, stderr = process.communicate()

    if proxying:
        proxy_thread.proxy.shutdown()
        proxy_thread.join()

    if verbose:
        print("Ran command: " + " ".join(command))
        print("Stdout:")
        print(stdout)
        print("Stderr:")
        print(stderr)

    err = stderr.decode("utf-8")
    if process.returncode != 0:
        if "502 Bad Gateway" in err:
            print("Spark service is not found in your DCOS cluster.")
            return (None, process.returncode)

        if "500 Internal Server Error" in err:
            print("Error reaching Spark cluster endpoint. Please make sure "
                  "Spark service is in running state in Marathon.")
            return (None, process.returncode)

        print("Spark submit failed:")
        print(stderr)
        return (None, process.returncode)
    else:
        if "{" in err:
            lines = err.splitlines()
            jsonStr = ""
            startScan = False
            for l in lines:
                if l.startswith("}") and startScan:
                    jsonStr += l + os.linesep
                    startScan = False
                elif startScan:
                    jsonStr += l + os.linesep
                elif l.startswith("{"):
                    startScan = True
                    jsonStr += l + os.linesep

            response = json.loads(jsonStr)
            return (response, process.returncode)
        return (None, process.returncode)


def _get_spark_hdfs_url():
    return spark_app()['labels'].get('SPARK_HDFS_CONFIG_URL')


def _get_command(dispatcher, args):
    spark_executable = 'spark-submit.cmd' if util.is_windows_platform() \
                                          else 'spark-submit'
    submit_file = spark_file(os.path.join('bin', spark_executable))

    if dispatcher.startswith("https://"):
        dispatcher = "mesos-ssl://" + dispatcher[8:]
    else:
        dispatcher = "mesos://" + dispatcher[7:]

    if _cert_verification():
        ssl_ops = []
    else:
        ssl_ops = ["--conf", "spark.ssl.noCertVerification=true"]

    return [submit_file, "--deploy-mode", "cluster", "--master",
            dispatcher] + ssl_ops + args


def _cert_verification():
    try:
        core_verify_ssl = config.get_config()['core.ssl_verify']
        return str(core_verify_ssl).lower() in ['true', 'yes', '1']
    except:
        return True


def _should_proxy(dispatcher):
    resp = requests.get(dispatcher, verify=_cert_verification())
    return resp.status_code == 401


def _get_token():
    dcos_url = config.get_config().get('core.dcos_url')
    hostname = urllib.parse.urlparse(dcos_url).hostname
    return http._get_dcos_auth(None, None, None, hostname).token


class ProxyThread(threading.Thread):
    def __init__(self, token, dispatcher):
        self.proxy = HTTPServer(('localhost', 0), ProxyHandler)
        self.proxy.dispatcher = dispatcher
        self.proxy._dcos_auth_token = token
        super(ProxyThread, self).__init__()

    def run(self):
        self.proxy.serve_forever()

    def port(self):
        return self.proxy.socket.getsockname()[1]


class ProxyHandler(BaseHTTPRequestHandler):
    MessageClass = HTTPMessage

    def do_GET(self):
        self._request('GET')

    def do_POST(self):
        self._request('POST')

    def _request(self, method):
        self.server._dcos_auth_token

        url = self.server.dispatcher
        if url.endswith('/'):
            url = url[:-1]
        url = url + self.path

        if method == 'POST':
            if 'content-length' in self.headers:
                body = self.rfile.read(
                    int(self.headers['content-length']))
            else:
                body = six.b('')
            req = urllib.request.Request(url, body)
        else:
            body = six.b('')
            req = urllib.request.Request(url)

        logger.debug('=== BEGIN REQUEST ===')
        logger.debug(url)
        logger.debug('\n')

        for key, value in self.headers.items():
            # key, value = line.strip().split(':', 1)
            logger.debug('{0}:{1}'.format(key, value))
            req.add_header(key, value)

        req.add_header(
            'Authorization',
            'token={}'.format(self.server._dcos_auth_token))

        logger.debug('\n')
        logger.debug(body)

        ctx = ssl.create_default_context()
        if not _cert_verification():
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE

        try:
            resp = urllib.request.urlopen(req, context=ctx)
        except urllib.error.HTTPError as e:
            resp = e

        self.send_response(resp.getcode())

        logger.debug('=== BEGIN RESPONSE ===')
        logger.debug(resp.getcode())

        for key, value in resp.info().items():
            # key, value = header.strip().split(':', 1)
            self.send_header(key, value)
            logger.debug('{0}:{1}'.format(key, value))
        self.end_headers()

        body = resp.read()
        self.wfile.write(body)

        logger.debug('\n')
        logger.debug(body)
