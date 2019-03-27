"""
Authnz specifics for HDFS tests
"""
import logging
import base64


log = logging.getLogger(__name__)


USERS = [
    "hdfs",
    "alice",
    "bob",
]


def get_principal_to_user_mapping() -> str:
    """
    Kerberized HDFS maps the primary component of a principal to local users, so
    we need to create an appropriate mapping to test authorization functionality.
    :return: A base64-encoded string of principal->user mappings
    """
    rules = [
        "RULE:[2:$1@$0](^hdfs@.*$)s/.*/hdfs/",
        "RULE:[1:$1@$0](^nobody@.*$)s/.*/nobody/"
    ]

    for user in USERS:
        rules.append("RULE:[1:$1@$0](^{user}@.*$)s/.*/{user}/".format(user=user))

    return base64.b64encode('\n'.join(rules).encode("utf-8")).decode("utf-8")
