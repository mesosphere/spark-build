import logging
import os
import pytest
import spark_utils as utils


log = logging.getLogger(__name__)
THIS_DIR = os.path.dirname(os.path.abspath(__file__))
SMOKE_TEST_SPARK_DOCKER_IMAGES = os.getenv('SMOKE_TEST_SPARK_DOCKER_IMAGES', '')


@pytest.mark.sanity
@pytest.mark.smoke
def test_spark_docker_images():
    if not SMOKE_TEST_SPARK_DOCKER_IMAGES:
        pytest.skip("A list of spark distribution images are required for this test")

    docker_images = SMOKE_TEST_SPARK_DOCKER_IMAGES.split(',')

    log.info("Testing the following docker images: ")
    for image in docker_images:
        log.info(" - " + image)

    for image in docker_images:
        log.info("Running a smoke test with " + image)
        _test_spark_docker_image(image)


def _test_spark_docker_image(docker_image):
    utils.upload_dcos_test_jar()
    utils.require_spark(additional_options={'service': {'docker-image': docker_image}})

    expected_groups_count = 12000
    num_mappers = 4
    value_size_bytes = 100
    num_reducers = 4
    sleep = 500

    python_script_path = os.path.join(THIS_DIR, 'jobs', 'python', 'shuffle_app.py')
    python_script_url = utils.upload_file(python_script_path)
    utils.run_tests(app_url=python_script_url,
                    app_args="{} {} {} {} {}".format(num_mappers, expected_groups_count, value_size_bytes, num_reducers, sleep),
                    expected_output="Groups count: {}".format(expected_groups_count),
                    args=["--conf spark.executor.cores=1",
                          "--conf spark.cores.max=4",
                          "--conf spark.scheduler.minRegisteredResourcesRatio=1",
                          "--conf spark.scheduler.maxRegisteredResourcesWaitingTime=3m"])

    utils.teardown_spark()
