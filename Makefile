# source /Users/milk/_AIS/product_catalog2/.venv/bin/activate
.PHONY: run skip export setup clean-pyc po-group \
	step1 step2 step3 step4 step5 step6 step7 step8 step9 step10 step11 step12 step13 step14 step15

VENV := .venv
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip
RUN := $(PYTHON) product_catalog/run_all.py

# Microsoft ODBC Driver 18 on macOS needs Homebrew's OpenSSL library path.
ifeq ($(shell uname -s),Darwin)
OPENSSL_LIB := $(shell brew --prefix openssl@3 2>/dev/null)/lib
ODBC_ENV := DYLD_LIBRARY_PATH="$(OPENSSL_LIB):$(DYLD_LIBRARY_PATH)"
else
ODBC_ENV :=
endif

run:
	$(ODBC_ENV) $(RUN)

# skip to a specific step:  make skip STEP=5
skip:
	$(ODBC_ENV) $(RUN) --skip-to=$(STEP)

# Individual step shortcuts
step1:  ; $(ODBC_ENV) $(RUN) --skip-to=1
step2:  ; $(ODBC_ENV) $(RUN) --skip-to=2
step3:  ; $(ODBC_ENV) $(RUN) --skip-to=3
step4:  ; $(ODBC_ENV) $(RUN) --skip-to=4
step5:  ; $(ODBC_ENV) $(RUN) --skip-to=5
step6:  ; $(ODBC_ENV) $(RUN) --skip-to=6
step7:  ; $(ODBC_ENV) $(RUN) --skip-to=7
step8:  ; $(ODBC_ENV) $(RUN) --skip-to=8
step9:  ; $(ODBC_ENV) $(RUN) --skip-to=9
step10: ; $(ODBC_ENV) $(RUN) --skip-to=10
step11: ; $(ODBC_ENV) $(RUN) --skip-to=11
step12: ; $(ODBC_ENV) $(RUN) --skip-to=12
step13: ; $(ODBC_ENV) $(RUN) --skip-to=13
step14: ; $(ODBC_ENV) $(RUN) --skip-to=14
step15: ; $(ODBC_ENV) $(RUN) --skip-to=15
step16: ; $(ODBC_ENV) $(RUN) --skip-to=16
step17: ; $(ODBC_ENV) $(RUN) --skip-to=17
step18: ; $(ODBC_ENV) $(RUN) --skip-to=18

po-group:
	$(ODBC_ENV) $(PYTHON) product_catalog/po_grouper.py

export:
	$(ODBC_ENV) EXPORT_EXCEL_FILES="$(FILES)" $(PYTHON) product_catalog/export_template_mapping.py
# 	FILES="BM_AIS_Resource Specification_v1.3.xlsx|BM_AIS_Product Specification_v1.3.xlsx|BM_AIS_MasterCharacteristics_v1.3.xlsx"
#	FILES="BM_AIS_MetaExtension_Promotion_v1.3.xlsx" make export

setup:
	python3 -m venv $(VENV)
	$(PIP) install -r requirements.txt

clean-pyc:
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
