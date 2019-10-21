package sorting

import org.apache.spark.sql.SparkSession

/**
	* Performs sort (transformation) and count (action) on the Dataset, loaded from [s3bucket].
	*
	* Usage: SortingApp [s3bucket]
	*/

object SortingApp {

	def main(args: Array[String]): Unit = {
		if (args.length != 1) {
			println("Usage: SortingApp [s3bucket]")
			System.exit(1)
		}

		val spark = SparkSession
			.builder
			.appName("SortingApp")
			.getOrCreate()

		val s3bucket = args(0)

		import spark.implicits._

		val sortedDS = spark
			.read
			.option("compression", "gzip")
			.json(s3bucket)
			.as[DataItem]
			.sort("key")

		spark.time(sortedDS.count())

		sortedDS.take(20).foreach(dataItem => println(dataItem.key))
		spark.stop()
	}

}
