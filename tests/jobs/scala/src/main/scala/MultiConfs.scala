import org.apache.spark.SparkConf

/**
  * Application that outputs the Spark configurations.
  * Specifically we want to test whether long strings of multiple arg=values are passed through correctly.
  * E.g. 
  * dcos spark run --submit-args="\
        --conf=spark.driver.extraJavaOptions='arg1=val1 arg2=val2 -Dparam3=\"valA valB\"' \
        --class MultiConfs \
        <jar> arg1 val1"
  */ 
object MultiConfs {
    def main(args: Array[String]): Unit = {
        val AppName = "MultiConfs App"
        println(s"Running $AppName\n")

        // Verify property is set in Spark conf
        val conf = new SparkConf().setAppName(AppName)
        println("Printing all conf values...")
        conf.getAll.foreach(println)
        
        // Verify property is set in system     
        val props = System.getProperties()
        println("Printing all System.properties...")
        props.list(System.out)
    }
}
