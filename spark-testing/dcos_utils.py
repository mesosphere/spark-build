import sdk_cmd


def get_task_container_id(task):
    for status in task['statuses']:
        if status['state'] == "TASK_RUNNING":
            return status['container_status']['container_id']['value']

    return None


def agent_ssh(host_ip, cmd):
    ssh_options = f"--user={sdk_cmd.LINUX_USER} " \
                  f"--option UserKnownHostsFile=/dev/null " \
                  f"--option StrictHostKeyChecking=no " \
                  f"--option LogLevel=QUIET"

    _, stdout, _ = sdk_cmd._run_cmd(
        f"LC_ALL=en_US.UTF-8 dcos node ssh --master-proxy --private-ip={host_ip} {ssh_options} \"{cmd}\"",
        print_output=False, check=False)
    return stdout


def delete_secret(secret: str) -> None:
    """
    Deletes a given secret.
    """
    # ignore any failures:
    sdk_cmd.run_cli("security secrets delete {}".format(secret))


def create_secret(secret: str, secret_value_or_filename: str, is_file: bool) -> None:
    """
    Creates secret of type file or value by given name
    """
    if is_file:
        sdk_cmd.run_cli("security secrets create -f {} {}".format(secret_value_or_filename, secret))
    else:
        sdk_cmd.run_cli("security secrets create -v {} {}".format(secret_value_or_filename, secret))


def get_framework_json(framework_name, completed=True):
    response = sdk_cmd.cluster_request("GET", "/mesos/frameworks").json()

    if completed:
        frameworks = sorted(response["completed_frameworks"], key=lambda x: x['unregistered_time'], reverse=True)
    else:
        frameworks = response["frameworks"]

    for framework in frameworks:
        if framework["name"] == framework_name:
            return framework

    raise AssertionError("Framework with name '{}' not found".format(framework_name))
