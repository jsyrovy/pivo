# Load secrets from `.env` for local runs when the file exists.
# In CI `.env` is absent, so this is empty and values come from the environment.
ENV_FILE := $(if $(wildcard .env),--env-file .env,)

.DEFAULT:
	help

help:
	@echo "I don't know what you want me to do."

run-pivni-valka:
	uv run --no-dev $(ENV_FILE) run_pivni_valka.py

run-pivni-valka-notificationless:
	uv run --no-dev $(ENV_FILE) run_pivni_valka.py --notificationless

run-pivni-valka-local:
	uv run --no-dev $(ENV_FILE) run_pivni_valka.py --local

publish-pivni-valka:
	uv run --no-dev run_pivni_valka.py --publish

publish-nabidka:
	uv run --no-dev run_nabidka.py

publish-all:
	$(MAKE) clean-dist
	$(MAKE) publish-pivni-valka
	$(MAKE) publish-nabidka
	cp web/* dist/
	cp untappd_pairing/pairings.json dist/nabidka/pairings.json

clean-dist:
	rm -rf dist/

test-pivni-valka:
	uv run --dev pytest tests/pivni_valka

run-archivist:
	uv run --no-dev $(ENV_FILE) run_archivist.py

run-untappd-pairing:
	uv run --no-dev $(ENV_FILE) run_untappd_pairing.py

run-untappd-pairing-local:
	uv run --no-dev $(ENV_FILE) run_untappd_pairing.py --local

mypy:
	uv run --dev -m mypy --ignore-missing-imports --strict  --exclude tests .
	uv run --dev -m mypy --ignore-missing-imports  tests

remove-pivni-valka-stats-duplicates:
	echo "$$(uniq pivni_valka/stats.csv)" > pivni_valka/stats.csv

format:
	uvx ruff format

test:
	uv run --dev -m pytest

coverage:
	uv run --dev -m coverage run -m pytest
	uv run --dev -m coverage report -m

save-db-to-file:
	uv run --no-dev -m run_tool save-db-to-file

before-commit:
	make format
	make format-html
	make test
	make lint-fix
	make lint-html
	make mypy

ipython:
	uv run --dev python -c "import IPython;IPython.terminal.ipapp.launch_new_instance();"

lint:
	uvx ruff check

lint-fix:
	uvx ruff check --fix

lint-html:
	uvx djlint templates/ --lint

format-html:
	uvx djlint templates/ --reformat

ty:
	uvx ty check