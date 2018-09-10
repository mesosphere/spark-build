import java.io.InputStream

import org.apache.spark.sql.{Row, SaveMode, SparkSession}

/**
  * Adapted from the spark hive example here:
  * https://github.com/apache/spark/blob/master/examples/src/main/scala/org/apache/spark/examples/sql/hive/SparkHiveExample.scala
  */
object HiveFull {
  case class Record(key: Int, value: String)

  def main(args: Array[String]): Unit = {

    if (args.length != 1) {
      Console.err.println(s"Need to pass the metastore uri: eg. thrift://<hostname>:9083")
      sys.exit(-1)
    }

    val stream : InputStream = getClass.getResourceAsStream("/kv1.txt")
    val lines = scala.io.Source.fromInputStream( stream ).getLines.toList

    lines.foreach(println)

    val spark = SparkSession
      .builder()
      .appName("Simple test with spark and hive integration")
      .config("hive.metastore.uris", args(0))
      .enableHiveSupport()
      .getOrCreate()

    import spark.implicits._

    import org.apache.hadoop.fs.FileSystem
    import org.apache.hadoop.fs.Path
    val fs = FileSystem.get(spark.sparkContext.hadoopConfiguration)

    println(s"Writing #lines: ${lines.length}")
    val outputPath = "hdfs:///kv1.txt"
    if(!fs.exists(new Path(outputPath)))
      spark
        .sparkContext
        .parallelize(lines)
        .saveAsTextFile("hdfs:///kv1.txt")

    import spark.sql

    sql("CREATE TABLE IF NOT EXISTS src (key INT, value STRING) USING hive")
    sql("LOAD DATA INPATH 'hdfs:///kv1.txt' INTO TABLE src")

    // Queries are expressed in HiveQL
    sql("SELECT * FROM src").show()
    // +---+-------+
    // |key|  value|
    // +---+-------+
    // |238|val_238|
    // | 86| val_86|
    // |311|val_311|
    // ...

    // Aggregation queries are also supported.
    sql("SELECT COUNT(*) FROM src").show()
    // +--------+
    // |count(1)|
    // +--------+
    // |    500 |
    // +--------+

    // The results of SQL queries are themselves DataFrames and support all normal functions.
    val sqlDF = sql("SELECT key, value FROM src WHERE key < 10 ORDER BY key")

    // The items in DataFrames are of type Row, which allows you to access each column by ordinal.
    val stringsDS = sqlDF.map {
      case Row(key: Int, value: String) => s"Key: $key, Value: $value"
    }
    stringsDS.show()
    // +--------------------+
    // |               value|
    // +--------------------+
    // |Key: 0, Value: val_0|
    // |Key: 0, Value: val_0|
    // |Key: 0, Value: val_0|
    // ...

    // You can also use DataFrames to create temporary views within a SparkSession.
    val recordsDF = spark.createDataFrame((1 to 100).map(i => Record(i, s"val_$i")))
    recordsDF.createOrReplaceTempView("records")

    // Queries can then join DataFrame data with data stored in Hive.
    sql("SELECT * FROM records r JOIN src s ON r.key = s.key").show()
    // +---+------+---+------+
    // |key| value|key| value|
    // +---+------+---+------+
    // |  2| val_2|  2| val_2|
    // |  4| val_4|  4| val_4|
    // |  5| val_5|  5| val_5|
    // ...

    // Create a Hive managed Parquet table, with HQL syntax instead of the Spark SQL native syntax
    // `USING hive`
    sql("CREATE TABLE IF NOT EXISTS hive_records(key int, value string) STORED AS PARQUET")
    // Save DataFrame to the Hive managed table
    val df = spark.table("src")
    df.write.mode(SaveMode.Overwrite).saveAsTable("hive_records")
    // After insertion, the Hive managed table has data now
    sql("SELECT * FROM hive_records").show()
    // +---+-------+
    // |key|  value|
    // +---+-------+
    // |238|val_238|
    // | 86| val_86|
    // |311|val_311|
    // ...

    // Needed for spark 2.3.0
    //val rand_suffix = Random.alphanumeric.take(10).mkString

    //val dataDir = s"hdfs:///tmp/parquet_data_${rand_suffix}"
    // Prepare a Parquet data directory
    //spark.range(10).write.parquet(dataDir)
    // Create a Hive external Parquet table
    //sql(s"CREATE EXTERNAL TABLE hive_ints_${rand_suffix}(key int) STORED AS PARQUET LOCATION '$dataDir'")
    // The Hive external table should already have data
    //sql(s"SELECT * FROM hive_ints_${rand_suffix}").show()
    // +---+
    // |key|
    // +---+
    // |  0|
    // |  1|
    // |  2|
    // ...

    println("Test completed successfully.")

    spark.stop()
  }
}
