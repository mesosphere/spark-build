#!/usr/bin/python

import json
import os
import shutil
import sys

def main():
    version = sys.argv[1]
    docker_image = sys.argv[2]
    python_package = sys.argv[3]

    try:
        os.mkdir('build')
    except OSError:
        pass

    try:
        os.mkdir('build/package')
    except OSError:
        pass

    shutil.copyfile('package/config.json', 'build/package/config.json')

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

    with open('package/marathon.json') as marathon_infile, \
         open('build/package/marathon.json', 'w') as marathon_outfile:
        marathon = marathon_infile.read()
        marathon = marathon.replace('$docker_image', '"{}"'.format(docker_image))
        marathon_outfile.write(marathon)
        marathon_outfile.write('\n')


if __name__ == '__main__':
    main()
