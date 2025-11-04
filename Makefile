BOLD := \033[1m
RESET := \033[0m

.DEFAULT: help

.PHONY: help
help:
	@echo "$(BOLD)CLI$(RESET)"
	@echo ""
	@echo "$(BOLD)make install$(RESET)"
	@echo "    install all requirements"
	@echo ""
	@echo "$(BOLD)make update$(RESET)"
	@echo "    update all requirements"
	@echo ""
	@echo "$(BOLD)make setup_dev$(RESET)"
	@echo "    install all requirements and setup for development"
	@echo ""
	@echo "$(BOLD)make test$(RESET)"
	@echo "    run tests"
	@echo ""
	@echo "$(BOLD)make mypy$(RESET)"
	@echo "    run static type checker (mypy)"
	@echo ""
	@echo "$(BOLD)make clean$(RESET)"
	@echo "    clean trash like *.pyc files"
	@echo ""
	@echo "$(BOLD)make install_pre_commit$(RESET)"
	@echo "    install pre_commit hook for git, "
	@echo "    so that linters will check up code before every commit"
	@echo ""
	@echo "$(BOLD)make pre_commit$(RESET)"
	@echo "    run linters check up"
	@echo ""

.PHONY: install
install:
	@echo "$(BOLD)Installing package$(RESET)"
	@poetry config virtualenvs.create false
	@poetry install --only main
	@echo "$(BOLD)Done!$(RESET)"

.PHONY: update
update:
	@echo "$(BOLD)Updating package and dependencies$(RESET)"
	@poetry update
	@echo "$(BOLD)Done!$(RESET)"

.PHONY: setup_dev
setup_dev:
	@echo "$(BOLD)DEV setup$(RESET)"
	@poetry install --only dev
	@echo "$(BOLD)Done!$(RESET)"

.PHONY: clean
clean:
	@echo "$(BOLD)Cleaning up repository$(RESET)"
	@find . -name \*.pyc -delete
	@echo "$(BOLD)Done!$(RESET)"

.PHONY: test
test: setup_dev
	@echo "$(BOLD)Running tests$(RESET)"
	@poetry run pytest --maxfail=2 ${ARGS}
	@echo "$(BOLD)Done!$(RESET)"

.PHONY: mypy
mypy: setup_dev
	@echo "$(BOLD)Running static type checker (mypy)$(RESET)"
	@poetry run mypy --no-error-summary --hide-error-codes --follow-imports=skip async_firebase
	@echo "$(BOLD)Done!$(RESET)"

.PHONY: install_pre_commit
install_pre_commit:
	@echo "$(BOLD)Add pre-commit hook for git$(RESET)"
	@pre-commit install
	@echo "$(BOLD)Done!$(RESET)"

.PHONY: pre_commit
pre_commit:
	@echo "$(BOLD)Run pre-commit$(RESET)"
	@pre-commit run --all-files
	@echo "$(BOLD)Done!$(RESET)"
