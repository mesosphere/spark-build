from __future__ import print_function
import sys
from random import getrandbits
from time import sleep

from pyspark.sql import SparkSession

# ShuffleApp test job ported from Scala to Python

if __name__ == "__main__":
    spark = SparkSession \
        .builder \
        .appName("Shuffle Test") \
        .getOrCreate()

    num_mappers = int(sys.argv[1]) if len(sys.argv) > 1 else 2
    num_keys = int(sys.argv[2]) if len(sys.argv) > 2 else 1000
    val_size = int(sys.argv[3]) if len(sys.argv) > 3 else 1000
    num_reducers = int(sys.argv[4]) if len(sys.argv) > 4 else num_mappers
    sleep_before_shutdown_millis = int(sys.argv[5]) if len(sys.argv) > 5 else 0

    def f(_):
        result = []
        for i in range(num_keys):
            arr = bytearray(getrandbits(8) for j in range(val_size))
            result.append((i, arr))
        return result

    key_pairs = spark.sparkContext.parallelize(range(0, num_mappers), num_mappers).flatMap(f).cache()
    key_pairs.count()

    print("RDD content sample: {}".format(key_pairs.take(10)))

    groups_count = key_pairs.groupByKey(num_reducers).count()
    print("Groups count: {}".format(groups_count))

    if sleep_before_shutdown_millis > 0:
        sleep(sleep_before_shutdown_millis / 1000)

    spark.stop()
