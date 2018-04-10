#include <curand.h>
#include <curand_kernel.h>

extern "C"
__global__ void piCalc(int *result)
{
  unsigned int tid = threadIdx.x + blockDim.x * blockIdx.x;
  int sum = 0;
  unsigned int N = 1000; // samples per thread unsigned
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
