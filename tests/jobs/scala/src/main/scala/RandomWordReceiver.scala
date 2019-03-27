import java.util.concurrent.atomic.AtomicLong
import java.util.concurrent.{Executors, ScheduledExecutorService, TimeUnit}

import org.apache.spark.internal.Logging
import org.apache.spark.storage.StorageLevel
import org.apache.spark.streaming.receiver.Receiver
import org.apache.spark.util.LongAccumulator

import scala.util.Random

class RandomWordReceiver(wordsPerSecond: Float, numberOfWords: AtomicLong, accumulator: LongAccumulator, infinite: Boolean = false)
  extends Receiver[String](StorageLevel.MEMORY_ONLY_2) with Logging {

  val rate: Long = (1000L / wordsPerSecond).toLong
  val inputList: Array[String] = "the quick brown fox jumps over the lazy dog".split(" ")
  val random: Random = Random

  private var executorService: ScheduledExecutorService = _

  def onStart(): Unit = {
    if (accumulator.value >= numberOfWords.get()) {
      val msg = "Receiver (re)started after all words had been published"
      logError(msg)
      stop(msg)
    } else {
      executorService = Executors.newScheduledThreadPool(1)
      val receiver = new WordReceiver

      executorService.scheduleAtFixedRate(receiver, 0, rate, TimeUnit.MILLISECONDS)
    }
  }

  def onStop() : Unit = {
    logInfo("Received 'stop' shutting down executor service")
    if (executorService != null) {
      executorService.shutdown()
    }
  }

  sealed class WordReceiver extends Runnable {
    /**
      * Select a random word from the input list until the receiver is stopped.
      */
    override def run(): Unit = {
      try {
        val word: String = inputList(random.nextInt(inputList.length))

        if (infinite) {
          logInfo(s"Writing: $word (infinite stream)")

          store(word)
        } else {
          val wordsLeft = numberOfWords.getAndDecrement()

          if (wordsLeft > 0L) {
            logInfo(s"Writing: '$word' ($wordsLeft words left)")
            store(word)
            accumulator.add(1)
          } else {
            stop("Requested number of words sent")
          }
        }
      } catch {
        case t: Throwable =>
          logError("Exception caught while emitting data", t)
          // restart if there is any other error
          restart("Error receiving data", t)
      }
    }
  }
}
