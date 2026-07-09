.PHONY: run skip export setup clean-pyc \
	step1 step2 step3 step4 step5 step6 step7 step8 step9 step10 step11 step12 step13 step14 step15

VENV := .venv
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip
RUN := $(PYTHON) product_catalog/run_all.py

run:
	$(RUN)

# skip to a specific step:  make skip STEP=5
skip:
	$(RUN) --skip-to=$(STEP)

# Individual step shortcuts
step1:  ; $(RUN) --skip-to=1
step2:  ; $(RUN) --skip-to=2
step3:  ; $(RUN) --skip-to=3
step4:  ; $(RUN) --skip-to=4
step5:  ; $(RUN) --skip-to=5
step6:  ; $(RUN) --skip-to=6
step7:  ; $(RUN) --skip-to=7
step8:  ; $(RUN) --skip-to=8
step9:  ; $(RUN) --skip-to=9
step10: ; $(RUN) --skip-to=10
step11: ; $(RUN) --skip-to=11
step12: ; $(RUN) --skip-to=12
step13: ; $(RUN) --skip-to=13
step14: ; $(RUN) --skip-to=14
step15: ; $(RUN) --skip-to=15
step16: ; $(RUN) --skip-to=16
step17: ; $(RUN) --skip-to=17

export:
	EXPORT_EXCEL_FILES="$(FILES)" $(PYTHON) product_catalog/export_template_mapping.py
# 	FILES="BM_AIS_Resource Specification_v1.3.xlsx|BM_AIS_Product Specification_v1.3.xlsx|BM_AIS_MasterCharacteristics_v1.3.xlsx"
#	FILES="BM_AIS_MetaExtension_Promotion_v1.3.xlsx" make export

setup:
	python3 -m venv $(VENV)
	$(PIP) install -r requirements.txt

clean-pyc:
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
