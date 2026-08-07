# Running product_catalog in Docker

Two services, defined in `docker-compose.yml`:

- **mysql** — MySQL 8.0 with a named volume (`mysql_data`) for persistence.
- **db-init** — one-shot job that installs every stored procedure/function found
  in `product_catalog/sql/` (via `product_catalog/install_sql.py`, which reuses
  `sql_runner.split_mysql_script` so `DELIMITER`-based bodies split correctly).
  Runs once after MySQL reports healthy, then exits. Safe to re-run any time —
  every `.sql` file does `DROP ... IF EXISTS` before `CREATE`.
- **app** — the Python image (`Dockerfile`), used to run `make run` / `make export` /
  `make po-group` etc. Its `.venv/bin/python` is a venv created with
  `--system-site-packages` purely so the existing Makefile (which hardcodes
  `VENV := .venv`) works unmodified inside the container.

## Quick start

```bash
# 1. Create your env file (same as running locally)
cp product_catalog/.env.example product_catalog/.env
#    edit product_catalog/.env: SOURCE_PRODUCT_TABLE, TYPHOON_API_KEY, etc.
#    DB_HOST/DB_PORT/DB_USER/DB_PASSWORD/DB_NAME are overridden by
#    docker-compose.yml (mysql/3306/root/changeme/product_catalog) — no need to
#    edit those for Docker use, but do change the MySQL root password in
#    docker-compose.yml for anything beyond local dev.

# 2. Build the image
make docker-build

# 3. Start MySQL and install the stored procedures/functions
make docker-init

# 4. Run the pipeline (or any other Make target) inside the app container
make docker-run CMD="make run"
make docker-run CMD="make export FILES=a.xlsx|b.xlsx"
make docker-run CMD="make po-group"

# ...or get an interactive shell
make docker-shell

# Stop everything
make docker-down
```

## Known gaps (this repo alone cannot run the full pipeline)

- `run_all.py`'s generate/translate flow calls five stored procedures that are
  **not** present in `product_catalog/sql/`: `generate_cdm_master`,
  `generate_ussd_master`, `generate_extension_cpc`,
  `generate_promotion_map_extension`, `generate_extension_group_type`. Steps
  12/13/15/16/18 of `make run` will fail against a freshly-initialized DB until
  those procedures are added (e.g. exported from your production database and
  dropped into `product_catalog/sql/`, then included in `install_sql.py`'s
  install order).
- The pipeline expects a legacy source table (`SOURCE_PRODUCT_TABLE` in
  `product_catalog/.env`, e.g. `PRODUCT_MST_20260508`) to already exist in the
  database — this repo does not ship any data. Import it yourself, e.g.:
  ```bash
  docker compose exec -T mysql mysql -uroot -pchangeme product_catalog < your_dump.sql
  ```
- `po_grouper.py` needs `category_new` and `PRODUCT_MST` data in the DB, plus a
  working `TYPHOON_API_KEY` in `product_catalog/.env` for AI-assisted grouping.

## Requirements

Requires Docker Compose v2.20+ (for the `service_completed_successfully`
condition used by `app`'s dependency on `db-init`). Check with `docker compose version`.

## Persistence

- MySQL data persists in the `mysql_data` named volume across
  `docker compose down` / `up` (use `docker compose down -v` to wipe it).
- `product_catalog/`, `template/`, `export/`, `.translation_cache.json`,
  `typhoon_cat_cache.json`, and `typhoon_series_cache.json` are bind-mounted
  from the host, so translation/AI caches and exported files land on your host
  filesystem, not just inside the container.
