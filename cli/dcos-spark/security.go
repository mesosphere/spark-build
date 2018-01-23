package main

import (
	"fmt"
	"errors"
	"crypto/rand"
	"encoding/base64"
	"strings"
	"log"
)


const KEYLENGTH = 128
const SECRET_REFERENCE_TEMPLATE = "spark.mesos.%s.secret.names"
const SECRET_FILENAME_TEMPLATE = "spark.mesos.%s.secret.filenames"
const SECRET_ENVKEY_TEMPLATE = "spark.mesos.%s.secret.envkeys"
const sparkKdcHostnameKey = "SPARK_SECURITY_KERBEROS_KDC_HOSTNAME"
const sparkKdcPortKey = "SPARK_SECURITY_KERBEROS_KDC_PORT"
const sparkKerberosRealmKey = "SPARK_SECURITY_KERBEROS_REALM"
const sparkKrb5ConfBase64BlobKey = "SPARK_MESOS_KRB5_CONF_BASE64"


func prepareBase64Secret(secretPath string) string {
	ss := strings.Split(secretPath, "/")
	// The secret file without any slashes
	fn := ss[len(ss) - 1]
	// secrets with __dcos_base64__ will be decoded by Mesos, but remove the prefix here
	if strings.HasPrefix(fn, "__dcos_base64__") {
		return strings.TrimPrefix(fn, "__dcos_base64__")
	}
	return fn
}

func addArgsForFileBasedSecret(args *sparkArgs, secretPath, property string) {
	taskTypes := []string{"driver", "executor"}
	for _, taskType := range taskTypes {
		secretRefProp := fmt.Sprintf(SECRET_REFERENCE_TEMPLATE, taskType)
		secretFileProp := fmt.Sprintf(SECRET_FILENAME_TEMPLATE, taskType)
		appendToProperty(secretRefProp, secretPath, args)
		appendToProperty(secretFileProp, prepareBase64Secret(secretPath), args)
	}
	args.properties[property] = prepareBase64Secret(secretPath)
}

func setupTLSArgs(args *sparkArgs) {
	args.properties["spark.mesos.containerizer"] = "mesos"
	args.properties["spark.ssl.enabled"] = "true"

	// Keystore and truststore
	const keyStoreFileName = "server.jks"
	const trustStoreFileName = "trust.jks"
	args.properties["spark.ssl.keyStore"] = keyStoreFileName
	if args.truststoreSecretPath != "" {
		args.properties["spark.ssl.trustStore"] = trustStoreFileName
	}

	// Secret paths, filenames, and place holder envvars
	paths := []string{args.keystoreSecretPath}
	filenames := []string{keyStoreFileName}
	envkeys := []string{"DCOS_SPARK_KEYSTORE"}
	if args.truststoreSecretPath != "" {
		paths = append(paths, args.truststoreSecretPath)
		filenames = append(filenames, trustStoreFileName)
		envkeys = append(envkeys, "DCOS_SPARK_TRUSTSTORE")
	}
	joinedPaths := strings.Join(paths, ",")
	joinedFilenames := strings.Join(filenames, ",")
	joinedEnvkeys := strings.Join(envkeys, ",")

	taskTypes := []string{"driver", "executor"}
	for _, taskType := range taskTypes {
		appendToProperty(fmt.Sprintf(SECRET_REFERENCE_TEMPLATE, taskType), joinedPaths, args)
		appendToProperty(fmt.Sprintf(SECRET_FILENAME_TEMPLATE, taskType), joinedFilenames, args)
		appendToPropertyIfSet(fmt.Sprintf(SECRET_ENVKEY_TEMPLATE, taskType), joinedEnvkeys, args)
	}

	// Passwords
	args.properties["spark.ssl.keyStorePassword"] = args.keystorePassword
	args.properties["spark.ssl.keyPassword"] = args.privateKeyPassword

	if args.truststoreSecretPath != "" {
		args.properties["spark.ssl.trustStorePassword"] = args.truststorePassword
	}

	// Protocol
	if _, ok := args.properties["spark.ssl.protocol"]; !ok {
		args.properties["spark.ssl.protocol"] = "TLS"
	}
}

func setupSaslProperties(secretPath string, args *sparkArgs) {
	args.properties["spark.mesos.containerizer"] = "mesos"
	args.properties["spark.authenticate"] = "true"
	args.properties["spark.authenticate.enableSaslEncryption"] = "true"
	args.properties["spark.authenticate.secret"] = "spark_shared_secret"
	args.properties["spark.executorEnv._SPARK_AUTH_SECRET"] = "spark_shared_secret"
	taskTypes := []string{"driver", "executor"}
	for _, taskType := range taskTypes {
		secretRefProp := fmt.Sprintf(SECRET_REFERENCE_TEMPLATE, taskType)
		secretFileProp := fmt.Sprintf(SECRET_FILENAME_TEMPLATE, taskType)
		appendToProperty(secretRefProp, secretPath, args)
		appendToProperty(secretFileProp, prepareBase64Secret(secretPath), args)
	}
}

func generateRandomBytes(n int) ([]byte, error) {
	// https://elithrar.github.io/article/generating-secure-random-numbers-crypto-rand/
	b := make([]byte, n)
	_, err := rand.Read(b)
	if err != nil {
		return nil, err
	}
	return b, nil
}

func GetRandomStringSecret() (string, error) {
	b, err := generateRandomBytes(KEYLENGTH)
	return base64.URLEncoding.EncodeToString(b), err
}

