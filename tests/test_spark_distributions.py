import logging
import os
import pytest
import spark_utils as utils
import json
import requests


log = logging.getLogger(__name__)
THIS_DIR = os.path.dirname(os.path.abspath(__file__))
EXAMPLES_JAR_PATH_TEMPLATE = "https://infinity-artifacts.s3-us-west-2.amazonaws.com/spark/spark-examples_{}-2.4.3.jar"


@pytest.mark.sanity
@pytest.mark.smoke
def test_spark_docker_images():

    spark_dists = _read_dists_from_manifest()

    log.info("Testing docker distributions listed in manifest.json")

    # Making sure all listed docker images exist before running any tests
    for dist in spark_dists:
        if dist.get('image') and not _docker_image_exists(dist['image']):
            pytest.skip(f"Can't found image {dist['image']} listed in manifest.json in the registry")

    for dist in spark_dists:
        if dist.get('image'):
            log.info(f"Running a smoke test with {dist['image']}")
            _test_spark_docker_image(dist)


def _read_dists_from_manifest():
    with open(os.path.join(THIS_DIR, '..', 'manifest.json'), 'r') as file:
        manifest = json.load(file)
    return manifest['spark_dist']


def _docker_image_exists(image):
    log.info(f'Checking if image {image} exists in the registry')
    name, tag = image.split(':')
    r = requests.get(f"https://hub.docker.com/v2/repositories/{name}/tags/{tag}")
    return r.status_code == 200


def _test_spark_docker_image(dist):
    utils.require_spark(additional_options={'service': {'docker-image': dist['image']}})
    example_jar_url = EXAMPLES_JAR_PATH_TEMPLATE.format(dist['scala_version'])

    expected_groups_count = 12000
    num_mappers = 4
    value_size_bytes = 100
    num_reducers = 4

    utils.run_tests(app_url=example_jar_url,
                    app_args=f"{num_mappers} {expected_groups_count} {value_size_bytes} {num_reducers}",
                    expected_output=str(expected_groups_count),
                    args=["--class org.apache.spark.examples.GroupByTest",
                          "--conf spark.executor.cores=1",
                          "--conf spark.cores.max=4",
                          "--conf spark.scheduler.minRegisteredResourcesRatio=1",
                          "--conf spark.scheduler.maxRegisteredResourcesWaitingTime=3m"])

    utils.teardown_spark()

