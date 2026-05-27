import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


THAI_TEXT_PATTERN = re.compile(r"[ก-๙]")
SAFE_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9_]+$")
SEQUENCE_TOKEN_PATTERN = re.compile(r"^([A-Za-z]+)(\d+)$")


@dataclass(frozen=True)
class DatabaseConfig:
    host: str
    port: int
    user: str
    password: str
    database: str


@dataclass(frozen=True)
class RunConfig:
    batch_id: int | None
    triggered_by: str
    sql_dir: Path
    source_product_table: str
    load_batch_name: str
    load_created_by: str


@dataclass(frozen=True)
class TranslationJob:
    name: str
    table_name: str
    id_column: str
    original_column: str
    transform: Callable[[str, "IdTranslator"], str] | None = None


@dataclass(frozen=True)
class SequenceRule:
    pattern: str
    prefix: str
    suffix: str
    padding: int


class IdTranslator:
    def __init__(self, source: str = "th", target: str = "en") -> None:
        from deep_translator import GoogleTranslator

        self.translator = GoogleTranslator(source=source, target=target)
        self.cache: dict[str, str] = {}
        self.sequence_rules: list[SequenceRule] = []

    def translate_id(self, value: str) -> str:
        parts = value.split("_")
        translated_parts = [
            self.translate_text(part) if has_thai_text(part) else part
            for part in parts
        ]
        return "_".join(translated_parts)

    def translate_text(self, text: str) -> str:
        if text in self.cache:
            return self.cache[text]

        try:
            translated = slugify(self.translator.translate(text))
        except Exception as error:
            print(f"Translate error: {text}")
            print(error)
            return text

        self.cache[text] = translated
        return translated


def load_env(env_path: Path) -> None:
    if not env_path.exists():
        return

    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def load_database_config(env_path: Path) -> DatabaseConfig:
    load_env(env_path)

    return DatabaseConfig(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", ""),
        database=os.getenv("DB_NAME", "product_catalog"),
    )


def load_run_config(env_path: Path) -> RunConfig:
    load_env(env_path)

    batch_id = parse_optional_int(os.getenv("BATCH_ID", ""))
    triggered_by = os.getenv("TRIGGERED_BY", "").strip() or "system"
    sql_dir = Path(os.getenv("SQL_DIR", "")).expanduser()
    source_product_table = os.getenv("SOURCE_PRODUCT_TABLE", "PRODUCT_MST_20260508")
    load_batch_name = os.getenv("LOAD_BATCH_NAME", "MIGRATE_DATA_20260508")
    load_created_by = os.getenv("LOAD_CREATED_BY", triggered_by).strip() or triggered_by

    return RunConfig(
        batch_id=batch_id,
        triggered_by=triggered_by,
        sql_dir=sql_dir,
        source_product_table=source_product_table,
        load_batch_name=load_batch_name,
        load_created_by=load_created_by,
    )


def parse_optional_int(value: str | None) -> int | None:
    if value is None or value.strip() == "":
        return None

    return int(value)


def connect_database(db_config: DatabaseConfig):
    import pymysql

    return pymysql.connect(
        host=db_config.host,
        port=db_config.port,
        user=db_config.user,
        password=db_config.password,
        database=db_config.database,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False,
    )


