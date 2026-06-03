import re
import csv
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from translation import connect_database, load_database_config, load_env


BASE_DIR = Path(__file__).resolve().parent
INVALID_SHEET_CHARS = re.compile(r"[\[\]:*?/\\]")
SAFE_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9_]+$")


def main() -> None:
    env_path = BASE_DIR / ".env"
    load_env(env_path)
    config = load_database_config(env_path)
    mapping_table = get_mapping_table_name()
    excel_file_filter = get_excel_file_filter()
    timestamp = datetime.now().strftime("%d%m%Y%H%M%S")
    output_dir = get_output_dir() / timestamp
    csv_dir = output_dir / "csv"
    xlsx_dir = output_dir / "xlsx"

    csv_dir.mkdir(parents=True, exist_ok=True)
    xlsx_dir.mkdir(parents=True, exist_ok=True)

    connection = connect_database(config)
    started_at = time.perf_counter()
    timings = []

    try:
        with connection.cursor() as cursor:
            mapping_rows = fetch_mapping_rows(cursor, mapping_table)
            mapping_rows = filter_mapping_rows_by_excel_file(
                mapping_rows,
                excel_file_filter,
            )
            if not mapping_rows:
                print("No mapping rows matched export filter")
                return

            datasets = measure(
                timings,
                "select_all_database_names",
                load_datasets,
                cursor,
                mapping_rows,
            )
            rows_by_raw_file = group_mapping_rows_by_raw_file(mapping_rows, timestamp)
            rows_by_excel_file = group_mapping_rows_by_excel_file(mapping_rows)

            measure(
                timings,
                "export_all_csv_files",
                export_csv_files,
                csv_dir,
                rows_by_raw_file,
                datasets,
            )

            for output_file, rows in rows_by_raw_file.items():
                measure(
                    timings,
                    f"export_xlsx_file:{output_file}",
                    export_workbook,
                    xlsx_dir / output_file,
                    rows,
                    datasets,
                    "Template File(Sheet Name)",
                )

            measure(
                timings,
                "export_all_combined_workbooks",
                export_combined_workbooks,
                output_dir,
                rows_by_excel_file,
                datasets,
                get_excel_template_dir(),
            )
    finally:
        connection.close()

    print(f"\nExport folder: {output_dir}")
    print_timing_summary(timings, started_at)


def get_mapping_table_name() -> str:
    import os

    table_name = os.getenv("TEMPLATE_MAPPING_TABLE", "template_mapping").strip()
    validate_identifier(table_name)
    return table_name


def get_output_dir() -> Path:
    import os

    path = Path(os.getenv("EXPORT_OUTPUT_DIR", "export")).expanduser()
    return path if path.is_absolute() else BASE_DIR.parent / path


def get_excel_template_dir() -> Path | None:
    import os

    value = os.getenv("EXCEL_TEMPLATE_DIR", "").strip()
    if not value:
        return None

    path = Path(value).expanduser()
    return path if path.is_absolute() else BASE_DIR.parent / path


def get_excel_file_filter() -> set[str]:
    import os

    value = os.getenv("EXPORT_EXCEL_FILES", "").strip()
    if not value:
        return set()

    return {
        build_excel_output_file_name(file_name.strip())
        for file_name in value.split("|")
        if file_name.strip()
    }


def fetch_mapping_rows(cursor, mapping_table: str) -> list[dict]:
    cursor.execute(f"SELECT * FROM {mapping_table}")

    mapping_rows = []
    for row in cursor.fetchall():
        database_name = text_value(row.get("DATABASE NAME"))
        if not database_name:
            continue

        validate_identifier(database_name)
        mapping_rows.append(row)

    return mapping_rows


def filter_mapping_rows_by_excel_file(
    mapping_rows: list[dict],
    excel_file_filter: set[str],
) -> list[dict]:
    if not excel_file_filter:
        return mapping_rows

    return [
        row
        for row in mapping_rows
        if build_excel_output_file_name(text_value(row.get("EXCEL File")))
        in excel_file_filter
    ]


