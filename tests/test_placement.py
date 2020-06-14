import logging

import pytest

import sdk_agents
import sdk_marathon
import spark_utils as utils

log = logging.getLogger(__name__)


@pytest.mark.sanity
def test_dispatcher_placement(configure_universe):
    constraint = ["hostname", "CLUSTER", sdk_agents.get_private_agents().pop()["hostname"]]
    service_name = "spark"
    log.info("Running test: service_name='{}', constraints=[[{}]]"
             .format(service_name, ','.join(constraint)))

    options = {
        "service": {
            "name": service_name,
            "constraints": [constraint]
        }
    }
    try:
        utils.require_spark(service_name=service_name, additional_options=options)

        dispatcher_host = sdk_marathon.get_scheduler_host(service_name)
        log.info("Dispatcher Host: {}".format(dispatcher_host))
        assert constraint[2] == dispatcher_host
    finally:
        utils.teardown_spark(service_name=service_name)
