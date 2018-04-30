import shakedown
import sys


# This script will deploy the specified number of dispatchers with an optional
# options json file. It will take the given base service name and
# append an index to generate a unique service name for each dispatcher.
#
# The service names of the deployed dispatchers will be written into an output
# file.
#
# Running:
# > dcos cluster setup <cluster url>
# > python deploy-dispatchers.py 2 spark-instance dispatchers.out


SPARK_PACKAGE_NAME="spark"


#TODO: add options json file contents
def deploy_dispatchers(num_dispatchers, service_name_base, output_file, options_json_file):
    with open(output_file, "w") as outfile:
        for i in range(0, num_dispatchers):
            service_name = "{}-{}".format(service_name_base, str(i))
            options = {}
            options["service"] = options.get("service", {})
            options["service"]["name"] = service_name

            options["service"]["UCR_containerizer"] = True
            options["service"]["docker-image"] = "mesosphere/spark-dev:931ca56273af913d103718376e2fbc04be7cbde0"

            shakedown.install_package(
                SPARK_PACKAGE_NAME,
                options_json=options)
            outfile.write("{}\n".format(service_name))


if __name__ == "__main__":
    """
        Usage: python deploy-dispatchers.py [num_dispatchers] [service_name_base] [output_file] (options_json_file)
    """

    if len(sys.argv) < 4:
        print("Usage: deploy-dispatchers.py [num_dispatchers] [service_name_base] [output_file] (options_json_file)")
        sys.exit(2)

    num_dispatchers = int(sys.argv[1])
    service_name_base = sys.argv[2]
    output_file = sys.argv[3]
    options_json_file = sys.argv[4] if len(sys.argv) > 4 else None
    print("num_dispatchers: {}".format(num_dispatchers))
    print("service_name_base: {}".format(service_name_base))
    print("output_file: {}".format(output_file))
    print("options_json_file: {}".format(options_json_file))

    deploy_dispatchers(num_dispatchers, service_name_base, output_file, options_json_file)
