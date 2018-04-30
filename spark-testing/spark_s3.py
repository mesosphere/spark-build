import os

from boto.s3.connection import S3Connection
from boto.s3.key import Key


conn = None
def _get_conn():
    global conn
    if conn is None:
        conn = S3Connection(
            os.environ['AWS_ACCESS_KEY_ID'],
            os.environ['AWS_SECRET_ACCESS_KEY'],
            security_token=os.getenv('AWS_SESSION_TOKEN'))
    return conn


def s3n_url(filename):
    return "s3n://{}/{}/{}".format(
        os.environ["S3_BUCKET"],
        os.environ["S3_PREFIX"],
        filename)


def s3_http_url(filename):
    return "http://{bucket}.s3.amazonaws.com/{prefix}/{file}".format(
        bucket=os.environ["S3_BUCKET"],
        prefix=os.environ["S3_PREFIX"],
        file=filename)


def upload_file(file_path):
    bucket = _get_bucket()
    basename = os.path.basename(file_path)

    content_type = _get_content_type(basename)

    path = _path(basename)
    key = Key(bucket, path)
    key.metadata = {'Content-Type': content_type}
    key.set_contents_from_filename(file_path)
    key.make_public()


def get_key(filename):
    bucket = _get_bucket()
    path = _path(filename)
    return bucket.get_key(path)


def list(prefix):
    path = _path(prefix)
    return _get_bucket().list(path)


def http_url(filename):
    return "http://{0}.s3.amazonaws.com/{1}/{2}".format(
        os.environ['S3_BUCKET'],
        os.environ['S3_PREFIX'],
        filename)


def _get_bucket():
    return _get_conn().get_bucket(os.environ['S3_BUCKET'])


def _path(basename):
    return '{}/{}'.format(os.environ['S3_PREFIX'], basename)


def _get_content_type(basename):
    if basename.endswith('.jar'):
        content_type = 'application/java-archive'
    elif basename.endswith('.py'):
        content_type = 'application/x-python'
    elif basename.endswith('.R'):
        content_type = 'application/R'
    else:
        content_type = 'text/plain'
    return content_type
