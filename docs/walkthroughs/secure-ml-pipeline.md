# Fully secure ML pipeline using Spark, HDFS, and Kafka
This walkthrough will show how to setup a Spark ML model for classification of data streaming from a Kafka topic. The
Kafka and HDFS clusters will use Kerberos for authentication and SASL. All Spark communication channels will also be
secured. Specifically we will demonstrate the following:
1.  Use Kerberos-secured HDFS and Kafka with Spark
1.  Use TLS and SASL in Spark
1.  Use Spark Streaming
1.  Use Spark ML Pipelines

Completing this walkthrough requires the following.
1.  DC/OS Cluster with 5 agents with >= 4 cores/agent.
1.  A running KDC that you can add principals to. 
1.  A way to download/acquire the `keytab` from the KDC to your local workstation.
1.  An S3 bucket to host a Spark application
1.  `sbt` to build the example application

## Setting up secure HDFS and Kafka
The Keberos `keytab` is a binary file and cannot be uploaded to the Secret Store directly. To use binary secrets in
DC/OS 1.10 and lower the binary file must be base64 encoded and the resultant string will be uploaded with the prefix:
`__dcos_base64__<secretname>`, this tells DC/OS to decode the file before placing it in the Sandbox.
In DC/OS 1.11+, base64 encoding of binary secrets is not necessary. You may skip the encoding
and update the secret names accordingly in the following example.

1.  Establish correct principals for HDFS and Kafka, assuming you're using the packages from the DC/OS universe.
    **Note** Requires DC/OS EE for file-based secrets. Add the following principals to the KDC (Obviously it is
    recommended to use a script or other automation to establish these principals):
    ```bash
    hdfs/name-0-node.hdfs.autoip.dcos.thisdcos.directory@LOCAL
    HTTP/name-0-node.hdfs.autoip.dcos.thisdcos.directory@LOCAL
    hdfs/name-0-zkfc.hdfs.autoip.dcos.thisdcos.directory@LOCAL
    HTTP/name-0-zkfc.hdfs.autoip.dcos.thisdcos.directory@LOCAL
    hdfs/name-1-node.hdfs.autoip.dcos.thisdcos.directory@LOCAL
    HTTP/name-1-node.hdfs.autoip.dcos.thisdcos.directory@LOCAL
    hdfs/name-1-zkfc.hdfs.autoip.dcos.thisdcos.directory@LOCAL
    HTTP/name-1-zkfc.hdfs.autoip.dcos.thisdcos.directory@LOCAL
    hdfs/journal-0-node.hdfs.autoip.dcos.thisdcos.directory@LOCAL
    HTTP/journal-0-node.hdfs.autoip.dcos.thisdcos.directory@LOCAL
    hdfs/journal-1-node.hdfs.autoip.dcos.thisdcos.directory@LOCAL
    HTTP/journal-1-node.hdfs.autoip.dcos.thisdcos.directory@LOCAL
    hdfs/journal-2-node.hdfs.autoip.dcos.thisdcos.directory@LOCAL
    HTTP/journal-2-node.hdfs.autoip.dcos.thisdcos.directory@LOCAL
    hdfs/data-0-node.hdfs.autoip.dcos.thisdcos.directory@LOCAL
    HTTP/data-0-node.hdfs.autoip.dcos.thisdcos.directory@LOCAL
    hdfs/data-1-node.hdfs.autoip.dcos.thisdcos.directory@LOCAL
    HTTP/data-1-node.hdfs.autoip.dcos.thisdcos.directory@LOCAL
    hdfs/data-2-node.hdfs.autoip.dcos.thisdcos.directory@LOCAL
    HTTP/data-2-node.hdfs.autoip.dcos.thisdcos.directory@LOCAL
    kafka/kafka-0-broker.secure-kafka.autoip.dcos.thisdcos.directory@LOCAL
    kafka/kafka-1-broker.secure-kafka.autoip.dcos.thisdcos.directory@LOCAL
    kafka/kafka-2-broker.secure-kafka.autoip.dcos.thisdcos.directory@LOCAL
    hdfs@LOCAL
    client@LOCAL
    ```
