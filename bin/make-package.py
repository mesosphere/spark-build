#!/usr/bin/env python

import json
import os
import shutil
import sys

def main():
    try:
        os.mkdir('build/package')
    except OSError:
        pass

    with open("manifest.json") as f:
        manifest = json.load(f)

    if os.getenv("DOCKER_IMAGE") is None:
        raise ValueError("DOCKER_IMAGE is a required env var.")
    else:
        manifest['docker_image'] = os.getenv("DOCKER_IMAGE")

    if os.getenv("PACKAGE_VERSION") is not None:
        manifest["version"] = os.getenv("PACKAGE_VERSION")

    # write template vars
    template_filenames = ['package/package.json',
                          'package/command.json',
                          'package/marathon.json.mustache',
                          'package/config.json',
                          'package/resource.json']

    for template_filename in template_filenames:
        with open(template_filename) as template_file, \
             open('build/{}'.format(template_filename), 'w') as output_file:
            template = template_file.read()
            for key, value in manifest.items():
                template = template.replace('${}'.format(key), value)

            output_file.write(template)

    print("Package built successfully.")


if __name__ == '__main__':
    main()
