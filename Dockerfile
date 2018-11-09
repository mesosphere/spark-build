FROM ubuntu:18.04
RUN apt-get update && apt-get install -y \
    bc \
    curl \
    default-jdk \
    gfortran \
    git \
    jq \
    libbz2-dev \
    liblzma-dev \
    libcurl4-openssl-dev \
    libpcre++-dev \
    libssl-dev \
    python-pip \
    python3 \
    python3-dev \
    python3-pip \
    python3-venv \
    python-software-properties \
    software-properties-common \
    wget \
    zip && \
    rm -rf /var/lib/apt/lists/*
# install go 1.7
RUN add-apt-repository -y ppa:longsleep/golang-backports && apt-get update && apt-get install -y golang-go
# AWS CLI for uploading build artifacts
RUN pip install awscli
# Install dcos-launch to create clusters for integration testing
RUN apt-get install -y python3-venv
RUN wget https://downloads.dcos.io/dcos-launch/bin/linux/dcos-launch -O /usr/bin/dcos-launch
RUN chmod +x /usr/bin/dcos-launch
# shakedown and dcos-cli require this to output cleanly
ENV LC_ALL=C.UTF-8
ENV LANG=C.UTF-8
# use an arbitrary path for temporary build artifacts
ENV GOPATH=/go-tmp

# Build R
ENV R_VERSION=3.4.0
ENV R_TGZ=R-${R_VERSION}.tar.gz
RUN export PATH=/root/packages/bin:$PATH \
  && cd /tmp \
  && wget https://cran.r-project.org/src/base/R-3/${R_TGZ} \
  && tar xf ${R_TGZ} \
  && cd R-${R_VERSION}/ \
  && ./configure --with-readline=no --with-x=no CPPFLAGS="-I/root/packages/include" LDFLAGS="-L/root/packages/lib" \
  && make \
  && make install

RUN apt-get update && apt-get install -y apt-transport-https \
  && echo "deb https://dl.bintray.com/sbt/debian /" | tee -a /etc/apt/sources.list.d/sbt.list \
  && apt-key adv --keyserver hkp://keyserver.ubuntu.com:80 --recv 2EE0EA64E40A89B84B2DF73499E82A75642AC823 \
  && apt-get update \
  && apt-get install -y sbt \
  && rm -rf /var/lib/apt/lists/*
