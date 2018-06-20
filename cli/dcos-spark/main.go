package main

import (
	"encoding/json"
	"errors"
	"fmt"
	"github.com/mesosphere/dcos-commons/cli"
	"github.com/mesosphere/dcos-commons/cli/client"
	"gopkg.in/alecthomas/kingpin.v3-unstable"
	"log"
	"net/http"
	"path"
	"strings"
)

func main() {
	app := cli.New()
	handleCommands(app)
	// Omit modname:
	kingpin.MustParse(app.Parse(cli.GetArguments()))
}

type SparkCommand struct {
	submissionId      string
	submitArgs        string
	submitDockerImage string
	submitEnv         map[string]string

	statusSkipMessage bool

	logFollow bool
	logLines  uint
	logFile   string

	secretPath string

	quotaRole  string
	quotaCpus  float64
	quotaMem   float64
	quotaGpus  int
	quotaForce bool
	quotaJson  bool
}

func (cmd *SparkCommand) runSubmit(a *kingpin.Application, e *kingpin.ParseElement, c *kingpin.ParseContext) error {
	marathonConfig, err := fetchMarathonConfig()
	if err != nil {
		return err
	}

	jsonPayload, err := buildSubmitJson(cmd, marathonConfig)
	if err != nil {
		return err
	}
	responseBytes, err := client.HTTPServicePostJSON("/v1/submissions/create", []byte(jsonPayload))
	if err != nil {
		log.Fatalf("Failed to create submission with error %s", err)
		//return err
	}

	responseJson := make(map[string]interface{})
	err = json.Unmarshal(responseBytes, &responseJson)
	if err != nil {
		log.Fatalf("Failed to unmarshal json with error %s", err)
		return err
	}

	err = checkSparkJSONResponse(responseJson)
	if err != nil {
		// Failure! Print the raw message:
		client.PrintJSONBytes(responseBytes)
		log.Fatalf("Failed to check spark dispatcher response with error %s", err)
		return err
	}

	// Success! Print the submissionId value:
	idObj, ok := responseJson["submissionId"]
	if ok {
		idString, ok := idObj.(string)
		if ok {
			// Match the older Python CLI's output:
			fmt.Printf("Run job succeeded. Submission id: %s\n", idString)
		} else {
			log.Fatalf("Failed to convert 'submissionId' field value to string: %s", responseJson)
		}
	} else {
		log.Fatalf("Failed to extract 'submissionId' field from JSON response: %s", responseJson)
	}
	return nil
}

func (cmd *SparkCommand) runStatus(a *kingpin.Application, e *kingpin.ParseElement, c *kingpin.ParseContext) error {
	responseBytes, err := client.HTTPServiceGet(fmt.Sprintf("/v1/submissions/status/%s", cmd.submissionId))
	if err != nil {
		client.PrintJSONBytes(responseBytes)
		return err
	}

	client.PrintJSONBytes(responseBytes)
	responseJson := make(map[string]interface{})
	err = json.Unmarshal(responseBytes, &responseJson)
	if err != nil {
		return err
	}

	if !cmd.statusSkipMessage {
		// Additionally, attempt to pretty-print the 'message' content, if any.
		// This is populated when the task has finished.
		messageObj, ok := responseJson["message"]
		if ok {
			messageString, ok := messageObj.(string)
			if ok {
				fmt.Printf("\nMessage:\n%s", messageString)
			} else {
				log.Printf("Failed to convert 'message' field value to string")
			}
		}
	}

	return checkSparkJSONResponse(responseJson)
}

func (cmd *SparkCommand) runLog(a *kingpin.Application, e *kingpin.ParseElement, c *kingpin.ParseContext) error {
	args := []string{"task", "log", "--completed"}
	if cmd.logFollow {
		args = append(args, "--follow")
	}
	if cmd.logLines != 0 {
		args = append(args, fmt.Sprintf("--lines=%d", cmd.logLines))
	}
	args = append(args, cmd.submissionId)
	if len(cmd.logFile) != 0 {
		args = append(args, cmd.logFile)
	}
	result, err := client.RunCLICommand(args...)
	// Always print output from CLI, which may contain user-facing errors (like 'log file not found'):
	fmt.Printf("%s\n", strings.TrimRight(result, "\n"))
	return err
}

func (cmd *SparkCommand) runKill(a *kingpin.Application, e *kingpin.ParseElement, c *kingpin.ParseContext) error {
	responseBytes, err := client.HTTPServicePost(fmt.Sprintf("/v1/submissions/kill/%s", cmd.submissionId))
	if err != nil {
		client.PrintJSONBytes(responseBytes)
		return err
	}
	client.PrintJSONBytes(responseBytes)
	responseJson := make(map[string]interface{})
	err = json.Unmarshal(responseBytes, &responseJson)
	if err != nil {
		return err
	}
	return checkSparkJSONResponse(responseJson)
}

