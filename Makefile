.PHONY: run export setup clean-pyc

VENV := .venv
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

run:
	$(PYTHON) product_catalog/run_all.py

export:
	$(PYTHON) product_catalog/export_template_mapping.py

setup:
	python3 -m venv $(VENV)
	$(PIP) install -r requirements.txt

clean-pyc:
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
