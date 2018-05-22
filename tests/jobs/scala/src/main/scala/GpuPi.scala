package com.databricks.spark.gpu.pi

import jcuda.driver.CUdevice_attribute._
import jcuda.driver.JCudaDriver._
import java.util._
import jcuda.driver._
import jcuda.runtime._
import jcuda.driver.CUmodule
import jcuda._
import jcuda.driver.CUdevice_attribute

object GpuPi {
  val numThreads = 1024
  def gpuPiMonteCarlo() : Array[Int] = {
    JCudaDriver.setExceptionsEnabled(true)
    cuInit(0)
    val pctx = new CUcontext()
    val dev = new CUdevice()
    cuDeviceGet(dev, 0)
    cuCtxCreate(pctx, 0, dev)
    val module = new CUmodule
    CUresult.stringFor(cuModuleLoad(module, "/mnt/mesos/sandbox/PiCalc.ptx"))
    val function = new CUfunction()
    cuModuleGetFunction(function, module, "piCalc");
    val deviceInput = new CUdeviceptr()
    val deviceOutput = new CUdeviceptr()
    cuMemAlloc(deviceInput, Integer.SIZE);
    cuMemAlloc(deviceOutput, Integer.SIZE * numThreads);
    val kernelParameters = Pointer.to(
      Pointer.to(deviceOutput)
    )
    cuLaunchKernel(function,
      1, 1, 1,           // Grid dimension
      numThreads, 1, 1,  // Block dimension
      1, null,           // Shared memory size and stream
      kernelParameters, null // Kernel- and extra parameters
    )
    cuCtxSynchronize()
    val hostOutput = new Array[Int](numThreads)
    cuMemcpyDtoH(Pointer.to(hostOutput), deviceOutput, Integer.SIZE * numThreads)
    hostOutput
  }
}
