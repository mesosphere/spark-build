package sorting

import org.apache.spark.sql.SparkSession

import scala.collection.SortedSet
import scala.collection.mutable.ListBuffer
import scala.reflect.ClassTag
import scala.util.matching.UnanchoredRegex

/**
	* Performs sort (transformation) and count (action) on the Dataset, loaded from [input path].
	* In case [input path] requires authentication, all the properties should be provided via
	* Spark Configuration or spark-submit '--conf key=value' arguments.
	*
	* Usage: SortingApp [input path] [output path]
	*/

object SortingApp {

	val pattern: UnanchoredRegex = """"key":"([a-zA-Z0-9]+)"""".r.unanchored

	case class PartitionValidationResult(
																				fileName: String,
																				isSuccess: Boolean,
																				totalKeys: Long,
																				outOfOrderKeys: Long,
																				sample: List[String],
																				firstKey: String,
																				lastKey: String) extends Ordered[PartitionValidationResult] {


		override def toString: String = {
			s"PartitionValidationResult {\n\tfile: $fileName,\n\tsuccess: $isSuccess,\n\ttotalKeys: $totalKeys,\n\tfirst: $firstKey,\n\tlast: $lastKey,\n\tunorderedKeys: $outOfOrderKeys,\n\tsample:\n${sample.mkString("\n")}}"
		}

		override def compare(that: PartitionValidationResult): Int = fileName.compareTo(that.fileName)
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

		validateGlobalOrdering({
			spark.
				sparkContext
				.wholeTextFiles(outputPath)
				.map(validateOrderingWithinPartition)
				.collect()
				.to[SortedSet]
		})
		spark.stop()
	}

	def validateOrderingWithinPartition(file: (String, String)): PartitionValidationResult = {

		var totalKeys = 0L
		var outOfOrderKeys = 0L
		val sampleKeys = new ListBuffer[String]()

		val (fileName, contents) = file
		val lines = contents.split("\n")
		var previous = ""
		lines.foreach(line => {
			totalKeys += 1
			if (line.compareTo(previous) < 0) {
				sampleKeys += previous
				sampleKeys += line
				sampleKeys += ""
				outOfOrderKeys += 1
			} else {
				previous = line
			}
		})

		val pattern(firstKey) = lines(0)
		val pattern(lastKey) = lines(lines.size - 1)

		PartitionValidationResult(
			fileName = fileName,
			isSuccess = outOfOrderKeys == 0,
			totalKeys = totalKeys,
			outOfOrderKeys = outOfOrderKeys,
			sample = sampleKeys.toList,
			firstKey = firstKey,
			lastKey = lastKey
		)
	}

	def validateGlobalOrdering(results: SortedSet[PartitionValidationResult]): Unit = {
		var previous: PartitionValidationResult = null
		results.foreach(result => {
			if (previous != null) {
				println(result)
				if (result.firstKey.compareTo(previous.lastKey) < 0)
					throw new IllegalStateException(s"Validation failed!\n$previous\n$result")
			}
			previous = result
		})
		println("Global ordering has been validated successfully.")
	}

}
