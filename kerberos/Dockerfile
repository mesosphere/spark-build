FROM ubuntu:14.04
MAINTAINER Dr. Stefan Schimanski <sttts@mesosphere.io>

RUN apt-get -y update

RUN echo package heimdal/realm string LOCAL | debconf-set-selections
RUN apt-get -y install python
RUN apt-get -y install heimdal-kdc
RUN apt-get -y install libsasl2-modules-gssapi-heimdal

EXPOSE	88

ADD krb5.conf.template /etc/krb5.conf.template
ADD run.sh /run.sh

RUN mkdir /export
VOLUME /export

ENV REALM_NAME LOCAL
ENV DOMAIN_NAME local

CMD ["/run.sh"]
