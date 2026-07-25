SHELL := /bin/bash

.PHONY: check dev stop smoke package

check:
	@./scripts/check.sh

dev:
	@./scripts/start-dev.sh

stop:
	@./scripts/stop-dev.sh

smoke:
	@python3 tests_e2e/smoke_test.py

package:
	@./scripts/package.sh
