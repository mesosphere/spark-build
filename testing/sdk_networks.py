'''
************************************************************************
FOR THE TIME BEING WHATEVER MODIFICATIONS ARE APPLIED TO THIS FILE
SHOULD ALSO BE APPLIED TO sdk_networks IN ANY OTHER PARTNER REPOS
************************************************************************
'''
import logging
import shakedown
import sdk_cmd

log = logging.getLogger(__name__)

ENABLE_VIRTUAL_NETWORKS_OPTIONS = {'service': {'virtual_network_enabled': True}}


def check_task_network(task_name, expected_network_name="dcos"):
    """Tests whether a task (and it's parent pod) is on a given network
    """
    _task = shakedown.get_task(task_id=task_name, completed=False)

    assert _task is not None, "Unable to find task named {}".format(task_name)
    if type(_task) == list or type(_task) == tuple:
        assert len(_task) == 1, "Found too many tasks matching {}, got {}"\
            .format(task_name, _task)
        _task = _task[0]

    for status in _task["statuses"]:
        if status["state"] == "TASK_RUNNING":
            for network_info in status["container_status"]["network_infos"]:
                if expected_network_name is not None:
                    assert "name" in network_info, \
                        "Didn't find network name in NetworkInfo for task {task} with " \
                        "status:{status}".format(task=task_name, status=status)
                    assert network_info["name"] == expected_network_name, \
                        "Expected network name:{expected} found:{observed}" \
                        .format(expected=expected_network_name, observed=network_info["name"])
                else:
                    assert "name" not in network_info, \
                        "Task {task} has network name when it shouldn't has status:{status}" \
                        .format(task=task_name, status=status)


def get_and_test_endpoints(package_name, service_name, endpoint_to_get, correct_count):
    """Gets the endpoints for a service or the specified 'endpoint_to_get' similar to running
    $ docs <service> endpoints
    or
    $ dcos <service> endpoints <endpoint_to_get>
    Checks that there is the correct number of endpoints"""
    endpoints = sdk_cmd.svc_cli(package_name, service_name, "endpoints {}".format(endpoint_to_get), json=True)
    assert len(endpoints) == correct_count, "Wrong number of endpoints, got {} should be {}" \
        .format(len(endpoints), correct_count)
    return endpoints


def check_endpoints_on_overlay(endpoints):
    def check_ip_addresses_on_overlay():
        # the overlay IP address should not contain any agent IPs
        return len(set(ip_addresses).intersection(set(shakedown.get_agents()))) == 0

    assert "address" in endpoints, "endpoints: {} missing 'address' key".format(endpoints)
    assert "dns" in endpoints, "endpoints: {} missing 'dns' key".format(endpoints)

    # endpoints should have the format <ip_address>:port
    ip_addresses = [e.split(":")[0] for e in endpoints["address"]]
    assert check_ip_addresses_on_overlay(), \
        "IP addresses for this service should not contain agent IPs, IPs were {}".format(ip_addresses)

    for dns in endpoints["dns"]:
        assert "autoip.dcos.thisdcos.directory" in dns, \
            "DNS {} is incorrect should have autoip.dcos.thisdcos.directory".format(dns)


def get_task_host(task):
    agent_id = task['slave_id']
    log.info("Retrieving agents information for {}".format(agent_id))
    agents = sdk_cmd.cluster_request("GET", "/mesos/slaves?slave_id={}".format(agent_id)).json()
    assert len(agents['slaves']) == 1, "Agent's details do not match the expectations for agent ID {}".format(agent_id)
    return agents['slaves'][0]['hostname']


def get_task_ip(task):
    task_running_status = None
    for status in task['statuses']:
        if status['state'] == "TASK_RUNNING":
            task_running_status = status
            break

    assert task_running_status is not None, "No TASK_RUNNING status found for task: {}".format(task)

    ip_address = task_running_status['container_status']['network_infos'][0]['ip_addresses'][0]['ip_address']
    assert ip_address is not None and ip_address, \
        "Running task IP address is not defined for task status: {}".format(task_running_status)
    return ip_address


def get_overlay_subnet(network_name='dcos'):
    subnet = None
    network_info = sdk_cmd.cluster_request("GET", "/mesos/overlay-master/state").json()
    for network in network_info['network']['overlays']:
        if network['name'] == network_name:
            subnet = network['subnet']
            break

    assert subnet is not None, "Unable to find subnet information for provided network name: {}".format(network_name)
    return subnet