func (cmd *SparkCommand) runWebui(a *kingpin.Application, e *kingpin.ParseElement, c *kingpin.ParseContext) error {
	// Hackish: Create the request we WOULD make, and print the resulting URL:
	fmt.Printf("%s\n", client.CreateServiceHTTPRequest("GET", "/ui").URL.String())
	return nil
}

func (cmd *SparkCommand) runGenerateSecret(a *kingpin.Application, e *kingpin.ParseElement, c *kingpin.ParseContext) error {
	secret, err := GetRandomStringSecret()

	if err != nil {
		return err
	}

	_, err = client.RunCLICommand(
		"security", "secrets", "create", cmd.secretPath, fmt.Sprintf("-v %s", secret))

	if err != nil {
		log.Fatalf("Unable to create secret, %s", err)
		return err
	}

	return err
}

type quotaScalar struct {
	Value float64 `json:"value"`
}

func createMesosQuotaRequest(method, quotaName string, jsonPayload []byte) *http.Request {
	// Get Mesos Quota URL: http://<dcos_url>/mesos/quota[/quotaName]
	var urlPath string
	if len(quotaName) != 0 {
		urlPath = path.Join("mesos", "quota", quotaName)
	} else {
		urlPath = path.Join("mesos", "quota")
	}
	mesosUrl := client.CreateURL(client.GetDCOSURL(), urlPath, "")
	return client.CreateHTTPRawRequest(method, mesosUrl, jsonPayload, "", "")
}

type quotaCreateGuarantee struct {
	Name   string      `json:"name"`
	Type   string      `json:"type"`
	Scalar quotaScalar `json:"scalar"`
}

type quotaCreateRequest struct {
	Role      string                 `json:"role"`
	Guarantee []quotaCreateGuarantee `json:"guarantee"`
	Force     bool                   `json:"force"`
}

func (cmd *SparkCommand) runQuotaCreate(a *kingpin.Application, e *kingpin.ParseElement, c *kingpin.ParseContext) error {
	requestValues := make([]quotaCreateGuarantee, 0)
	if cmd.quotaCpus != 0 {
		requestValues = append(requestValues, quotaCreateGuarantee{
			Name: "cpus",
			Type: "SCALAR",
			Scalar: quotaScalar{Value: cmd.quotaCpus},
		})
	}
	if cmd.quotaMem != 0 {
		requestValues = append(requestValues, quotaCreateGuarantee{
			Name: "mem",
			Type: "SCALAR",
			Scalar: quotaScalar{Value: cmd.quotaMem},
		})
	}
	if cmd.quotaGpus != 0 {
		requestValues = append(requestValues, quotaCreateGuarantee{
			Name: "gpus",
			Type: "SCALAR",
			Scalar: quotaScalar{Value: float64(cmd.quotaGpus)},
		})
	}
	if len(requestValues) == 0 {
		return fmt.Errorf("No quota resources were provided. Please specify resources to be assigned to this quota")
	}
	requestPayload := quotaCreateRequest{Role: cmd.quotaRole, Guarantee: requestValues, Force: cmd.quotaForce}
	requestBytes, err := json.Marshal(requestPayload)
	if err != nil {
		return err
	}
	// Ignore response content: If the command succeeded, the response is empty
	_, err = client.CheckHTTPResponse(client.HTTPQuery(createMesosQuotaRequest("POST", "", requestBytes)))
	if err != nil {
		return err
	}
	client.PrintMessage(`The requested quota for role '%s' has been successfully configured. This quota may be used in your Spark configuration:
- In the Dispatcher: 'dcos package install spark' with 'service.role' option configured
- In the Executors: 'dcos spark run' with '--conf spark.cores.max' and '--conf spark.mesos.role' options configured
For more information, see the Job Scheduling section of the documentation at http://docs.mesosphere.com/services/spark/`, cmd.quotaRole)
	return err
}

func (cmd *SparkCommand) runQuotaRemove(a *kingpin.Application, e *kingpin.ParseElement, c *kingpin.ParseContext) error {
	// Ignore response content: If the command succeeded, the response is empty
	_, err := client.CheckHTTPResponse(client.HTTPQuery(createMesosQuotaRequest("DELETE", cmd.quotaRole, nil)))
	if err != nil {
		return err
	}
	client.PrintMessage(`The quota for role '%s' has been successfully removed.`, cmd.quotaRole)
	return err
}

type quotaListGuarantee struct {
	Name   string      `json:"name"`
	Scalar quotaScalar `json:"scalar"`
	Type   string      `json:"type"` // not printed
}

type quotaListInfo struct {
	Guarantees []quotaListGuarantee `json:"guarantee"`
	Principal  string               `json:"principal"`
	Role       string               `json:"role"`
}

type quotaListResponse struct {
	Infos []quotaListInfo `json:"infos"`
}

