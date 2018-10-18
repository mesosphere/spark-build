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
  while [ -n "$1" ]; do
    case $1 in
      "--spark-dist-dir")
        shift
        SPARK_DIST_DIR=$1
        ;;
      "--hadoop-version")
        shift
        HADOOP_VERSION=$1
        ;;
      "--docker-dist-image")
        shift
        DOCKER_DIST_IMAGE=$1
        ;;
      "--hadoop-version")
        shift
        HADOOP_VERSION=$1
        ;;
      "--rebuild-docker")
        REBUILD_DOCKER=true
        ;;
      "--rebuild-spark")
        REBUILD_SPARK=true
        ;;
      "-h" | "--help")
        PRINT_HELP=true
        ;;
    esac
    shift
  done
}

build_spark_distibution () {
  pushd ${SPARK_DIST_DIR}
  ./dev/make-distribution.sh --tgz -Pmesos "-Phadoop-${HADOOP_VERSION}" -Pnetlib-lgpl -Psparkr -Phive -Phive-thriftserver -DskipTests
  popd
}

set_args "$@"

echo
echo "Running with parameters:"
echo "SPARK_DIST_DIR=$SPARK_DIST_DIR"
echo "HADOOP_VERSION=$HADOOP_VERSION"
echo "DOCKER_DIST_IMAGE=$DOCKER_DIST_IMAGE"
echo "REBUILD_DOCKER=$REBUILD_DOCKER"
echo "REBUILD_SPARK=$REBUILD_SPARK"
echo "PRINT_HELP=$PRINT_HELP"
echo

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

rm -rf build

if [ "${REBUILD_DOCKER}" = true ]; then
  echo "Rebuilding base Docker image used for publishing"
  make docker-build
  export DOCKER_BUILD_IMAGE=`cat docker-build`
else
  docker pull mesosphere/spark-build:latest
  echo mesosphere/spark-build:latest > docker-build
fi

if [ "${REBUILD_SPARK}" = true ]; then
  echo "Script launched with '--rebuild-spark' flag. Rebuilding Spark distribution."
  find ${SPARK_DIST_DIR} -name "spark-*.tgz" | xargs rm
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
if [ -n "${DOCKER_DIST_IMAGE}" ]; then
    export DOCKER_DIST_IMAGE=${DOCKER_DIST_IMAGE}
fi

make stub-universe-url
