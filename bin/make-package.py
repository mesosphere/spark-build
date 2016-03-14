#!/usr/bin/env python

import json
import os
import shutil
import sys

def main():
    with open("manifest.json") as f:
        manifest = json.load(f)

    try:
        os.mkdir('build/package')
    except OSError:
        pass

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
