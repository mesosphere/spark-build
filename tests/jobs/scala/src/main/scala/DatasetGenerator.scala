import org.apache.spark.sql.SparkSession

import scala.util.Random

/**
	* Generates dataset in form of randomly generated key/value pairs. Can be used in stress-tests and benchmarks
  *
	* Usage: DatasetGenerator [totalRecords] [recordSize] [s3_destination]
	*/

case class DataItem(key: String, value: Array[Byte])

object DatasetGenerator {

	def main(args: Array[String]): Unit = {

		if (args.length != 3) {
			println("Usage: DatasetGenerator [totalRecords] [recordSize] (in bytes) [s3_destination]")
			System.exit(1)
		}

		val spark = SparkSession
			.builder
			.config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
			.config("spark.hadoop.fs.s3a.aws.credentials.provider", "org.apache.hadoop.fs.s3a.TemporaryAWSCredentialsProvider")
			.appName("Dataset Generator")
			.getOrCreate()

		val sc = spark.sparkContext

		val totalRecords = args(0).toInt
		val recordSize = args(1).toInt
		val s3_destination = args(2)

		import spark.implicits._

		// generate static prefix for the key
		val prefix = Random.alphanumeric.take(120).mkString

		sc.parallelize(Seq.fill(totalRecords) {
			generateDataItem(recordSize, prefix)
		})
			.toDS()
			.write
			.option("compression", "gzip")
			.json(s3_destination)

		spark.stop()
	}

	def generateDataItem(recordSize: Int, prefix: String): DataItem = {
		val byteArr = new Array[Byte](recordSize)
		Random.nextBytes(byteArr)
		val keyRandomPart = Random.alphanumeric.take(8).mkString
		DataItem(prefix + keyRandomPart, byteArr)
	}
}
