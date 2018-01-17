---
layout: layout.pug
navigationTitle: 
excerpt:
title: Custom Docker Images
menuWeight: 95
featureMaturity:

---

**Note:** Customizing the Spark image Mesosphere provides is supported. However, customizations have the potential to adversely affect the integration between Spark and DC/OS. In situations where Mesosphere support suspects a customization may be adversely impacting Spark with DC/OS, Mesosphere support may request that the customer reproduce the issue with an unmodified
Spark image.

You can customize the Docker image in which Spark runs by extending the standard Spark Docker image. In this way, you can install your own libraries, such as a custom Python library.

1. In your Dockerfile, extend from the standard Spark image and add your customizations:

    ```
    FROM mesosphere/spark:1.0.4-2.0.1
    RUN apt-get install -y python-pip
    RUN pip install requests
    ```

1. Then, build an image from your Dockerfile.

        docker build -t username/image:tag .
        docker push username/image:tag

1. Reference your custom Docker image with the `--docker-image` option when running a Spark job.

        dcos spark run --docker-image=myusername/myimage:v1 --submit-args="http://external.website/mysparkapp.py 30"
