import com.databricks.spark.gpu.pi.GpuPi
import org.apache.spark.SparkContext
import org.apache.spark.SparkConf
import java.io._
import scala.math.Pi
import sys.process._

/* App that uses Monte Carlo simulation to calculate Pi on GPUs.
 * App assumption: spark.executor.cores=1
 * Based on: https://docs.databricks.com/applications/deep-learning/jcuda.html
 */
object GpuPiApp {
  def main(args: Array[String]): Unit = {
    println("RUNNING GpuPiApp")
    if (args.length < 1) {
      throw new IllegalArgumentException("USAGE: <number_of_executors> [samples_per_thread] [app_name]")
    }

    val numThreads = 1024
    val numberOfExecutors = args(0).toLong
    println(s"numberOfExecutors: $numberOfExecutors")
    val samplesPerThread = if (args.length < 2) 1000 else args(1).toInt
    println(s"samplesPerThread: $samplesPerThread")
    val appName = if (args.length < 3) "GpuPiApp" else args(2)
    println(s"appName: $appName")
    val conf = new SparkConf().setAppName(appName)
    val sc = new SparkContext(conf)

    doGpu(sc, samplesPerThread, numThreads, numberOfExecutors)
  }

  private def doGpu(sc: SparkContext, samplesPerThread: Int, numThreads: Int, numberOfExecutors: Long): Unit = {
    // Compile the kernel function on every node
    val cuFilePath = "/mnt/mesos/sandbox/PiCalc.cu"
    sc.range(0, numberOfExecutors)
      .map{x => {
        writeCuFile(samplesPerThread, cuFilePath)
        Seq(
          "/usr/local/cuda/bin/nvcc", "-ptx", cuFilePath, "-o", "/mnt/mesos/sandbox/PiCalc.ptx") !!
        }
      }
      .collect()

    // Calculate Pi with GPUs
    println("Calculating Pi with GPUs")
    val totalSamples = numberOfExecutors * numThreads * samplesPerThread
    val totalInTheCircle = sc.range(0, numberOfExecutors).map { x =>
      sumInts(GpuPi.gpuPiMonteCarlo())
    }.reduce(_ + _)
    val piGPU = totalInTheCircle * 4.0 / totalSamples

    // Check result
    val actualPi = Pi

    val piGPUDiffPercent = (actualPi - piGPU) * 100.0 / actualPi
    println(s"Pi calculated with GPUs: $piGPU, DiffPercent: ${piGPUDiffPercent}%")
  }

  private def sumInts(xs: Iterable[Int]): Long =
    xs.foldLeft(0L)(_ + _)

  private def writeCuFile(samplesPerThread: Int, filePath: String): Unit = {
    val contents = s"""
#include <curand.h>
#include <curand_kernel.h>

extern "C"
__global__ void piCalc(int *result)
{
  unsigned int tid = threadIdx.x + blockDim.x * blockIdx.x;
  int sum = 0;
  unsigned int N = $samplesPerThread; // samples per thread unsigned
  int seed = tid;
  curandState s; // seed a random number generator
  curand_init(seed, 0, 0, &s);
  // take N samples in a quarter circle
  for(unsigned int i = 0; i < N; ++i) {
    // draw a sample from the unit square
    float x = curand_uniform(&s);
    float y = curand_uniform(&s); // measure distance from the origin
    float dist = sqrtf(x*x + y*y);
    // add 1.0f if (u0,u1) is inside the quarter circle
    if(dist <= 1.0f) sum += 1;
  }
  result[tid] = sum;
}
"""
    val file = new File(filePath)
    val bw = new BufferedWriter(new FileWriter(file))
    bw.write(contents)
    bw.close()
  }
}
