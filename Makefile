.PHONY: run export setup clean-pyc

VENV := .venv
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

run:
	$(PYTHON) product_catalog/run_all.py

export:
	EXPORT_EXCEL_FILES="$(FILES)" $(PYTHON) product_catalog/export_template_mapping.py
# 	FILES="BM_AIS_Resource Specification_v1.3.xlsx|BM_AIS_Product Specification_v1.3.xlsx|BM_AIS_MasterCharacteristics_v1.3.xlsx"

setup:
	python3 -m venv $(VENV)
	$(PIP) install -r requirements.txt

clean-pyc:
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
