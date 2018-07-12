package main

import (
	"fmt"
	"errors"
	"crypto/rand"
	"encoding/base64"
	"github.com/mesosphere/dcos-commons/cli/client"
	"strings"
)


const KEYLENGTH = 128

var TASK_TYPES = []string{"driver", "executor"}

var SECRET_REFERENCE_PROPERTIES = map[string]string{
	"driver": "spark.mesos.driver.secret.names",
	"executor": "spark.mesos.executor.secret.names",
}

var SECRET_FILENAME_PROPERTIES = map[string]string{
	"driver": "spark.mesos.driver.secret.filenames",
	"executor": "spark.mesos.executor.secret.filenames",
}

var SECRET_ENVKEY_PROPERTIES = map[string]string{
	"driver": "spark.mesos.driver.secret.envkeys",
	"executor": "spark.mesos.executor.secret.envkeys",
}

const SPARK_KDC_HOSTNAME_KEY = "SPARK_SECURITY_KERBEROS_KDC_HOSTNAME"
const SPARK_KDC_PORT_KEY = "SPARK_SECURITY_KERBEROS_KDC_PORT"
const SPARK_KERBEROS_REALM_KEY = "SPARK_SECURITY_KERBEROS_REALM"
const SPARK_KERBEROS_KRB5_BLOB = "SPARK_MESOS_KRB5_CONF_BASE64"


// utility function used by SASL and Kerberos for user-defined secrets that may be base64 encoded blobs
// basically removes the prefix while ignoring the secret directory structure
func prepareBase64Secret(secretPath string) string {
	// this should never happen as validate inputs should always be upstream of calling this function
	if secretPath == "" {
		panic("Secret path cannot be empty")
	}

	absoluteSecretPath := strings.Split(secretPath, "/")
	filename := absoluteSecretPath[len(absoluteSecretPath) - 1]
	// secrets with __dcos_base64__ will be decoded by Mesos, but remove the prefix here
	if strings.HasPrefix(filename, "__dcos_base64__") {
		return strings.TrimPrefix(filename, "__dcos_base64__")
	}
	return filename
}

// TLS
func SetupTLS(args *sparkArgs) error {
	if args.keystoreSecretPath != "" {
		err := validateTLSArgs(args)
		if err != nil {
			return err
		}
		setupTLSArgs(args)
	}
	return nil
}

func validateTLSArgs(args *sparkArgs) error {
	// Make sure passwords are set
	if args.keystorePassword == "" || args.privateKeyPassword == "" {
		return errors.New("Need to provide keystore password and key password with keystore")
	}

	if args.truststoreSecretPath != "" {
		if args.truststorePassword == "" {
			return errors.New("Need to provide truststore password with truststore")
		}
	}
	return nil
}

func setupTLSArgs(args *sparkArgs) {
	args.properties["spark.mesos.containerizer"] = "mesos"
	args.properties["spark.ssl.enabled"] = "true"

	// Keystore and truststore
	const keyStoreFileName = "server.jks"
	const trustStoreFileName = "trust.jks"
	addPropertyAndWarn(args, "spark.ssl.keystore", keyStoreFileName)

	// Secret paths, filenames, and place holder envvars
	paths := []string{args.keystoreSecretPath}
	filenames := []string{keyStoreFileName}
	envkeys := []string{"DCOS_SPARK_KEYSTORE"}

	if args.truststoreSecretPath != "" {  // optionally add the truststore configs also
		addPropertyAndWarn(args, "spark.ssl.trustStore", trustStoreFileName)
		setPropertyToDefaultIfNotSet(args, "spark.ssl.trustStorePassword", args.truststorePassword)
		paths = append(paths, args.truststoreSecretPath)
		filenames = append(filenames, trustStoreFileName)
		envkeys = append(envkeys, "DCOS_SPARK_TRUSTSTORE")
	}

	joinedPaths := strings.Join(paths, ",")
	joinedFilenames := strings.Join(filenames, ",")
	joinedEnvkeys := strings.Join(envkeys, ",")

	for _, taskType := range TASK_TYPES {
		appendToProperty(SECRET_REFERENCE_PROPERTIES[taskType], joinedPaths, args)
		appendToProperty(SECRET_FILENAME_PROPERTIES[taskType], joinedFilenames, args)
		appendToPropertyIfSet(SECRET_ENVKEY_PROPERTIES[taskType], joinedEnvkeys, args)
	}

	// Passwords
	setPropertyToDefaultIfNotSet(args, "spark.ssl.keyStorePassword", args.keystorePassword)
	setPropertyToDefaultIfNotSet(args, "spark.ssl.keyPassword", args.privateKeyPassword)

	// Protocol
	setPropertyToDefaultIfNotSet(args, "spark.ssl.protocol", "TLS")
}

