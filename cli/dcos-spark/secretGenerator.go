package main

import (
	"crypto/rand"
	"encoding/base64"
)

const KEYLENGTH = 128

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

