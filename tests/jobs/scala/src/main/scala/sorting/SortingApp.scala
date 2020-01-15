package sorting

import java.io.{BufferedReader, InputStreamReader}

import org.apache.spark.input.PortableDataStream
import org.apache.spark.sql.SparkSession

import scala.collection.SortedSet
import scala.collection.JavaConverters._
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
      s"""PartitionValidationResult {
         |  file: $fileName,
         |  success: $isSuccess,
         |  totalKeys: $totalKeys,
         |  first: $firstKey,
         |  last: $lastKey,
         |  unorderedKeys: $outOfOrderKeys,
         |  sample:
         |  ${sample.mkString("\n")}
         |}
       """.stripMargin
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
        .binaryFiles(outputPath)
        .map({case (file, stream) => validateBinaryOrderingWithinPartition(file, stream)})
        .collect()
        .to[SortedSet]
    })
    spark.stop()
  }

  def validateBinaryOrderingWithinPartition(fileName: String, contents: PortableDataStream): PartitionValidationResult = {
    val regexErrorMessage = "[Error: unable to find a key match in regex]"
    var totalKeys = 0L
    var outOfOrderKeys = 0L
    val sampleKeys = new ListBuffer[String]()

    val reader = new BufferedReader(new InputStreamReader(contents.open()))
    var firstKey = ""
    var previous = ""

    reader.lines().iterator().asScala.foreach(line => {
      if (previous.isEmpty) {
        firstKey = pattern.findFirstIn(line).getOrElse(regexErrorMessage)
      }

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

    PartitionValidationResult(
      fileName = fileName,
      isSuccess = outOfOrderKeys == 0,
      totalKeys = totalKeys,
      outOfOrderKeys = outOfOrderKeys,
      sample = sampleKeys.toList,
      firstKey = firstKey,
      lastKey = pattern.findFirstIn(previous).getOrElse(regexErrorMessage)
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
