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
    val durationSeconds = args(1).toLong
    val durationMillis = durationSeconds * 1000

    spark.sparkContext.parallelize(0 until numTasks, numTasks).foreachPartition{_ =>
      val finishTime = System.currentTimeMillis + durationMillis
      println(s"Working for $durationSeconds seconds")

      while (System.currentTimeMillis < finishTime) {
        if (System.currentTimeMillis() % 1000 == 0) {
          Thread.sleep(1)
        }
      }

      println("Work finished")
    }

    spark.stop()
  }
}
