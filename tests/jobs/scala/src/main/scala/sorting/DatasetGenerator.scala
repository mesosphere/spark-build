package sorting

import org.apache.spark.sql.SparkSession
import org.apache.spark.sql.types.{DataTypes, StringType, StructField, StructType}

import scala.util.Random

/**
  * Generates a dataset in form of randomly generated key/value pairs. Can be used in stress-tests and benchmarks
  */

case class DataItem(key: String, value: Array[Byte])

object DataItem {
  def schema = StructType(Seq(
    StructField("key", StringType, nullable = false),
    StructField("value", DataTypes.BinaryType, nullable = false)
  ))
}

case class Config(numFiles: Int = -1,
                  numRecords: Int = -1,
                  staticPrefixLength: Int = 120,
                  randomSuffixLength: Int = 8,
                  valueSizeBytes: Int = 1000000,
                  targetLocation: String = "")

object DatasetGenerator {

  private val parser = new scopt.OptionParser[Config]("DatasetGenerator") {
    head("Dataset generator for Spark sorting benchmarks", "0.1")
    opt[Int]("num-files") required() action { (x, c) => c.copy(numFiles = x) } text "the target number of files to create"
    opt[Int]("num-records") required() action { (x, c) => c.copy(numRecords = x) } text "number of records (key-value pairs) to generate"
    opt[Int]("static-prefix-length") optional() action { (x, c) => c.copy(staticPrefixLength = x) } text "length of the static part of the keys"
    opt[Int]("random-suffix-length") optional() action { (x, c) => c.copy(randomSuffixLength = x) } text "length of the variable part of the keys"
    opt[Int]("value-size-bytes") optional() action { (x, c) => c.copy(valueSizeBytes = x) } text "binary value size in bytes"
    opt[String]("output-path") required() action { (x, c) => c.copy(targetLocation = x) } text "target path to persist generated dataset"
  }

  def main(args: Array[String]): Unit = {
    parser.parse(args, Config()) match {
      case Some(config) =>
        generateDataSet(config)

      case None =>
        println(parser.usage)
        System.exit(1)
    }
  }

  private def generateDataSet(config: Config): Unit = {
    val prefix = Random.alphanumeric.take(config.staticPrefixLength).mkString

    val spark = SparkSession
      .builder
      .appName("Dataset Generator")
      .getOrCreate()

    import spark.implicits._

    spark.sparkContext.parallelize(1 to config.numRecords, numSlices = config.numFiles)
      .map(_ => generateDataItem(config.valueSizeBytes, config.randomSuffixLength, prefix))
      .toDS()
      .write
      .option("compression", "gzip")
      .json(config.targetLocation)

    spark.stop()
  }

  private def generateDataItem(valueSizeBytes: Int, randomSuffixLength: Int, prefix: String): DataItem = {
    val byteArr = new Array[Byte](valueSizeBytes)
    Random.nextBytes(byteArr)
    val keyRandomPart = Random.alphanumeric.take(randomSuffixLength).mkString
    DataItem(prefix + keyRandomPart, byteArr)
  }
}
