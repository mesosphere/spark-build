import org.apache.spark.sql.SparkSession

/**
  * MockTaskRunner creates a number of noop Spark tasks specified by 'numTasks' each of which
  * sleeps for 'taskDurationSec'. The main goal of this class is to mimic long-running Spark
  * applications (i.e. Spark Streaming) for the testing and troubleshooting purposes.
  *
  * Usage: MockTaskRunner [numTasks] [taskDurationSec]
  */
object MockTaskRunner {
  def main(args: Array[String]): Unit = {
    if (args.length < 2) {
      println("Usage: MockTaskRunner [numTasks] [taskDurationSec]")
      System.exit(1)
    }

    val spark = SparkSession
      .builder
      .appName("MockTaskRunner")
      .getOrCreate()

    val numTasks = args(0).toInt
    val sleepSeconds = args(1).toLong
    val sleepMillis = sleepSeconds * 1000

    spark.sparkContext.parallelize(0 until numTasks, numTasks).foreachPartition{_ =>
      println(s"Sleeping for $sleepSeconds seconds")
      Thread.sleep(sleepMillis)
      println(s"Sleep finished")
    }

    spark.stop()
  }
}
