docker:
	bin/make-docker.sh

universe:
	bin/universe.sh

test:
	bin/test.sh

dist:
	bin/dist.sh

.PHONY: docker universe test dist
