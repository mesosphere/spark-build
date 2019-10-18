import logging
import os
import os.path

import botocore.session

log = logging.getLogger(__name__)


def s3_url(filename):
    return "s3a://{}/{}/{}".format(
        os.environ['S3_BUCKET'], os.environ['S3_PREFIX'], filename)


def http_url(filename):
    return "http://{}.s3.amazonaws.com/{}/{}".format(
        os.environ['S3_BUCKET'], os.environ['S3_PREFIX'], filename)


def get_credentials():
    return _get_session().get_credentials()


def upload_file(file_path):
    basename = os.path.basename(file_path)
    log.info('Uploading {} => {} ...'.format(file_path, http_url(basename)))
    with open(file_path, 'rb') as file_obj:
        response = _get_conn().put_object(
            ACL='public-read',
            Bucket=os.environ['S3_BUCKET'],
            ContentType=_get_content_type(basename),
            Key=_path(basename),
            Body=file_obj)
    log.info('Uploaded {}, response: {}'.format(file_path, response))


def list(prefix):
    path = _path(prefix)
    log.info('Getting list for {} => {} ...'.format(prefix, path))
    response = _get_conn().list_objects_v2(
        Bucket=os.environ['S3_BUCKET'],
        Prefix=path)
    log.info('List for {} => {}: {}'.format(prefix, path, response))
    return [obj['Key'] for obj in response['Contents']]


__sess = None
def _get_session():
    global __sess
    if __sess is None:
        # Fetches credentials automatically:
        __sess = botocore.session.get_session()
    return __sess


__conn = None
def _get_conn():
    global __conn
    if __conn is None:
        __conn = _get_session().create_client('s3')
    return __conn


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
