# Copilot Instructions for product_catalog

## What this is
A Python + MySQL ETL/migration pipeline that ingests a legacy `PRODUCT_MST` export,
loads it into normalized `tbl_*` tables via MySQL stored procedures, translates Thai
IDs/names to English (Google Translate + Typhoon LLM), and exports Excel reports
using a template mapping table. Most business logic lives in **SQL stored
procedures/functions** under `product_catalog/sql/`, not in Python — Python mainly
orchestrates procedure calls, handles things MySQL can't do (external translation
APIs, Excel I/O), and manages config/session bookkeeping.

## Setup & running
- `make setup` — creates `.venv` and installs `requirements.txt` (pymysql,
  deep-translator, openpyxl). Note: `po_grouper.py` additionally needs
  `pandas`, `numpy`, and `requests`, which are **not** in `requirements.txt` —
  install them manually if working on that script.
- Config lives in `product_catalog/.env` (copy from `product_catalog/.env.example`).
  It is parsed by a hand-rolled `load_env()` in `translation.py` (not python-dotenv),
  so only simple `KEY=VALUE` lines are supported.
- `make run` — runs the full pipeline (`product_catalog/run_all.py`).
- `make skip STEP=N` or `make stepN` (N=1..18) — resume the pipeline from a
  specific step using the latest `batch_id` from `ingest_batch` (see
  `--skip-to` in `run_all.py`). Steps 1-18 map to the ordered `step(...)` calls
  in `run_generate_flow()`; step 14 (installment master) is currently commented out.
- `make export FILES="a.xlsx|b.xlsx"` — runs `export_template_mapping.py`,
  driven by the `template_mapping` DB table and `template/excel_header_template.xlsx`.
- `make po-group` — runs `po_grouper.py` (AI-assisted PO grouping via Typhoon API).
- `make clean-pyc` — removes `__pycache__` dirs.
- There is no test suite, linter, or build step configured in this repo.

## Pipeline architecture (`run_all.py`)
1. **Reset & load** (`reset_and_load_product_mst`): drops all generated
   `tbl_*`/`v_*` objects, copies `SOURCE_PRODUCT_TABLE` into `stg_product_mst`,
   calls `staging_and_batch_tables()`, then installs and calls a special
   `load_product_mst_only` procedure — a runtime-patched copy of
   `load_product_mst` from `02_load_product_mst.sql` with the trailing
   `CALL generate_all(...)` block stripped out (via regex), so the Python
   driver controls each downstream step individually instead of one big
   in-DB transaction.
2. **Generate/translate flow** (`run_generate_flow`): a fixed sequence of
   `step(num, name, func, *args)` calls, each either invoking a MySQL stored
   procedure (`CALL procedure_name(...)`) or a Python translation job. Steps
   can be skipped via `--skip-to`.
3. Before each run, stale MySQL sessions holding a lock on the same database
   are detected via `SHOW FULL PROCESSLIST` and killed
   (`kill_stale_database_sessions`) to avoid lock timeouts.

## Translation conventions (`translation.py`)
- `IdTranslator` wraps `deep_translator.GoogleTranslator` (th→en) and caches
  every translated token in `.translation_cache.json` at the repo root — check
  this cache before assuming a translation call will hit the network.
- IDs are translated **token-by-token** (split on `_`), only translating tokens
  containing Thai characters (`has_thai_text`, regex `[ก-๙]`); non-Thai tokens
  pass through unchanged.
- `TranslationJob` (name, table_name, id_column, original_column, transform)
  describes one column-translation task. Adding a new translatable ID column
  means defining a new `TranslationJob` plus a `translate_*_id` transform
  function following the existing `translate_po_id` / `translate_variant_id` /
  `translate_promotion_id` pattern, then wiring it into `run_generate_flow`.
- Sequence numbers embedded in IDs (e.g. `...mg7` → `...mg007`) are normalized
  using `SequenceRule`s loaded from the `sequence_registry` table
  (`padding`, `prefix`, `suffix`); this normalization runs both before and
  after translation so padding survives translation.
- Every translation job auto-adds an `<ORIGINAL_COLUMN>` TEXT column (if
  missing) to preserve the pre-translation value, and an index on the ID
  column, before running.
- All dynamic SQL identifiers (table/column names) are validated against
  `SAFE_IDENTIFIER_PATTERN` (`^[A-Za-z0-9_]+$`) before being interpolated into
  queries — follow this pattern for any new dynamic SQL.

## SQL directory (`product_catalog/sql/`)
- Files are either numbered pipeline scripts (`00_notes.sql`, `01_...`,
  `02_...`, `03_generate_all.sql`) or individual `CREATE PROCEDURE ...().sql` /
  `CREATE FUNCTION ...().sql` files, one object per file.
- `sql_files.py::SQL_INSTALL_FILES` defines the **required install order**
  for these files (functions/procedures before the scripts that call them) —
  when adding a new procedure/function file, add it to this list in the
  correct dependency position.
- SQL comments and stored-procedure logic are written in Thai; keep new
  comments in the same style for consistency.
- Multi-statement `.sql` files are split by `sql_runner.py::split_mysql_script`,
  which understands `DELIMITER` changes — required for files defining
  triggers/procedures with `;` inside the body.

## Export & grouping scripts
- `export_template_mapping.py`: reads the `template_mapping` DB table plus
  `EXCEL_TEMPLATE_DIR`/`template/excel_header_template.xlsx`, and writes
  timestamped output under `EXPORT_OUTPUT_DIR/<timestamp>/{csv,xlsx}/`
  (git-ignored `export/`). Filter which source Excel files are processed via
  `EXPORT_EXCEL_FILES` env var (pipe-separated).
- `po_grouper.py`: groups products by category using DB data
  (`category_new`, `PRODUCT_MST`) and the Typhoon LLM API for
  low-confidence/unmatched cases, writing results to `po_group` and caching
  AI responses in `typhoon_cat_cache.json` / `typhoon_series_cache.json`
  (both git-ignored, safe to delete to force re-classification).

## Conventions
- Scripts add both `PROJECT_ROOT` and the `product_catalog` package dir to
  `sys.path` at import time (see the boilerplate at the top of `run_all.py`,
  `export_template_mapping.py`, `po_grouper.py`) so `import translation` and
  `from product_catalog....` both resolve — replicate this if adding a new
  top-level script.
- Long-running MySQL `CALL` statements print a terminal spinner
  (`call_procedure` in `sql_runner`/`run_all.py`) and per-step timings; keep
  new steps wrapped in `measure(...)` so they show up in the timing summary.
