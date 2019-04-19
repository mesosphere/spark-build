import org.apache.spark.sql.SparkSession
import com.google.common.math.IntMath
import com.google.common.base.Verify

/**
  * Application that outputs the sum of numbers from 1 to N.
  * Specifically we want to test whether a package (e.g. guava) is available by specifying in the packages flag in submit-args.
  * E.g. 
  * dcos spark run --submit-args="\
        --packages=com.google.guava:guava:23.0 \
        --class ProvidedPackages \
        <jar> number"
  */ 
object ProvidedPackages {
    def main(args: Array[String]): Unit = {
        val appName = "ProvidedPackages"
        println(s"Running $appName\n")

        var inputNumber = 10
        // Check argument is provided
        if (args.length > 0) {
	    try {
	        inputNumber = args(0).toInt
	    } catch {
		case e: NumberFormatException => inputNumber = 10
	    }
        }

	// Calculate the sum on the driver
	var driverSum = 0
	(1 to inputNumber).foreach(driverSum += _)

        val spark = SparkSession.builder.appName(appName).getOrCreate()

	// Calculate the sum on the executor
        val executorSum = spark.sparkContext.parallelize(1 to inputNumber).reduce((x, y) => IntMath.checkedAdd(x, y))
        
        // Verify both sums
        Verify.verify(driverSum == executorSum, "Sum of %s numbers on the executor (%s) is not equal to sum on the driver (%s)", inputNumber.toString, executorSum.toString, driverSum.toString)
	println(s"$driverSum")
    }
}
