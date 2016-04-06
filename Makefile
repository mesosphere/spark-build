docker:
	bin/make-docker.sh

package:
	bin/make-package.py

universe:
	bin/make-universe.sh

test:
	bin/test.sh

.PHONY: package docker universe test
