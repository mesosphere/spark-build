# TODO(mowsiany): the following image should match the version of scripts under
# /tests
FROM mesosphere/dcos-commons:latest
ADD requirements.txt /tmp/tests-requirements.txt
RUN pip3 install -r /tmp/tests-requirements.txt
ENV PYTHONPATH="/spark-build/testing:/spark-build/spark-testing"
WORKDIR /spark-build