// SASL Executor encryption and authentication
func SetupSASL(args *sparkArgs) {
	if args.saslSecret != "" {
		setupSaslProperties(args)
	}
}

func setupSaslProperties(args *sparkArgs) {
	secretPath := args.saslSecret
	args.properties["spark.mesos.containerizer"] = "mesos"
	args.properties["spark.authenticate"] = "true"
	args.properties["spark.authenticate.enableSaslEncryption"] = "true"
	args.properties["spark.authenticate.secret"] = "spark_shared_secret"
	args.properties["spark.executorEnv._SPARK_AUTH_SECRET"] = "spark_shared_secret"
	for _, taskType := range TASK_TYPES {
		appendToProperty(SECRET_REFERENCE_PROPERTIES[taskType], secretPath, args)
		appendToProperty(SECRET_FILENAME_PROPERTIES[taskType], prepareBase64Secret(secretPath), args)
		appendToPropertyIfSet(SECRET_ENVKEY_PROPERTIES[taskType], prepareBase64Secret(secretPath), args)
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
func SetupKerberos(args *sparkArgs) error {
	kerberosPrincipal := getPrincipal(args)
	if kerberosPrincipal != "" {
		err := validateKerberosInputs(args)
		if err != nil {
			return err
		}

		// Set principal
		client.PrintMessage("Using Kerberos principal '%s'", kerberosPrincipal)

		// re-assign if the user used spark.yarn.principal
		args.properties["spark.yarn.principal"] = args.kerberosPrincipal

		// mesos secrets
		err = setupKerberosSecretsConfigs(args)
		if err != nil {
			return err
		}
	}
	return nil
}

func getPrincipal(args *sparkArgs) string {
	principal, contains := args.properties["spark.yarn.principal"]
	if contains {
		return principal
	}
	return args.kerberosPrincipal
}

func validateKerberosInputs(args *sparkArgs) error {
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

func addConfigForKerberosKeytabs(args *sparkArgs, secretPath, property string) {
	keytabEnvVarPlaceholder := "DCOS_SPARK_KERBEROS_KEYTAB"
	for _, taskType := range TASK_TYPES {
		appendToProperty(SECRET_REFERENCE_PROPERTIES[taskType], secretPath, args)
		appendToProperty(SECRET_FILENAME_PROPERTIES[taskType], prepareBase64Secret(secretPath), args)
		appendToPropertyIfSet(SECRET_ENVKEY_PROPERTIES[taskType], keytabEnvVarPlaceholder, args)
	}
	args.properties[property] = prepareBase64Secret(secretPath)
}

func setupKerberosSecretsConfigs(args *sparkArgs) error {
	args.properties["spark.mesos.containerizer"] = "mesos"
	if args.keytabSecretPath != "" { // using keytab secret
		addConfigForKerberosKeytabs(args, args.keytabSecretPath, "spark.yarn.keytab")
		return nil
	}
	if args.tgtSecretPath != "" { // using tgt secret
		addConfigForKerberosKeytabs(args, args.tgtSecretPath, "spark.mesos.driverEnv.KRB5CCNAME")
		return nil
	}
	if args.tgtSecretValue != "" { // using secret by value
		appendToProperty("spark.mesos.driver.secret.values", args.tgtSecretValue, args)
		args.properties["spark.mesos.driverEnv.KRB5CCNAME"] = "tgt"
		appendToProperty(SECRET_FILENAME_PROPERTIES["driver"], "tgt.base64", args)
		return nil
	}
	return errors.New(fmt.Sprintf("Unable to add Kerberos args, got args %v", args))
}
