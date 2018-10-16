#!/bin/bash

set -e

SPARK_DIST_DIR=""
HADOOP_VERSION="2.6"
DOCKER_DIST_IMAGE=""
REBUILD_DOCKER=false
REBUILD_SPARK=false
PRINT_HELP=false

SCRIPT_NAME=`basename "$0"`

print_help () {
  echo "Usage: ${SCRIPT_NAME} [<options>...]"
  echo "Options:"
  echo "--spark-dist-dir <absolute path>  Mandatory. Absolute path to Spark project sources used to build and/or upload Spark archive"
  echo "--hadoop-version <version>        Optional. Hadoop version to build Spark with. Default: ${HADOOP_VERSION}"
  echo "--docker-dist-image <image tag>   Optional. Target Docker image to publish. Default: mesosphere/spark-dev:<git commit sha>"
  echo "--rebuild-docker                  If Docker image should be rebuilt. Default: ${REBUILD_DOCKER}"
  echo "--rebuild-spark                   If Spark distribution should be rebuilt. Default: ${REBUILD_SPARK}"
  echo "--help                            Print this message"
}

set_args () {
  for arg in "$@"; do
    case "$arg" in
      ("--spark-dist-dir")
        shift
        SPARK_DIST_DIR=$1
        ;;
      ("--hadoop-version")
        shift
        HADOOP_VERSION=$1
        ;;
      ("--docker-dist-image")
        shift
        DOCKER_DIST_IMAGE=$1
        ;;
      ("--hadoop-version")
        shift
        HADOOP_VERSION=$1
        ;;
      ("--rebuild-docker")
        REBUILD_DOCKER=true
        ;;
      ("--rebuild-spark")
        REBUILD_SPARK=true
        ;;
      ("-h" | "--help")
        PRINT_HELP=true
        ;;
    esac
  done
}

build_spark_distibution () {
  pushd ${SPARK_DIST_DIR}
  ./dev/make-distribution.sh --tgz -Pmesos "-Phadoop-${HADOOP_VERSION}" -Pnetlib-lgpl -Psparkr -Phive -Phive-thriftserver -DskipTests
  popd
}

set_args "$@"

if [ "${PRINT_HELP}" = true ]; then
  print_help
  exit 0
fi

if [ -z "${SPARK_DIST_DIR}" ]; then
  printf "Please specify '--spark-dist-dir'\n\n"
  print_help
  exit 1
fi

echo "Running: ${SCRIPT_NAME} $@"

if [ "${REBUILD_DOCKER}" = true ]; then
  echo "Rebuilding base Docker image used for publishing"
  make docker-build
  export DOCKER_BUILD_IMAGE=`cat docker-build`
else
  docker pull mesosphere/spark-build:latest
  echo mesosphere/spark-build:latest > docker-build
fi

if [ -z $"{REBUILD_SPARK}" ]; then
  echo "Script launched with '--rebuild-spark' flag. Rebuilding Spark distribution."
  build_spark_distibution
fi

SPARK_BUILDS=`ls -1 ${SPARK_DIST_DIR}/spark-*.tgz 2>/dev/null | wc -l`
if [ ${SPARK_BUILDS} == 0 ]; then
  echo "Spark distribution archive is missing. Script will run ${SPARK_DIST_DIR}/dev/make-distribution.sh"
  build_spark_distibution
fi

SPARK_DIST=`ls ${SPARK_DIST_DIR}/spark-*.tgz`
echo "Using Spark Distribution: ${SPARK_DIST}"
mkdir -p build/dist
cp ${SPARK_DIST} build/dist

echo "Building stub universe and Uploading Spark Distribution to it"
DOCKER_DIST_IMAGE=${DOCKER_DIST_IMAGE} make stub-universe-url