SHELL := /bin/bash

.PHONY: check dev stop smoke p2-check package

check:
	@./scripts/check.sh

dev:
	@./scripts/start-dev.sh

stop:
	@./scripts/stop-dev.sh

smoke:
	@python3 tests_e2e/smoke_test.py

p2-check:
	@./scripts/check-p2.sh

package:
	@./scripts/package.sh