def database_object_exists(cursor, database_name: str) -> bool:
    cursor.execute(
        """
        SELECT COUNT(*) AS cnt
        FROM INFORMATION_SCHEMA.TABLES
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = %s
        """,
        (database_name,),
    )
    result = cursor.fetchone()
    return result["cnt"] > 0


def group_mapping_rows_by_raw_file(
    mapping_rows: list[dict],
    timestamp: str,
) -> dict[str, list[dict]]:
    rows_by_file = defaultdict(list)

    for row in mapping_rows:
        output_file = build_output_file_name(text_value(row["Raw data Output File"]), timestamp)
        rows_by_file[output_file].append(row)

    return dict(rows_by_file)


def group_mapping_rows_by_excel_file(mapping_rows: list[dict]) -> dict[str, list[dict]]:
    rows_by_file = defaultdict(list)

    for row in mapping_rows:
        excel_file = build_excel_output_file_name(text_value(row["EXCEL File"]))
        if not excel_file:
            continue

        rows_by_file[excel_file].append(row)

    return {
        file_name: sorted(rows, key=sheet_sort_key)
        for file_name, rows in rows_by_file.items()
    }


def sheet_sort_key(row: dict) -> tuple[int, str]:
    try:
        sheet_no = int(str(row.get("SHEET NO", "")).strip())
    except ValueError:
        sheet_no = 999999

    return sheet_no, text_value(row.get("EXCEL SHEET NAME"))


def build_output_file_name(raw_output_file: str, timestamp: str) -> str:
    return build_base_output_name(raw_output_file, timestamp) + ".xlsx"


def build_csv_output_file_name(raw_output_file: str, timestamp: str) -> str:
    return build_base_output_name(raw_output_file, timestamp) + ".csv"


def build_excel_output_file_name(excel_file: str) -> str:
    file_name = sanitize_file_name(excel_file)
    if not file_name:
        return ""

    if not file_name.lower().endswith(".xlsx"):
        file_name += ".xlsx"

    return file_name


def build_base_output_name(raw_output_file: str, timestamp: str) -> str:
    file_name = raw_output_file.strip()
    file_name = file_name.replace("<ddmmyyyyhhmiss>", timestamp)

    if file_name.lower().endswith(".csv"):
        file_name = file_name[:-4]

    return sanitize_file_name(file_name)


def sanitize_file_name(file_name: str) -> str:
    return re.sub(r'[<>:"/\\|?*]+', "_", file_name).strip()


def load_datasets(cursor, mapping_rows: list[dict]) -> dict[str, tuple[list[str], list[dict]]]:
    datasets = {}
    database_names = sorted({text_value(row.get("DATABASE NAME")) for row in mapping_rows})

    for database_name in database_names:
        if not database_name:
            continue

        if not database_object_exists(cursor, database_name):
            print(f"Skip missing database object: {database_name}")
            continue

        started_at = time.perf_counter()
        cursor.execute(f"SELECT * FROM {database_name}")
        columns = [column[0] for column in cursor.description]
        rows = cursor.fetchall()
        datasets[database_name] = (columns, rows)
        print(
            f"Selected {database_name}: {len(rows)} rows in "
            f"{format_duration(time.perf_counter() - started_at)}"
        )

    return datasets


def export_workbook(
    output_path: Path,
    rows: list[dict],
    datasets: dict[str, tuple[list[str], list[dict]]],
    sheet_name_column: str,
) -> None:
    from openpyxl import Workbook

    started_at = time.perf_counter()
    workbook = Workbook(write_only=True)
    used_sheet_names = set()

    for row in rows:
        database_name = text_value(row["DATABASE NAME"])
        if database_name not in datasets:
            print(f"Skip missing dataset for {database_name} -> {output_path.name}")
            continue

        sheet_name = unique_sheet_name(
            clean_sheet_name(text_value(row[sheet_name_column])),
            used_sheet_names,
        )
        worksheet = workbook.create_sheet(title=sheet_name)

        print(f"\n=== EXPORT {database_name} -> {output_path.name} / {sheet_name} ===")
        write_dataset_to_worksheet(worksheet, datasets[database_name])

    if not workbook.sheetnames:
        print(f"Skip empty workbook: {output_path}")
        return

    workbook.save(output_path)
    print(f"Saved: {output_path} in {format_duration(time.perf_counter() - started_at)}")


