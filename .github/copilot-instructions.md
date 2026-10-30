# Copilot Instructions

## Project Overview

This repository is a Python and SQL Server data migration/export workflow. The Python orchestration code is under `product_catalog/`, SQL Server scripts are in `product_catalog/sql/`, and the Excel header template is in `template/`.

Key modules:

- `product_catalog/run_all.py` orchestrates the database reset/load and generate/translate flow.
- `product_catalog/translation.py` handles database configuration, connections, and ID translation.
- `product_catalog/sql_runner.py` splits SQL Server scripts at standalone `GO` batch separators.
- `product_catalog/export_template_mapping.py` exports database mappings to XLSX and CSV.
- `product_catalog/po_grouper.py` groups product offering data.

## Setup and Commands

- Dependencies are listed in `requirements.txt`.
- Setup is documented for Python 3.11 or 3.12 in `product_catalog/start.md`; `make setup` creates `.venv` and installs the requirements.
- `make run` runs the full workflow. `make skip STEP=5` resumes the generation flow at step 5 using the latest batch.
- `make po-group` runs the PO grouping utility.
- `make export` runs the template mapping export. Pass the desired workbook names through `FILES`, separated by `|`.
- Make targets use POSIX shell commands and `.venv/bin/python`, so they are intended for macOS/Linux or a compatible shell. On Windows, use an activated virtual environment and invoke the relevant Python script directly.
- There is currently no test suite or test target. Keep checks scoped to the changed behavior and do not claim tests were run when they were not.

## Configuration and Safety

- Copy `product_catalog/.env.example` to `product_catalog/.env` and set database values locally. `.env` is ignored; never commit credentials or replace the example with real secrets.
- The workflow connects to a live SQL Server through ODBC Driver 18. Database-dependent commands require valid credentials, network access, and the ODBC driver.
- **Do not run `make run` against a shared or production database without explicit authorization.** The full flow resets sequence state, drops generated tables and views, and recreates/loads data.
- The SQL scripts are SQL Server/T-SQL. Preserve standalone `GO` batch separators; they are client-side delimiters and must not be sent as SQL statements.

## Change Guidance

- Keep Python orchestration, SQL procedure definitions, and export behavior aligned when changing their shared data contract.
- Preserve the existing environment-variable configuration pattern and validate external identifiers before interpolating them into SQL.
- Avoid unrelated cleanup; there are no automated tests to catch broad regressions.
