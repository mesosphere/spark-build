import org.apache.spark.{SparkConf, SparkContext}

/**
  * Application that will count the number of lines in a file stored on HDFS or other available
  * storage service.
  *
  * Usage:
  * {SPARK} {ARGS} {PATH_TO_ASSEMBLY} hdfs:///path/to/textfile
  * where {SPARK} is either `dcos spark run` or `./bin/spark-submit`
  * {ARGS} are the configuration arguments to Spark (e.g. `--conf spark.cores.max=8`)
  * {PATH_TO_ASSEMBLY} is the location of the snapshot jar containing this application
  * note that this application requires the hdfs-site.xml and core-site.xml configuration
  * files to be present in the HADOOP_CONF_DIR directory (`/etc/hadoop` by default)
  */
object HDFSWordCount {
  def main(args: Array[String]): Unit = {
    val conf = new SparkConf()
    val sc = new SparkContext(conf)
    val file = args(0)
    val rdd = sc.textFile(file)
    print(s"number of lines in ${file}: ${rdd.count()}")
  }
}