// KERBEROS

func ValidateInputs(args *sparkArgs) error {
	if args.keytabSecretPath == "" && args.tgtSecretPath == "" && args.tgtSecretValue == "" {
		return errors.New("need to provide Keytab secret, TGT secret, or TGT value " +
			"with Kerberos principal")
	}

	if args.keytabSecretPath != "" && (args.tgtSecretValue != "" || args.tgtSecretPath != "") {
		return errors.New("keytabs and TGTs cannot be used together")
	}

	if args.tgtSecretPath != "" && args.tgtSecretValue != "" {
		return errors.New("cannot use a TGT-by-value and a TGT-by-secret at the same time")
	}
	return nil
}

func GetPrincipal(args *sparkArgs) string {
	principal, contains := args.properties["spark.yarn.principal"]
	if contains {
		return principal
	} else {
		if args.kerberosPrincipal != "" {
			return args.kerberosPrincipal
		} else {
			return ""
		}
	}
}

func setupKerberosSecretsConfigs(args *sparkArgs) error {
	args.properties["spark.mesos.containerizer"] = "mesos"
	if args.keytabSecretPath != "" { // using keytab secret
		addArgsForFileBasedSecret(args, args.keytabSecretPath, "spark.yarn.keytab")
		return nil
	}
	if args.tgtSecretPath != "" { // using tgt secret
		addArgsForFileBasedSecret(args, args.tgtSecretPath, "spark.mesos.driverEnv.KRB5CCNAME")
		return nil
	}
	if args.tgtSecretValue != "" { // using secret by value
		appendToProperty("spark.mesos.driver.secret.values", args.tgtSecretValue, args)
		args.properties["spark.mesos.driverEnv.KRB5CCNAME"] = "tgt"
		appendToProperty(fmt.Sprintf(SECRET_FILENAME_TEMPLATE, "driver"), "tgt.base64", args)
		return nil
	}
	return errors.New(fmt.Sprintf("Unable to add Kerberos args, got args %s", args))
}

func propertyGiven(propValue string, err error) bool {
	if propValue == "" && err != nil {
		return false
	} else {
		return true
	}
}

func addEnvvarToDriverAndExecutor(args *sparkArgs, key, value string) {
	driverProp := fmt.Sprintf("spark.mesos.driverEnv.%s", key)
	executorProp := fmt.Sprintf("spark.executorEnv.%s", key)
	_, contains := args.properties[driverProp]
	if !contains {
		args.properties[driverProp] = value
	}
	_, contains = args.properties[executorProp]
	if !contains {
		args.properties[executorProp] = value
	}
}

func forwardEnvironmentVariablesFromMarathonConfig(args *sparkArgs, marathonJson map[string]interface{}) {
	krb5confBase64, errBase64Blob := getStringFromTree(marathonJson, []string{"app", "env", sparkKrb5ConfBase64BlobKey})
	kdcHostname, errHostname := getStringFromTree(marathonJson, []string{"app", "env", sparkKdcHostnameKey})
	kdcPort, errPort := getStringFromTree(marathonJson, []string{"app", "env", sparkKdcPortKey})
	kdcRealm, errRealm := getStringFromTree(marathonJson, []string{"app", "env", sparkKerberosRealmKey})

	// We allow the user to set SPARK_SECURITY_KERBEROS_KDC_HOSTNAME and SPARK_SECURITY_KERBEROS_KDC_PORT, and
	// SPARK_SECURITY_KERBEROS_REALM, these values will be used to template a krb5.conf. If the user sets
	// SPARK_MESOS_KRB5_CONF_BASE64 it will be overwritten, but log a warning to be sure.
	kdcPropCount := 0
	if propertyGiven(kdcHostname, errHostname) {
		log.Printf("Using %s for KDC hostname", kdcHostname)
		addEnvvarToDriverAndExecutor(args, sparkKdcHostnameKey, kdcHostname)
		kdcPropCount += 1
	}

	if propertyGiven(kdcPort, errPort) {
		log.Printf("Using %s for KDC port", kdcPort)
		addEnvvarToDriverAndExecutor(args, sparkKdcPortKey, kdcPort)
		kdcPropCount += 1
	}

	if propertyGiven(kdcRealm, errRealm) {
		log.Printf("Using %s for KDC realm", kdcRealm)
		addEnvvarToDriverAndExecutor(args, sparkKerberosRealmKey, kdcRealm)
		kdcPropCount += 1
	}

	if kdcPropCount > 0 && kdcPropCount != 3 {
		log.Printf("WARNING: Only some of the required 3 environment variables (%s, %s, %s) were " +
			"found for templating krb5.conf", sparkKdcHostnameKey, sparkKdcPortKey, sparkKerberosRealmKey)
	}

	if propertyGiven(krb5confBase64, errBase64Blob) {
		if kdcPropCount > 0 {
			log.Printf("WARNING: base64 encoded krb5.conf found (env key %s), overwriting %s " +
				"%s and %s", sparkKrb5ConfBase64BlobKey, sparkKdcHostnameKey, sparkKdcPortKey, sparkKerberosRealmKey)
		}
		addEnvvarToDriverAndExecutor(args, sparkKrb5ConfBase64BlobKey, krb5confBase64)
	} else {
		if kdcPropCount == 0 {
			log.Printf("No KDC krb5.conf parameters found in marathon configuration")
		}
	}
}
