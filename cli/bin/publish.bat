set VERSION=%GIT_TAG_NAME%
set PLATFORM=windows-x86-64

pip install awscli
echo version = '%VERSION%' > dcos_spark/version.py
make clean env binary
aws s3 cp dist/dcos-spark.exe s3://downloads.mesosphere.io/spark/assets/cli/%GIT_TAG_NAME%/%PLATFORM%/dcos-spark.exe