1.  Download the `keytab` file to a local directory.
1.  Base64 encode the file with `base64 -w 0 {source} > {destination}` (we recommend using `base64` from GNU coreutils.
    If the version on your machine is different the `-w` flag may need to be replaced with the appropriate flag to
    disable wrapping.
1.  Install the DC/OS Enterprise CLI with the command line: `dcos package install --yes dcos-enterprise-cli`   
1.  Upload the base64 encoded file to the secret store: `dcos security secrets create __dcos_base64__keytab --value-file
    {destination}`.
    *   Notice we have uploaded the secret to the root (will be `/__dcos_base64__keytab`)
1.  You're now ready to install HDFS and Kafka. This can be done using the UI (DC/OS Catalog) or through the CLI as
    demonstrated here. First make an `options.json` containing at least (these are the same for both services):
    ```json
    {
      "service": {
        "security": {
          "kerberos": {
            "enabled": true,
            "kdc": {
              "hostname": "<agent_hosting_kdc_or_dns>",
              "port": "<port_to_communicate_with_kdc>"
            },
            "realm": "LOCAL",
            "keytab_secret": "__dcos_base64__keytab"
          },
          "transport_encryption": {
            "enabled": true,
            "allow_plaintext": false
          }
        }
      }
    }
    ```
    
## Install Spark and prepare Java Authentication and Authorization Service (JAAS) file for Kafka
1.  Install Spark including HDFS settings, using the instructions in [installing-secure-spark.md](). Using Kafka from
    Spark does not require any special configuration when installing Spark.
1.  Using Kerberos-secured Kafka from Spark requires a JAAS file to be available to the job, we use S3 to host the
    artifact. In this example use the following: 
    ```
    KafkaClient {
        com.sun.security.auth.module.Krb5LoginModule required
        useKeyTab=true
        storeKey=true
        keyTab="/mnt/mesos/sandbox/kafka-client.keytab"
        useTicketCache=false
        serviceName="kafka"
        principal="client@LOCAL";
    }; 
    ```

    This is also available in the [resources](https://github.com/mesosphere/spark-build/tree/master/tests/resources) of
    the test repo. Add these contents to a local file, copy it to S3 and make it publicly accessible. For the
    remainder of the tutorial we'll reference this location as `http://JAAS_ARTIFACT.conf` 

## Run the example
_All of the code for this example is in SpamHam.scala in the
[resources](https://github.com/mesosphere/spark-build/tree/master/tests/resources) folder of this repo_
1.  We need to upload the training data to S3, we use the file `SMSSpamCollection.txt` that can be found in the
    [resources](https://github.com/mesosphere/spark-build/tree/master/tests/resources) of the test repo. This artifact
    needs to be publicly available to your cluster, we will refer to this artifact as `http://SMS_DATA.txt`.
1.  Build the example jar by following the instructions in the
    [README](https://github.com/mesosphere/spark-build/tree/master/tests/jobs). Upload that to S3 so
    that it can be publicly accessible, we will refer to this artifact as `http://DCOS_EXAMPLES.jar` 
1.  Run the model training step, notice here we only use HDFS:
    ```bash
    dcos spark run --submit-args="\
    --kerberos-principal=hdfs@LOCAL \
    --keytab-secret-path=/__dcos_base64__keytab \
    --keystore-secret-path=spark/__dcos_base64__keystore \
    --keystore-password=changeit \
    --private-key-password=changeit \
    --truststore-secret-path=spark/__dcos_base64__truststore \
    --truststore-password=changeit \
    --executor-auth-secret=spark/spark-auth-secret \
    --conf spark.cores.max=8 \
    --conf spark.mesos.uris=http://SMS_DATA.txt \
    --class SpamHamModelFactory http://DCOS_EXAMPLES.jar file:///mnt/mesos/sandbox/SMSSpamCollection.txt 0.8 hdfs:///nb_model"
    ```

    **Note:** The examples on this page assume that you are using the default
    service name for Spark, "spark". If using a different service name, update
    the secret paths accordingly.

1.  Setup the Spammer, this small job will just push messages to the topic:
    ```bash
    dcos spark run --submit-args="\
    --kerberos-principal=client@LOCAL \
    --keytab-secret-path=/__dcos_base64__keytab \
    --keystore-secret-path=spark/__dcos_base64__keystore \
    --keystore-password=changeit \
    --private-key-password=changeit \
    --truststore-secret-path=spark/__dcos_base64__truststore \
    --truststore-password=changeit \
    --executor-auth-secret=spark/spark-auth-secret \
    --conf spark.cores.max=2 \
    --conf spark.mesos.uris=http://SMS_DATA.txt,http://JAAS_ARTIFACT.conf \
    --conf spark.driver.extraJavaOptions=-Djava.security.auth.login.config=/mnt/mesos/sandbox/JAAS_ARTIFACT.conf \
    --conf spark.executor.extraJavaOptions=-Djava.security.auth.login.config=/mnt/mesos/sandbox/JAAS_ARTIFACT.conf \
    --class Spammer http://DCOS_EXAMPLES.jar file:///mnt/mesos/sandbox/SMSSpamCollection.txt top1 <broker>:<port> true"
    ```
    *Note* If you are running DC/OS Kafka, you can get the `broker` and `port` from running 
    ```bash
    dcos <kafka_service> --name=<service_name> endpoints broker
    ```
    Likely this will be something like:
    ```bash
    dcos kafka --name=secure-kafka endpoints broker
    ```
    
1.  Run the classifier, this will load the model you built and saved to HDFS and use it to classify the messages from
    the `Spammer`:
    ```bash
    dcos spark run --submit-args="\
    --kerberos-principal=client@LOCAL \
    --keytab-secret-path=/__dcos_base64__keytab \
    --keystore-secret-path=spark/__dcos_base64__keystore \
    --keystore-password=changeit \
    --private-key-password=changeit \
    --truststore-secret-path=spark/__dcos_base64__truststore \
    --truststore-password=changeit \
    --executor-auth-secret=/spark/spark-auth-secret \
    --conf spark.cores.max=4 \
    --conf spark.mesos.uris=http://SMS_DATA.txt,http://JAAS_ARTIFACT.conf \
    --conf spark.driver.extraJavaOptions=-Djava.security.auth.login.config=/mnt/mesos/sandbox/JAAS_ARTIFACT.conf \
    --conf spark.executor.extraJavaOptions=-Djava.security.auth.login.config=/mnt/mesos/sandbox/JAAS_ARTIFACT.conf \
    --class SpamHamStreamingClassifier http://DCOS_EXAMPLES.jar top1 <broker>:<port> hdfs:///nb_model true"

    ```   
    You can look at the `stdout` for this job and see a running average classification accuracy for your spam detector. 
    
## Digging deeper

1.  Training a model with a ML Pipeline. One of the nicest features in later Spark versions is the Pipeline model in
    Spark-ml. These powerful abstractions allow you to wire together `Transformers` and `Estimators`. See the [Spark ML
    docs](https://spark.apache.org/docs/latest/ml-pipeline.html) for a thorough explanation. The basic idea is that a
    `Transformer` will simply compute results from individual datums, whereas `Estimators` need to be _fit_ on all the
    data.  In our example the `Pipeline` is:

    ```scala
    // SpamHam.scala 
    def spamOrHamPipeline(numFeatures: Int): Pipeline = {
      val stringIndexer = new StringIndexer()
        .setInputCol("spamorham")
        .setOutputCol("label")
      val tokenizer = new Tokenizer()
        .setInputCol("message")
        .setOutputCol("tokens")
      val hashingTF = new HashingTF()
        .setInputCol(tokenizer.getOutputCol)
        .setOutputCol("rawFeatures")
        .setNumFeatures(numFeatures)
      val idf = new IDF()
        .setInputCol(hashingTF.getOutputCol)
        .setOutputCol("features")
     val nb = new NaiveBayes()
     new Pipeline().setStages(Array(stringIndexer, tokenizer, hashingTF, idf, nb))
    }
    ```
    That's it. Here's a description of the various steps:
    1.  The `StringIndexer` is a `Estimator` that turns our "spam" and "ham" labels into indices (numbers) which are
        easier for the downstream stages to understand.
    1.  The `Tokenizer` is a `Transformer` that breaks a sentence of words into the constituent words (i.e. tokens).
    1.  The `HashingTF` is a `Transformer` that maps the tokens to feature vectors, basically treating each message as a
        "bag of words".
    1.  The `IDF` or _Inverse Document Frequency_ is an `Estimator` that attempts to find more important words from less
        important ones. For example, the word "is" or "a" are not likely to be informative in our classification
        downstream.
    
    1.  Lastly the `NaiveBayes` step is an `Estimator` that produces a probabilistic binary classification model based
        on [naive Bayes](https://en.wikipedia.org/wiki/Naive_Bayes_classifier).

1.  Generating a data stream. We need to generate some data to classify, so we're going to download the same file we
    used to train the classifier and make new messages from the vocabulary contained in that file. You're welcome to
    look through the example for the implementation details regarding how the new "messages" are generated. We'll focus
    instead on how to establish a `KafkaProducer`.
    ```scala
    // The kafka producer requires a Java HashMap
    val props = new util.HashMap[String, Object]()
    props.put(ProducerConfig.BOOTSTRAP_SERVERS_CONFIG, brokers)
    props.put(ProducerConfig.VALUE_SERIALIZER_CLASS_CONFIG,
      "org.apache.kafka.common.serialization.StringSerializer")
    props.put(ProducerConfig.KEY_SERIALIZER_CLASS_CONFIG,
      "org.apache.kafka.common.serialization.StringSerializer")

    if (kerberized ==  "true") {
      props.put("sasl.kerberos.service.name", "kafka")
      props.put("security.protocol", "SASL_PLAINTEXT")
      props.put("sasl.mechanism", "GSSAPI")
    }
    ```
    These are the bare minimum properties that need to be set to have Spark produce date into a kafka topic. Remember
    that `brokers` will be passed in via the command line. 
    ```scala
    val Array(labeledMessages, topic, brokers, kerberized) = args
    ```
    From there the producer pattern is straight forward.
    ```scala
       stream.foreachRDD { rdd =>
         println(s"Number of events: ${rdd.count()}")
         rdd.foreachPartition { p =>
           val producer = new KafkaProducer[String, String](props)
           p.foreach { r =>
             val d = r.toString()
             val msg = new ProducerRecord[String, String](topic, null, d)
             producer.send(msg)
           }
           producer.close()
         }
       } 
    ```

1.  Finally we want to hook up our classifier model to the stream. We can load our model:
    ```scala
    val model = PipelineModel.load(modelUri)
    ```
    The setup for the `KafkaConsumer` is slightly different than that of the producer, and unfortunately we cannot share
    code because they use different data structures.
    ```scala
    val props = mutable.Map[String, Object](
      "bootstrap.servers" -> brokers,
      "key.deserializer" -> classOf[StringDeserializer],
      "value.deserializer" -> classOf[StringDeserializer],
      "group.id" -> "use_a_separate_group_id_for_each_stream",
      "auto.offset.reset" -> "latest",
      "enable.auto.commit" -> (false: java.lang.Boolean)
    )

    if (kerberized == "true") {
      val kerbProps = Map[String, Object](
        "sasl.kerberos.service.name" -> "kafka",
        "security.protocol" -> "SASL_PLAINTEXT",
        "sasl.mechanism" -> "GSSAPI"
      )
    ```
    As you can see most of the necessary properties are the same. From here we can use a standard consumer pattern:
    ```scala
       val messages = KafkaUtils.createDirectStream[String, String](
         ssc,
         LocationStrategies.PreferConsistent,
         ConsumerStrategies.Subscribe[String, String](Array(topic), props))
   
       val lines = messages.map(_.value)
       lines.foreachRDD {
         (rdd: RDD[String], _: Time) =>
           val raw = spark.createDataFrame(SpamHamUtils.lineToRow(rdd), SpamHamUtils.SMSSchema)
           val predictions = model.transform(raw)
           val correct = CorrectAccumulator.getInstance(rdd.sparkContext)
           val total = TrialCounter.getInstance(rdd.sparkContext)
           predictions.foreach { r =>
             val label = r.getAs[Double](2)
             val prediction = r.getAs[Double](8)
             if (prediction == label) correct.add(1)
             total.add(1)
           }
           println(s"Running accuracy ${correct.value.toFloat / total.value}")
       } 
    ```
