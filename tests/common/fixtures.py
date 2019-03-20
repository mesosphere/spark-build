import pytest
import sdk_repository
import spark_utils as utils


@pytest.fixture(scope='session')
def configure_universe():
    yield from sdk_repository.universe_session()


@pytest.fixture(scope='session')
def configure_security_spark():
    yield from utils.spark_security_session()
