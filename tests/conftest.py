import pytest
import sdk_repository


@pytest.fixture(scope='session')
def configure_universe():
    yield from sdk_repository.universe_session()
