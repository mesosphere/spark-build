#!/usr/bin/python

import json
import os
import shutil
import sys

def main():
    with open("conf/pkg_config.json") as f:
        pkg_config = json.load(f)

        # package.json version
        version = pkg_config['version']

        # marathon.json container.docker.image
        docker_image = pkg_config['docker_image']

        # command.json pip[.]
        python_package = pkg_config['python_package']

        # config.json properties.spark.properties.uri.default
        spark_dist = pkg_config['spark_dist']

    try:
        os.mkdir('build')
    except OSError:
        pass

    try:
        os.mkdir('build/package')
    except OSError:
        pass

    with open('build/package/command.json', 'w') as command_outfile:
        command = {'pip': [python_package]}
        json.dump(command, command_outfile, indent=2)
        command_outfile.write('\n')

    with open('package/package.json') as package_infile, \
         open('build/package/package.json', 'w') as package_outfile:
        package = json.load(package_infile)
        package['version'] = version
        json.dump(package, package_outfile, indent=2)
        package_outfile.write('\n')

    with open() as marathon_infile, \
         open('build/package/marathon.json', 'w') as marathon_outfile:
        marathon = marathon_infile.read()
        marathon = marathon.replace('$docker_image', '"{}"'.format(docker_image))
        marathon_outfile.write(marathon)
        marathon_outfile.write('\n')

    with open('package/config.json') as config_infile, \
         open('build/package/config.json', 'w') as config_outfile:
        config = config_infile.read()
        config = config.replace('$spark_dist', spark_dist)
        config_outfile.write(config)
        config_outfile.write('\n')


if __name__ == '__main__':
    main()
