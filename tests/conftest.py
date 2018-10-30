import pytest
import sdk_repository

pytest_plugins = [
    "tests.fixtures.hdfs",
    "tests.fixtures.kafka",
    "tests.fixtures.kdc"
]

@pytest.fixture(scope='session')
def configure_universe():
    yield from sdk_repository.universe_session()
