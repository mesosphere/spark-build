import os
import sys
from random import random
from operator import add

from pyspark.sql import SparkSession

def check_secret(secret_name, secret_content):
    '''
    Make sure the extra secret envvar and secret file show up in driver.
    '''
    envvar_content = os.environ.get(secret_name)
    if envvar_content != secret_content:
        print("Unexpected contents in secret envvar, found: {} expected: {}".format(envvar_content, secret_content))
        exit(1)

    file_content = open(secret_name, 'r').read()
    if file_content != secret_content:
        print("Unexpected contents in secret file, found: {} expected: {}".format(file_content, secret_content))
        exit(1)


if __name__ == "__main__":
    """
        Usage: pi [partitions] [secret] [secret content]
        Checks for the given env-based and file-based driver secret.
        Then calculates the value of pi.
    """

    check_secret(sys.argv[2], sys.argv[3])

    spark = SparkSession \
        .builder \
        .appName("PythonPi") \
        .getOrCreate()

    partitions = int(sys.argv[1])
    n = 100000 * partitions

    def f(_):
        x = random() * 2 - 1
        y = random() * 2 - 1
        return 1 if x ** 2 + y ** 2 < 1 else 0

    count = spark.sparkContext.parallelize(range(1, n + 1), partitions).map(f).reduce(add)
    print("Pi is roughly %f" % (4.0 * count / n))

    spark.stop()
