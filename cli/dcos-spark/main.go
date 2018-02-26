package main

import (
	"encoding/json"
	"errors"
	"fmt"
	"github.com/mesosphere/dcos-commons/cli"
	"github.com/mesosphere/dcos-commons/cli/client"
	"gopkg.in/alecthomas/kingpin.v3-unstable"
	"log"
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
	secretPath		  string

	statusSkipMessage bool

	logFollow bool
	logLines  uint
	logFile   string
}

func (cmd *SparkCommand) runSubmit(a *kingpin.Application, e *kingpin.ParseElement, c *kingpin.ParseContext) error {
	jsonPayload, err := buildSubmitJson(cmd)
	if err != nil {
		return err
	}
	responseBytes, err := client.HTTPServicePostJSON(
		fmt.Sprintf("/v1/submissions/create/%s", cmd.submissionId), jsonPayload)
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

func handleCommands(app *kingpin.Application) {
	cmd := &SparkCommand{submitEnv: make(map[string]string)}
	run := app.Command("run", "Submit a job to the Spark Mesos Dispatcher").Action(cmd.runSubmit)

	run.Flag("submit-args", fmt.Sprintf("Arguments matching what would be sent to 'spark-submit': %s",
		sparkSubmitHelp())).Required().PlaceHolder("ARGS").StringVar(&cmd.submitArgs)
	// TODO this should be moved to submit args
	run.Flag("docker-image", "Docker image to run the job within").
		Default("").
		StringVar(&cmd.submitDockerImage)
	run.Flag("env", "Environment variable(s) to pass into the Spark job.").
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
	log.Flag("lines_count", "Print the last N lines.").
		Default("10").UintVar(&cmd.logLines) //TODO "lines"?
	log.Flag("file", "Specify the sandbox file to print.").
		Default("stdout").StringVar(&cmd.logFile)
	log.Arg("submission-id", "The ID of the Spark job").Required().StringVar(&cmd.submissionId)

	kill := app.Command("kill", "Aborts a submitted Spark job").Action(cmd.runKill)
	kill.Arg("submission-id", "The ID of the Spark job").Required().StringVar(&cmd.submissionId)

	secret := app.Command("secret", "Make a shared secret, used for RPC authentication").
		Action(cmd.runGenerateSecret)
	secret.Arg("secret_path", "path and name for the secret").Required().StringVar(&cmd.secretPath)

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
