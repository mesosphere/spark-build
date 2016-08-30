docker:
	bin/make-docker.sh

build:
	bin/build.sh

test:
	bin/test.sh

.PHONY: build test
