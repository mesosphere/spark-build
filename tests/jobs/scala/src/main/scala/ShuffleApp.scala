import org.apache.spark.sql.SparkSession

import scala.util.Random

/**
  * This is a slight modification of GroupByTest from Spark Examples but with a deterministic
  * sequential key generation which doesn't rely on random number generator.
  *
  * Usage: ShuffleApp [numMappers] [numKeys] [valueSize] [numReducers] [sleepBeforeShutdown]
  */
object ShuffleApp {
  def main(args: Array[String]): Unit = {
    val spark = SparkSession
      .builder
      .appName("Shuffle Test")
      .getOrCreate()

    val numMappers = if (args.length > 0) args(0).toInt else 2
    val numKeys = if (args.length > 1) args(1).toInt else 1000
    val valSize = if (args.length > 2) args(2).toInt else 1000
    val numReducers = if (args.length > 3) args(3).toInt else numMappers
    val sleepBeforeShutdownMillis = if (args.length > 4) args(4).toLong * 1000 else 0

    val keyPairs = spark.sparkContext.parallelize(0 until numMappers, numMappers).flatMap { _ =>
      val random = new Random
      val result = new Array[(Int, Array[Byte])](numKeys)

      //each partition will contain a full copy of keys to enforce shuffle
      for (i <- 0 until numKeys) {
        val byteArr = new Array[Byte](valSize)
        random.nextBytes(byteArr)
        result(i) = (i, byteArr)
      }
      result
    }.cache()
    keyPairs.count()

    println(
      s"""
         |RDD contents sample:
         | ${keyPairs.take(10).mkString(", ")}
       """.stripMargin)

    val groupsCount = keyPairs.groupByKey(numReducers).count()
    println(s"Groups count: $groupsCount")
    Thread.sleep(sleepBeforeShutdownMillis)
    spark.stop()
  }
}
