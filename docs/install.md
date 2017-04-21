---
post_title: Install and Customize
menu_order: 0
feature_maturity: stable
enterprise: 'no'
---

Spark is available in the Universe and can be installed by using either the web interface or the DC/OS CLI.

##  <a name="install-enterprise"></a>Prerequisites

- Depending on your security mode in Enterprise DC/OS, you may [need to provision a service account](https://docs.mesosphere.com/service-docs/spark/spark-auth/) before installing Spark. Only someone with `superuser` permission can create the service account.
	- `strict` [security mode](https://docs.mesosphere.com/1.9/installing/custom/configuration-parameters/#security) requires a service account.  
	- `permissive` security mode a service account is optional.
	- `disabled` security mode does not require a service account.

# Default Installation

To start a basic Spark cluster, run the following command on the DC/OS CLI.

    $ dcos package install spark

This command installs the dispatcher, and, optionally, the history server. See [Custom Installation][7] to install the history server.

Go to the **Services** > **Deployments** tab of the DC/OS web interface to monitor the deployment. Once it is
complete, visit Spark at `http://<dcos-url>/service/spark/`.

You can also [install Spark via the DC/OS web interface](https://docs.mesosphere.com/1.9/usage/webinterface/#universe).

**Note:** If you install Spark via the web interface, run the following command from the DC/OS CLI to install the Spark CLI:

    $ dcos package install spark --cli

<a name="custom"></a>

# Custom Installation

You can customize the default configuration properties by creating a JSON options file and passing it to `dcos package install --options`. For example, to install the history server, create a file called `options.json`:

    {
      "history-server": {
        "enabled": true
      }
    }

Then, install Spark with your custom configuration:

    $ dcos package install --options=options.json spark

Run the following command to see all configuration options:

    $ dcos package describe spark --config

## Customize Spark Distribution

DC/OS Spark does not support arbitrary Spark distributions, but Mesosphere does provide multiple pre-built distributions, primarily used to select Hadoop versions.  To use one of these distributions, first select your desired Spark distribution from [here](https://github.com/mesosphere/spark-build/blob/master/docs/spark-versions.md), then select the corresponding docker image from [here](https://hub.docker.com/r/mesosphere/spark/tags/), then use those values to set the following configuration variables:

    {
      "service": {
        "spark-dist-uri": "<spark-dist-uri>"
        "docker-image": "<docker-image>"
      }
    }

# Minimal Installation

For development purposes, you may wish to install Spark on a local DC/OS cluster. For this, you can use [dcos-vagrant][16].

1. Install DC/OS Vagrant:

	Install a minimal DC/OS Vagrant according to the instructions [here][16].

1. Install Spark:

        $ dcos package install spark

1. Run a simple Job:

        $ dcos spark run --submit-args="--class org.apache.spark.examples.SparkPi http://downloads.mesosphere.com.s3.amazonaws.com/assets/spark/spark-examples_2.10-1.5.0.jar"

NOTE: A limited resource environment such as DC/OS Vagrant restricts some of the features available in DC/OS Spark.  For example, unless you have enough resources to start up a 5-agent cluster, you will not be able to install DC/OS HDFS, and you thus won't be able to enable the history server.

Also, a limited resource environment can restrict how you size your executors, for example with `spark.executor.memory`.

# Multiple Installations

Installing multiple instances of the DC/OS Spark package provides basic multi-team support. Each dispatcher displays only the jobs submitted to it by a given team, and each team can be assigned different resources.

To install mutiple instances of the DC/OS Spark package, set each `service.name` to a unique name (e.g.: "spark-dev") in your JSON configuration file during installation:

    {
      "service": {
        "name": "spark-dev"
      }
    }

To use a specific Spark instance from the DC/OS Spark CLI:

    $ dcos config set spark.app_id <service.name>

 [7]: #custom
 [16]: https://github.com/mesosphere/dcos-vagrant