func (cmd *SparkCommand) runQuotaList(a *kingpin.Application, e *kingpin.ParseElement, c *kingpin.ParseContext) error {
	responseBytes, err := client.CheckHTTPResponse(client.HTTPQuery(createMesosQuotaRequest("GET", "", nil)))
	if err != nil {
		return err
	}
	if cmd.quotaJson {
		client.PrintJSONBytes(responseBytes)
		return nil
	}
	var response quotaListResponse
	err = json.Unmarshal(responseBytes, &response)
	if err != nil {
		return err
	}
	switch len(response.Infos) {
	case 0:
		client.PrintMessage("No quotas are configured.")
	case 1:
		client.PrintMessage("1 quota entry:")
	default:
		client.PrintMessage("%d quota entries:", len(response.Infos))
	}
	for _, info := range response.Infos {
		resources := ""
		for _, guarantee := range info.Guarantees {
			resources += fmt.Sprintf(" %s=%g", guarantee.Name, guarantee.Scalar.Value)
		}
		client.PrintMessage("- role=%s:%s (principal=%s)", info.Role, resources, info.Principal)
	}
	return err
}

func handleCommands(app *kingpin.Application) {
	cmd := &SparkCommand{submitEnv: make(map[string]string)}

	run := app.Command("run", "Submit a job to the Spark Mesos Dispatcher").Action(cmd.runSubmit)
	run.Flag("submit-args", fmt.Sprintf("Arguments matching what would be sent to 'spark-submit': %s",
		sparkSubmitHelp())).Required().PlaceHolder("ARGS").StringVar(&cmd.submitArgs)
	// TODO this should be moved to submit args
	run.Flag("docker-image", "Docker image to run the job within").
		Default("").
		StringVar(&cmd.submitDockerImage)
	run.Flag("env", "Environment variable(s) to pass into the Spark job").
		Short('E').
		PlaceHolder("ENVKEY=ENVVAL").
		StringMapVar(&cmd.submitEnv)

	status := app.Command("status", "Retrieves the status of a submitted Spark job").
		Action(cmd.runStatus)
	status.Flag("skip-message", "Omit the additional printout of the 'message' field").
		BoolVar(&cmd.statusSkipMessage)
	status.Arg("submission-id", "The ID of the Spark job").Required().StringVar(&cmd.submissionId)

	log := app.Command("log", "Retrieves a log file from a submitted Spark job").Action(cmd.runLog)
	log.Flag("follow", "Dynamically update the log").BoolVar(&cmd.logFollow)
	log.Flag("lines_count", "Print the last N lines").
		Default("10").UintVar(&cmd.logLines) //TODO "lines"?
	log.Flag("file", "Specify the sandbox file to print").
		Default("stdout").StringVar(&cmd.logFile)
	log.Arg("submission-id", "The ID of the Spark job").Required().StringVar(&cmd.submissionId)

	kill := app.Command("kill", "Aborts a submitted Spark job").Action(cmd.runKill)
	kill.Arg("submission-id", "The ID of the Spark job").Required().StringVar(&cmd.submissionId)

	secret := app.Command("secret", "Make a shared secret, used for RPC authentication").
		Action(cmd.runGenerateSecret)
	secret.Arg("secret-path", "path and name for the secret").Required().StringVar(&cmd.secretPath)

	quota := app.Command("quota", "Manage service quotas with Mesos")
	quotaCreate := quota.Command("create", "Create a resource quota for a given role").Action(cmd.runQuotaCreate)
	quotaCreate.Arg("role", "Mesos role to create the quota against").Required().StringVar(&cmd.quotaRole)
	quotaCreate.Flag("cpus", "Amount of CPUs").Short('c').PlaceHolder("float").Float64Var(&cmd.quotaCpus)
	quotaCreate.Flag("mem", "Amount of Memory, in MB").Short('m').PlaceHolder("float").Float64Var(&cmd.quotaMem)
	quotaCreate.Flag("gpus", "Amount of GPUs").Short('g').PlaceHolder("int").IntVar(&cmd.quotaGpus)
	quotaCreate.Flag("force", "Force the role to be created, even if it doesn't fit").BoolVar(&cmd.quotaForce)
	quotaRemove := quota.Command("remove", "Remove a previously created quota for a given role").Action(cmd.runQuotaRemove)
	quotaRemove.Arg("role", "Mesos role to remove the quota from").Required().StringVar(&cmd.quotaRole)
	list := quota.Command("list", "List all currently assigned quotas").Alias("ls").Action(cmd.runQuotaList)
	list.Flag("json", "Show raw JSON response instead of user-friendly list").BoolVar(&cmd.quotaJson)

	app.Command("webui", "Returns the Spark Web UI URL").Action(cmd.runWebui)
}

func checkSparkJSONResponse(responseJson map[string]interface{}) error {
	// Parse out the 'success' value returned by Spark, to ensure that we return an error code when success=false:
	successObj, ok := responseJson["success"]
	if !ok {
		return errors.New("Missing 'success' field in response JSON")
	}
	successBool, ok := successObj.(bool)
	if !ok {
		return errors.
			New(fmt.Sprintf("Unable to convert 'success' field in response JSON to boolean: %s", successObj))
	}
	if !successBool {
		return errors.New("Spark returned success=false")
	}
	return nil
}
