dist:
	bin/dist.sh

docker:
	bin/docker.sh

test:
	bin/test.sh

.PHONY: dist docker test
