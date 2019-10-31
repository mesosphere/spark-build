package sorting

import org.apache.spark.sql.SparkSession

import scala.collection.mutable.ListBuffer
import scala.reflect.ClassTag

/**
	* Performs sort (transformation) and count (action) on the Dataset, loaded from [input path].
	* In case [input path] requires authentication, all the properties should be provided via
	* Spark Configuration or spark-submit '--conf key=value' arguments.
	*
	* Usage: SortingApp [input path] [output path]
	*/

object SortingApp {

	//TODO: this is a good candidate for gathering more information about partition (min key, max key, any errors).
	//			Once each partition is validated, the final result can be sorted based by min key, collected, and analized
	//			on the driver side to be able to reason about global ordering

	case class PartitionValidationResult(
																				index: Int,
																				isSuccess: Boolean,
																				totalKeys: Long,
																				outOfOrderKeys: Long,
																				sample: List[String]){
		override def toString: String = {
			s"PartitionValidationResult index: $index, success: $isSuccess, totalKeys: $totalKeys, unorderedKeys: $outOfOrderKeys, sample:\n${sample.mkString("\n")}"
		}
	}

	def main(args: Array[String]): Unit = {
		if (args.length != 2) {
			println("Usage: SortingApp [input path] [output path]")
			System.exit(1)
		}

		val spark = SparkSession
			.builder
			.appName("SortingApp")
			.getOrCreate()

		val inputPath = args(0)
		val outputPath = args(1)

		import spark.implicits._

		val ordering = new Ordering[DataItem] {
			override def compare(x: DataItem, y: DataItem): Int = x.key.compareTo(y.key)
		}
		//TODO: ideally, the time should be reported as a metric
		spark.time {
			spark
				.read
				.option("compression", "gzip")
				.schema(DataItem.schema)
				.json(inputPath)
				.as[DataItem]
				.rdd
				.sortBy(identity)(ord = ordering, ctag = ClassTag(classOf[DataItem]))
				.toDS()
				.write
				.json(outputPath)
		}

		//This is a naive implementation which terminates when the first unordered pair of keys appears in a partition.
		//FIXME: this implementation doesn't validate the global ordering of keys, only the ordering within a partition
		//			 ValidationResult can be used to accumulate per-partition statistics and perform final validation
		spark
			.read
			.schema(DataItem.schema)
			.json(outputPath)
			.as[DataItem]
			.rdd
			.mapPartitionsWithIndex(validateOrderingWithinPartition)
			.filter(result => !result.isSuccess)
			.collect()
			.foreach(println)

		spark.stop()
	}

	def validateOrderingWithinPartition(partitionIndex: Int, iterator: Iterator[DataItem]): Iterator[PartitionValidationResult] = {
		var totalKeys = 0L
		var outOfOrderKeys = 0L

		var previous = ""
		val sampleKeys = new ListBuffer[String]()
		while (iterator.nonEmpty) {
			totalKeys += 1
			val key = iterator.next().key
			if (key.compareTo(previous) < 0) {
				sampleKeys += previous
				sampleKeys += key
				sampleKeys += ""
				outOfOrderKeys += 1
			} else {
				previous = key
			}
		}

		Seq(PartitionValidationResult(
			index = partitionIndex,
			isSuccess = false,
			totalKeys = totalKeys,
			outOfOrderKeys = outOfOrderKeys,
			sample = sampleKeys.toList)
		).iterator
	}
}
