import itertools
import json
import logging
import os
import sys
import typing

import sdk_install
import sdk_security
import sdk_utils


log = logging.getLogger(__name__)


def setup_security(service_name: str, linux_user: str) -> typing.Dict:
    """
    Adds a service account and secret for the specified service name.
    """
    if not sdk_utils.is_strict_mode():
        return {}

    service_account = normalize_string("{}-service-account".format(service_name))
    service_account_secret = "{}-service-account-secret".format(service_name)
    return sdk_security.setup_security(service_name,
                                       linux_user,
                                       service_account, service_account_secret)


def get_strict_mode_options(service_account_info: typing.Dict) -> typing.Dict:

    options = {}

    if "linux_user" in service_account_info:
        user_options = {
            "service": {
                "user": service_account_info["linux_user"]
            }

        }
        options = sdk_install.merge_dictionaries(options, user_options)


    if sdk_utils.is_strict_mode():
        service_account_options = {
            'service': {
                'service_account': service_account_info["name"],
                'service_account_secret': service_account_info["secret"],
            }
        }
        options = sdk_install.merge_dictionaries(options, service_account_options)

    return options


def get_service_options(service_name: str, service_account_info: typing.Dict,
                        options: typing.Dict, config_path: str) -> typing.Dict:
    """
    Get the options for a service as a combination of other options.
    """

    config_options = {}
    if config_path:
        if os.path.isfile(config_path):
            with open(config_path, 'r') as fp:
                log.info("Reading options from %s", config_path)
                config_options = json.load(fp)
        else:
            log.error("Specified options file does not exits: %s", config_path)
            sys.exit(1)
    else:
        log.info("No options specified. Using defaults")

    # Always set the service name
    service_name_options = {"service": {"name": service_name}}

    return merge_service_options([get_strict_mode_options(service_account_info),
                                  options,
                                  config_options,
                                  service_name_options, ])


def merge_service_options(options: typing.List[typing.Dict]) -> typing.Dict:
    """
    Merge the specified service options with the options later in the list taking precedence.
    """

    result = {}
    for o in options:
        result = sdk_install.merge_dictionaries(result, o)

    return result


# https://github.com/pytoolz/toolz/blob/c3a62944ea9502396f24ac68d3c70d954a368c9e/toolz/itertoolz.py#L468
def concat(seqs):
    """ Concatenate zero or more iterables, any of which may be infinite.
    An infinite sequence will prevent the rest of the arguments from
    being included.
    We use chain.from_iterable rather than ``chain(*seqs)`` so that seqs
    can be a generator.
    >>> list(concat([[], [1], [2, 3]]))
    [1, 2, 3]
    See also:
        itertools.chain.from_iterable  equivalent
    """
    return itertools.chain.from_iterable(seqs)


# https://github.com/pytoolz/toolz/blob/c3a62944ea9502396f24ac68d3c70d954a368c9e/toolz/itertoolz.py#L498
def mapcat(func, seqs):
    """ Apply func to each sequence in seqs, concatenating results.
    >>> list(mapcat(lambda s: [c.upper() for c in s],
    ...             [["a", "b"], ["c", "d", "e"]]))
    ['A', 'B', 'C', 'D', 'E']
    """
    return concat(map(func, seqs))


def normalize_string(s: str) -> str:
    return s.replace("/", "__").replace('-', '_')


def make_repeater(n):
    """Returns a lambda that returns a list (an iterable really) of `n` `x`s.

    >>> repeat_3 = make_repeater(3)
    >>> list(repeat_3('foo'))
    ['foo', 'foo', 'foo']
    >>> list(make_repeater(2)('bar'))
    ['bar', 'bar']
    """
    return lambda x: itertools.repeat(x, n)