def export_combined_workbooks(
    output_dir: Path,
    rows_by_excel_file: dict[str, list[dict]],
    datasets: dict[str, tuple[list[str], list[dict]]],
    template_dir: Path | None,
) -> None:
    from openpyxl import Workbook, load_workbook

    combined_started_at = time.perf_counter()

    for excel_file, rows in rows_by_excel_file.items():
        file_started_at = time.perf_counter()
        output_path = output_dir / excel_file
        template_path = find_template_path(template_dir, excel_file)
        workbook = load_workbook(template_path) if template_path else Workbook(write_only=True)
        used_sheet_names = set()

        print(f"\n=== EXPORT COMBINED {excel_file} ===")
        if template_path:
            print(f"Using template: {template_path}")

        for row in rows:
            database_name = text_value(row["DATABASE NAME"])
            if database_name not in datasets:
                print(f"Skip missing dataset for {database_name} -> {excel_file}")
                continue

            sheet_name = clean_sheet_name(text_value(row["EXCEL SHEET NAME"]))
            worksheet = get_or_create_worksheet(workbook, sheet_name, used_sheet_names)

            print(f"Sheet {row.get('SHEET NO', '')}: {database_name} -> {sheet_name}")
            if template_path:
                write_dataset_to_template_worksheet(worksheet, datasets[database_name])
            else:
                write_dataset_to_worksheet(worksheet, datasets[database_name])

        if not workbook.sheetnames:
            print(f"Skip empty combined workbook: {output_path}")
            continue

        workbook.save(output_path)
        print(f"Saved: {output_path} in {format_duration(time.perf_counter() - file_started_at)}")

    print(
        "Combined workbooks total: "
        f"{format_duration(time.perf_counter() - combined_started_at)}"
    )


def find_template_path(template_dir: Path | None, excel_file: str) -> Path | None:
    if not template_dir:
        return None

    path = template_dir / excel_file
    return path if path.exists() else None


def get_or_create_worksheet(workbook, sheet_name: str, used_sheet_names: set[str]):
    if sheet_name in workbook.sheetnames:
        used_sheet_names.add(sheet_name)
        return workbook[sheet_name]

    unique_name = unique_sheet_name(sheet_name, used_sheet_names)
    return workbook.create_sheet(title=unique_name)


def export_csv_files(
    csv_dir: Path,
    rows_by_file: dict[str, list[dict]],
    datasets: dict[str, tuple[list[str], list[dict]]],
) -> None:
    csv_started_at = time.perf_counter()

    for rows in rows_by_file.values():
        for row in rows:
            file_started_at = time.perf_counter()
            csv_file_name = build_csv_output_file_name(
                text_value(row["Raw data Output File"]),
                csv_dir.parent.name,
            )
            database_name = text_value(row["DATABASE NAME"])
            if database_name not in datasets:
                print(f"Skip missing dataset for {database_name} -> {csv_file_name}")
                continue

            output_path = csv_dir / csv_file_name

            print(f"\n=== EXPORT CSV {database_name} -> {csv_file_name} ===")
            write_dataset_to_csv(output_path, datasets[database_name])
            print(f"CSV file time: {format_duration(time.perf_counter() - file_started_at)}")

    print(f"CSV files total: {format_duration(time.perf_counter() - csv_started_at)}")


def write_dataset_to_csv(output_path: Path, dataset: tuple[list[str], list[dict]]) -> None:
    columns, rows = dataset

    row_count = 0
    with output_path.open("w", newline="", encoding="utf-8-sig") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(columns)

        for row in rows:
            writer.writerow([text_value(row[column]) for column in columns])
            row_count += 1

    print(f"Rows: {row_count}")
    print(f"Saved: {output_path}")


