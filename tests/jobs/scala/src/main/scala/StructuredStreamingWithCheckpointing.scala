import org.apache.spark.sql.SparkSession

/**
  * Sample Spark Structured Streaming application that consumes data from Kafka (Kerberos supported)
  * and outputs count of unique message bodies parsed as Strings to STDOUT
  */
object StructuredStreamingWithCheckpointing {
  def main(args: Array[String]): Unit = {

    println("Starting Kafka Structured Streaming Application")
    println("Creating Spark Context")
    val spark = SparkSession
      .builder
      .appName("StructuredStreamingWithCheckpointing")
      .getOrCreate()

    println("Spark Context Created")

    spark.sparkContext.setLogLevel("DEBUG")

    import spark.implicits._

    println(s"args.length: ${args.length}, args:")
    args.foreach(println)
    println()

    var dataStreamReader = spark
      .readStream
      .format("kafka")
      .option("kafka.bootstrap.servers", args(0))
      .option("kafka.session.timeout.ms", 10000)
      .option("kafka.max.poll.records", 500)
      .option("subscribe", args(1))
      .option("startingOffsets", "earliest")
      .option("checkpointLocation", args(2))

    if (args.length == 4 && args(3).nonEmpty){
      println(s"kafka.security.protocol: ${args(3)}")
      dataStreamReader = dataStreamReader.option("kafka.security.protocol", args(3))
    } else {
      println("kafka.security.protocol is not specified")
    }

    val query = dataStreamReader
      .load()
      .selectExpr("CAST(value AS STRING)")
      .as[String]
      .groupBy("value")
      .count()
      .writeStream
      .option("checkpointLocation", args(2))
      .outputMode("complete")
      .format("console")
      .start()

    query.awaitTermination()
  }
}
