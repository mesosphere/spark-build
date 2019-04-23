package main

import (
	"bytes"
	"fmt"
	"io"
	"io/ioutil"
	"net/http"
	"testing"

	"github.com/mesosphere/dcos-commons/cli/client"
	"github.com/stretchr/testify/assert"
)

func createHttpResponseWithStatus(statusCode int, filename string) http.Response {
	status := fmt.Sprintf("%v %s", statusCode, http.StatusText(statusCode))
	var body io.ReadCloser
	if filename != "" {
		content, _ := ioutil.ReadFile(filename)
		body = ioutil.NopCloser(bytes.NewBuffer(content))
	}
	return http.Response{StatusCode: statusCode, Status: status, Body: body}
}

func TestUnauthorizedResponseCustomCheck(t *testing.T) {
	response := createHttpResponseWithStatus(http.StatusUnauthorized, "testdata/responses/unauthorized.html")
	testMethod := "GET"
	testUrl := "https://example.com/marathon/v2/apps/spark"
	request, _ := http.NewRequest(testMethod, testUrl, bytes.NewReader(nil))
	response.Request = request

	client.SetCustomResponseCheck(checkForUnauthorized)
	_, err := client.CheckHTTPResponse(&response, nil)

	expectedErrorMessage := fmt.Sprintf("%s request to %s was not authorized. Make sure you are logged in.",
		testMethod, testUrl)
	assert.Equal(t, err.Error(), expectedErrorMessage)
}
