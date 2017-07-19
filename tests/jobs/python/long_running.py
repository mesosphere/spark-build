from __future__ import print_function


import sys
import time
from pyspark.sql import SparkSession


if __name__ == "__main__":
    """
        Usage: long_running [partitions] [run_time_sec]
    """
    partitions = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    run_time_sec = int(sys.argv[2]) if len(sys.argv) > 2 else 600

    spark = SparkSession \
        .builder \
        .appName("Long-Running Spark Job") \
        .getOrCreate()

    n = 100000 * partitions
    data = spark.sparkContext.parallelize(range(1, n + 1), partitions)

    def processPartition(partition):
        """Sleep for run_time_sec"""
        print('Start processing partition')
        time.sleep(run_time_sec)
        print('Done processing partition')

    data.foreachPartition(processPartition)
    print('Job completed successfully')

    spark.stop()
