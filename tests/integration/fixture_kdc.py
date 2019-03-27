import itertools
import pytest
import sdk_auth
import sdk_hosts

from tests.integration.fixture_hdfs import HDFS_SERVICE_NAME, GENERIC_HDFS_USER_PRINCIPAL, ALICE_PRINCIPAL
from tests.integration.fixture_kafka import KAFKA_SERVICE_NAME


@pytest.fixture(scope='package')
def kerberos_env():
    try:
        kafka_principals = build_kafka_principals()
        hdfs_principals = build_hdfs_principals()

        kerberos_env = sdk_auth.KerberosEnvironment(persist=True)
        kerberos_env.add_principals(kafka_principals + hdfs_principals)
        kerberos_env.finalize()
        yield kerberos_env

    finally:
        kerberos_env.cleanup()


def build_kafka_principals():
    fqdn = "{service_name}.{host_suffix}".format(service_name=KAFKA_SERVICE_NAME,
                                                 host_suffix=sdk_hosts.AUTOIP_HOST_SUFFIX)

    brokers = ["kafka-0-broker", "kafka-1-broker", "kafka-2-broker"]

    principals = []
    for b in brokers:
        principals.append("kafka/{instance}.{domain}@{realm}".format(
            instance=b,
            domain=fqdn,
            realm=sdk_auth.REALM))

    principals.append("client@{realm}".format(realm=sdk_auth.REALM))
    return principals


def build_hdfs_principals():
    primaries = ["hdfs", "HTTP"]
    fqdn = "{service_name}.{host_suffix}".format(service_name=HDFS_SERVICE_NAME,
                                                 host_suffix=sdk_hosts.AUTOIP_HOST_SUFFIX)
    instances = [
        "name-0-node",
        "name-0-zkfc",
        "name-1-node",
        "name-1-zkfc",
        "journal-0-node",
        "journal-1-node",
        "journal-2-node",
        "data-0-node",
        "data-1-node",
        "data-2-node",
    ]
    principals = []
    for (instance, primary) in itertools.product(instances, primaries):
        principals.append(
            "{primary}/{instance}.{fqdn}@{REALM}".format(
                primary=primary,
                instance=instance,
                fqdn=fqdn,
                REALM=sdk_auth.REALM
            )
        )
    principals.append(GENERIC_HDFS_USER_PRINCIPAL)
    principals.append(ALICE_PRINCIPAL)
    return principals


@pytest.fixture(scope='package')
def kerberos_options(kerberos_env):
    return {
        "kerberos": {
            "enabled": True,
            "kdc": {
                "hostname": kerberos_env.get_host(),
                "port": int(kerberos_env.get_port())
            },
            "keytab_secret": kerberos_env.get_keytab_path(),
            "realm": kerberos_env.get_realm()
        }
    }
