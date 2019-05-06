import java.nio.charset.StandardCharsets
import java.security.cert.X509Certificate
import java.security.cert.CertificateException

import org.apache.commons.io.IOUtils

import org.apache.http.client.methods.HttpGet
import org.apache.http.conn.ssl.NoopHostnameVerifier
import org.apache.http.HttpHeaders
import org.apache.http.impl.client.HttpClients
import org.apache.http.impl.client.CloseableHttpClient

import org.apache.http.ssl.SSLContextBuilder
import org.apache.http.conn.ssl.TrustStrategy
import org.apache.http.conn.ssl.SSLConnectionSocketFactory

import org.apache.spark.SparkConf

import org.json4s._
import org.json4s.jackson.JsonMethods._

/**
  * Application that outputs Spark Mesos Secret Configuration.
  * Specifically we want to test whether secret configurations passed through correctly.
  * E.g. 
  * dcos spark run --submit-args="\
        --conf=spark.mesos.driver.secret.names='/path/to/secret' \
        --conf=spark.mesos.driver.secret.envkeys='SECRET_ENV_KEY' \
        --class SecretConfs \
        <jar> authToken"
  */ 
object SecretConfs {
    implicit val formats = DefaultFormats
    case class SecretResponse(value: String)

    class TrustAllStrategy extends TrustStrategy {
        @throws(classOf[CertificateException])
        override def isTrusted(chain: Array[X509Certificate], authType:String): Boolean = { true }
    }

    def main(args: Array[String]): Unit = {
        val appName = "SecretConfs"
	var baseUrl = "https://master.mesos/secrets/v1/secret/default"
        val authToken = args(0)

        println(s"Running $appName\n")
	
        val conf = new SparkConf().setAppName(appName)
        val secretPath = conf.get("spark.mesos.driver.secret.names", "")
        var secretValue = conf.get("spark.mesos.driver.secret.values", "")
	var secretFile = conf.get("spark.mesos.driver.secret.filenames", "")

        if(!secretPath.isEmpty()) {
            secretValue = getSecretContent(baseUrl, secretPath, authToken, !secretFile.isEmpty())
        }

        println(secretValue)
    }

    def getSecretContent(url:String, endPoint:String, authToken:String, isSecretFile:Boolean): String = {
        var httpClient = createAcceptAllClient()
        val httpGet = new HttpGet(url+endPoint)

        httpGet.addHeader(HttpHeaders.AUTHORIZATION, "token="+authToken)

        val httpResponse = httpClient.execute(httpGet)
        val entity = httpResponse.getEntity()
        val resContent = IOUtils.toString(entity.getContent, StandardCharsets.UTF_8)
	println("Fetched Secret Content: " + resContent)

        httpClient.close()

	if(isSecretFile) {
		resContent
	} else {
	        val resJson = parse(resContent).extract[SecretResponse]
        	resJson.value
	}
    }

    def createAcceptAllClient(): CloseableHttpClient = {
        val sslContext = SSLContextBuilder.create().loadTrustMaterial(new TrustAllStrategy()).build()
        val allowAllHosts = new NoopHostnameVerifier()
        val connectionFactory = new SSLConnectionSocketFactory(sslContext, allowAllHosts)
        return HttpClients
                .custom()
                .setSSLSocketFactory(connectionFactory)
                .build()
    }
}