def slugify(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = re.sub(r"_+", "_", text)
    return text.strip("_")


def has_thai_text(text: str) -> bool:
    return bool(THAI_TEXT_PATTERN.search(text))


def translate_plain_id(value: str, translator: IdTranslator) -> str:
    return translator.translate_id(value)


def translate_po_id(value: str, translator: IdTranslator) -> str:
    base_value, sequence_suffix = split_sequence_suffix(value, translator.sequence_rules)
    translated = translator.translate_id(base_value) + sequence_suffix
    return normalize_sequence_parts(translated, translator.sequence_rules)


def translate_variant_id(value: str, translator: IdTranslator) -> str:
    parts = value.split("_")
    translated_parts = [translate_variant_part(part, translator) for part in parts]
    translated = "_".join(translated_parts)
    return normalize_sequence_parts(translated, translator.sequence_rules)


def translate_variant_part(part: str, translator: IdTranslator) -> str:
    if not has_thai_text(part):
        return part

    if part.endswith("-of"):
        return translator.translate_text(part[:-3]) + "-of"

    return translator.translate_text(part)


def split_sequence_suffix(value: str, rules: list[SequenceRule]) -> tuple[str, str]:
    for rule in sequence_rules_by_suffix_length(rules):
        if not rule.suffix:
            continue

        match = re.search(f"({re.escape(rule.suffix)})(\\d+)$", value)
        if match:
            suffix_start = match.start()
            digits = match.group(2).zfill(rule.padding)
            return value[:suffix_start], f"{rule.suffix}{digits}"

    return value, ""


def normalize_sequence_parts(value: str, rules: list[SequenceRule]) -> str:
    value = normalize_sequence_suffixes(value, rules)
    value = normalize_sequence_prefixes(value, rules)
    parts = value.split("_")
    return "_".join(normalize_sequence_token(part, rules) for part in parts)


def normalize_sequence_suffixes(value: str, rules: list[SequenceRule]) -> str:
    for rule in sequence_rules_by_suffix_length(rules):
        if not rule.suffix:
            continue

        value = re.sub(
            f"{re.escape(rule.suffix)}(\\d+)",
            lambda match: f"{rule.suffix}{match.group(1).zfill(rule.padding)}",
            value,
        )

    return value


def normalize_sequence_prefixes(value: str, rules: list[SequenceRule]) -> str:
    for rule in sequence_rules_by_prefix_length(rules):
        if not rule.prefix:
            continue

        value = re.sub(
            f"(?<![A-Za-z0-9]){re.escape(rule.prefix)}([_-]?)(\\d+)",
            lambda match: (
                f"{rule.prefix}{match.group(1)}"
                f"{match.group(2).zfill(rule.padding)}"
            ),
            value,
        )

    return value


def normalize_sequence_token(part: str, rules: list[SequenceRule]) -> str:
    match = SEQUENCE_TOKEN_PATTERN.fullmatch(part)
    if not match:
        return part

    token_prefix, digits = match.groups()
    padding = find_sequence_token_padding(token_prefix, rules)
    if padding is None:
        return part

    return token_prefix + digits.zfill(padding)


def find_sequence_token_padding(token_prefix: str, rules: list[SequenceRule]) -> int | None:
    for rule in rules:
        candidates = [
            rule.prefix,
            sequence_token_prefix_from_suffix(rule.suffix),
        ]

        if token_prefix in candidates:
            return rule.padding

    return None


def sequence_token_prefix_from_suffix(suffix: str) -> str:
    if not suffix:
        return ""

    return re.split(r"[^A-Za-z0-9]+", suffix)[-1]


def sequence_rules_by_suffix_length(rules: list[SequenceRule]) -> list[SequenceRule]:
    return sorted(rules, key=lambda rule: len(rule.suffix), reverse=True)


def sequence_rules_by_prefix_length(rules: list[SequenceRule]) -> list[SequenceRule]:
    return sorted(rules, key=lambda rule: len(rule.prefix), reverse=True)


def run_translation_jobs(jobs: list[TranslationJob], db_config: DatabaseConfig) -> None:
    translator = IdTranslator()
    connection = connect_database(db_config)

    try:
        with connection.cursor() as cursor:
            for job in jobs:
                run_translation_job(cursor, connection, job, translator, db_config.database)
    finally:
        connection.close()


def run_translation_job(
    cursor,
    connection,
    job: TranslationJob,
    translator: IdTranslator,
    database_name: str,
) -> None:
    validate_job(job)
    transform = job.transform or translate_plain_id

    print(f"\n=== {job.name} ===")
    if not table_exists(cursor, database_name, job.table_name):
        print(f"Skip: table {job.table_name} does not exist")
        return

    translator.sequence_rules = load_sequence_rules(cursor, database_name)
    ensure_original_column(cursor, connection, database_name, job)
    rows = fetch_rows(cursor, job)

    print(f"Found {len(rows)} rows")

    update_data = []
    for index, row in enumerate(rows, start=1):
        old_value = row[job.id_column]
        new_value = normalize_sequence_parts(
            transform(old_value, translator),
            translator.sequence_rules,
        )

        print(f"[{index}]")
        print("OLD:", old_value)
        print("NEW:", new_value)
        print("-" * 100)

        update_data.append((new_value, old_value, old_value))

    if not update_data:
        print("No rows to update")
        return

    update_rows(cursor, job, update_data)
    connection.commit()
    print("Update completed")


def ensure_original_column(cursor, connection, database_name: str, job: TranslationJob) -> None:
    check_column_sql = """
        SELECT COUNT(*) AS cnt
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = %s
          AND TABLE_NAME = %s
          AND COLUMN_NAME = %s
    """
    cursor.execute(
        check_column_sql,
        (database_name, job.table_name, job.original_column),
    )

    result = cursor.fetchone()
    if result["cnt"] > 0:
        print(f"Column {job.original_column} already exists")
        return

    print(f"Adding column {job.original_column} ...")
    cursor.execute(
        f"ALTER TABLE {job.table_name} ADD COLUMN {job.original_column} TEXT NULL"
    )
    connection.commit()
    print("Column added")


def table_exists(cursor, database_name: str, table_name: str) -> bool:
    cursor.execute(
        """
        SELECT COUNT(*) AS cnt
        FROM INFORMATION_SCHEMA.TABLES
        WHERE TABLE_SCHEMA = %s
          AND TABLE_NAME = %s
        """,
        (database_name, table_name),
    )
    result = cursor.fetchone()
    return result["cnt"] > 0


def load_sequence_rules(cursor, database_name: str) -> list[SequenceRule]:
    if not table_exists(cursor, database_name, "sequence_registry"):
        return []

    cursor.execute(
        """
        SELECT pattern, prefix, suffix, padding
        FROM sequence_registry
        WHERE padding IS NOT NULL
        """
    )

    rules = []
    for row in cursor.fetchall():
        rules.append(
            SequenceRule(
                pattern=str(row.get("pattern") or ""),
                prefix=str(row.get("prefix") or ""),
                suffix=str(row.get("suffix") or ""),
                padding=int(row.get("padding") or 0),
            )
        )

    return [rule for rule in rules if rule.padding > 0]


def fetch_rows(cursor, job: TranslationJob) -> list[dict]:
    sql_select = f"""
        SELECT {job.id_column}
        FROM {job.table_name}
        WHERE {job.id_column} REGEXP '[ก-๙]'
          AND {job.original_column} IS NULL
    """
    cursor.execute(sql_select)
    return cursor.fetchall()


def update_rows(cursor, job: TranslationJob, update_data: list[tuple[str, str, str]]) -> None:
    sql_update = f"""
        UPDATE {job.table_name}
        SET
            {job.id_column} = %s,
            {job.original_column} = %s
        WHERE {job.id_column} = %s
    """
    cursor.executemany(sql_update, update_data)


def validate_job(job: TranslationJob) -> None:
    identifiers = [job.table_name, job.id_column, job.original_column]

    for identifier in identifiers:
        if not SAFE_IDENTIFIER_PATTERN.fullmatch(identifier):
            raise ValueError(f"Unsafe SQL identifier: {identifier}")
