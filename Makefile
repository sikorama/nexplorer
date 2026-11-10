VENV   := .venv
PYTHON := $(VENV)/bin/python
STAMP  := $(VENV)/.installed

.PHONY: help venv run test clean mrproper

help:
	@echo "make venv      create .venv and install nexplorer with dev dependencies"
	@echo "make run       run nexplorer through .venv (ARGS=... to pass arguments)"
	@echo "make test      run pytest through .venv (ARGS=... to pass arguments)"
	@echo "make clean     remove build outputs and caches"
	@echo "make mrproper  clean, and remove .venv too"

venv: $(STAMP)

$(STAMP): pyproject.toml
	python3 -m venv $(VENV)
	$(PYTHON) -m pip install -e '.[dev]'
	touch $(STAMP)

run: venv
	$(PYTHON) -m nexplorer $(ARGS)

test: venv
	$(PYTHON) -m pytest $(ARGS)

clean:
	rm -rf build dist .pytest_cache *.egg-info
	find . -name __pycache__ -type d -prune -not -path './$(VENV)/*' -exec rm -rf {} +

mrproper: clean
	rm -rf $(VENV)