def clean_sheet_name(sheet_name: str) -> str:
    cleaned = INVALID_SHEET_CHARS.sub("_", sheet_name.strip())
    return (cleaned or "Sheet1")[:31]


def unique_sheet_name(sheet_name: str, used_sheet_names: set[str]) -> str:
    base_name = sheet_name[:31]
    candidate = base_name
    index = 2

    while candidate in used_sheet_names:
        suffix = f"_{index}"
        candidate = base_name[: 31 - len(suffix)] + suffix
        index += 1

    used_sheet_names.add(candidate)
    return candidate


def write_dataset_to_worksheet(worksheet, dataset: tuple[list[str], list[dict]]) -> None:
    from openpyxl.utils import get_column_letter

    columns, rows = dataset
    worksheet.append(columns)
    column_widths = [display_width(column) for column in columns]

    row_count = 0
    for row in rows:
        values = [excel_text_value(row[column]) for column in columns]
        worksheet.append(values)
        column_widths = [
            max(width, display_width(value))
            for width, value in zip(column_widths, values)
        ]
        row_count += 1

    for index, width in enumerate(column_widths, start=1):
        worksheet.column_dimensions[get_column_letter(index)].width = min(width + 2, 60)

    print(f"Rows: {row_count}")


def write_dataset_to_template_worksheet(worksheet, dataset: tuple[list[str], list[dict]]) -> None:
    data_start_row = infer_template_data_start_row(worksheet)
    clear_rows_from(worksheet, data_start_row)
    write_dataset_rows(worksheet, dataset, data_start_row, include_header=False)


def infer_template_data_start_row(worksheet) -> int:
    if not worksheet.merged_cells.ranges:
        return 2

    return max(cell_range.max_row for cell_range in worksheet.merged_cells.ranges) + 1


def clear_rows_from(worksheet, start_row: int) -> None:
    if worksheet.max_row >= start_row:
        worksheet.delete_rows(start_row, worksheet.max_row - start_row + 1)


def write_dataset_rows(
    worksheet,
    dataset: tuple[list[str], list[dict]],
    start_row: int,
    include_header: bool,
) -> None:
    columns, rows = dataset
    row_index = start_row

    if include_header:
        for column_index, column in enumerate(columns, start=1):
            worksheet.cell(row_index, column_index, column)
        row_index += 1

    row_count = 0
    for row in rows:
        for column_index, column in enumerate(columns, start=1):
            worksheet.cell(row_index, column_index, excel_text_value(row[column]))
        row_index += 1
        row_count += 1

    print(f"Rows: {row_count}")


def validate_identifier(identifier: str) -> None:
    if not SAFE_IDENTIFIER_PATTERN.fullmatch(identifier):
        raise ValueError(f"Unsafe database object name: {identifier}")


def text_value(value) -> str:
    return "" if value is None else str(value).strip()


def excel_text_value(value) -> str:
    return "" if value is None else str(value)


def display_width(value) -> int:
    if value is None:
        return 0

    text = str(value)
    return max(len(line) for line in text.splitlines()) if text else 0


def measure(timings: list[tuple[str, float]], name: str, func, *args, **kwargs):
    started_at = time.perf_counter()

    try:
        return func(*args, **kwargs)
    finally:
        elapsed = time.perf_counter() - started_at
        timings.append((name, elapsed))
        print(f"\n=== {name} finished in {format_duration(elapsed)} ===")


def print_timing_summary(timings: list[tuple[str, float]], started_at: float) -> None:
    total = time.perf_counter() - started_at

    print("\n=== EXPORT TIMING SUMMARY ===")
    for name, elapsed in timings:
        print(f"{name}: {format_duration(elapsed)}")

    print(f"TOTAL: {format_duration(total)}")


def format_duration(seconds: float) -> str:
    minutes, secs = divmod(seconds, 60)
    hours, minutes = divmod(int(minutes), 60)

    if hours:
        return f"{hours}h {minutes}m {secs:.3f}s"

    if minutes:
        return f"{minutes}m {secs:.3f}s"

    return f"{secs:.3f}s"


if __name__ == "__main__":
    main()
