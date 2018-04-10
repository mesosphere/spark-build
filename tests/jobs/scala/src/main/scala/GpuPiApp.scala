import com.databricks.spark.gpu.pi.GpuPi
import org.apache.spark.sql.functions.sum
import org.apache.spark.SparkContext
import org.apache.spark.SparkConf
import scala.math.Pi
import sys.process._

/* App that uses Monte Carlo simulation to calculate Pi on GPUs.
 * App assumption: spark.executor.cores=1
 * Based on: https://docs.databricks.com/applications/deep-learning/jcuda.html
 */
object GpuPiApp {
  def main(args: Array[String]): Unit = {
    println("RUNNING GpuPiApp")
    if (args.length != 1) {
      throw new IllegalArgumentException("USAGE: <number_of_executors>")
    }

    val conf = new SparkConf().setAppName("GpuPiApp")
    val sc = new SparkContext(conf)
    val samplesPerThread = 1000
    val numThreads = 1024
    val numberOfExecutors = args(0).toInt
    println(s"numberOfExecutors: $numberOfExecutors")

    doGpu(sc, samplesPerThread, numThreads, numberOfExecutors)
  }

  private def doGpu(sc: SparkContext, samplesPerThread: Int, numThreads: Int, numberOfExecutors: Int): Unit = {
    // Compile the kernel function on every node
    sc.range(0, numberOfExecutors)
      .map{x => Seq(
        "/usr/local/cuda/bin/nvcc", "-ptx", "/mnt/mesos/sandbox/PiCalc.cu", "-o", "/mnt/mesos/sandbox/PiCalc.ptx")!!
      }
      .collect()

    // Calculate Pi with GPUs
    println("Calculating Pi with GPUs")
    val totalSamples = numberOfExecutors * numThreads * samplesPerThread
    val totalInTheCircle = sc.range(0, numberOfExecutors).map { x =>
      GpuPi.gpuPiMonteCarlo().sum
    }.reduce(_ + _)
    val piGPU = totalInTheCircle * 4.0 / totalSamples

    // Check result
    val actualPi = Pi

    val piGPUDiffPercent = (actualPi - piGPU) * 100.0 / actualPi
    println(s"Pi calculated with GPUs: $piGPU, DiffPercent: ${piGPUDiffPercent}%")
  }
}
