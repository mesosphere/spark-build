docker:
	bin/make-docker.sh

build:
	bin/build.sh

test:
	bin/test.sh

dist:
	bin/dist.sh

.PHONY: build test
