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

    return sdk_cmd.run_cli(f"node ssh --master-proxy --private-ip={host_ip} {ssh_options} \"{cmd}\"",
                           print_output=False)
