import os
import re
import csv
import time
from copy import copy
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from translation import connect_database, load_database_config, load_env

from openpyxl import Workbook, load_workbook
from openpyxl.utils import get_column_letter


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
            mapping_rows = fetch_mapping_rows(
                cursor,
                mapping_table,
            )

            mapping_rows = filter_mapping_rows_by_excel_file(
                mapping_rows,
                excel_file_filter,
            )

            if not mapping_rows:
                print("No mapping rows matched export filter")
                return

            datasets = measure(
                timings,
                "load_datasets",
                load_datasets,
                cursor,
                mapping_rows,
            )

            rows_by_raw_file = group_mapping_rows_by_raw_file(
                mapping_rows,
                timestamp,
            )

            rows_by_excel_file = group_mapping_rows_by_excel_file(
                mapping_rows,
            )

            header_template_path = get_excel_header_template_path()
            header_template_workbook = (
                load_workbook(header_template_path)
                if header_template_path
                else None
            )

            #
            # EXPORT XLSX
            #
            for output_file, rows in rows_by_raw_file.items():
                measure(
                    timings,
                    f"export_xlsx:{output_file}",
                    export_workbook,
                    xlsx_dir / output_file,
                    rows,
                    datasets,
                    "Template File(Sheet Name)",
                    header_template_workbook,
                )

            #
            # CONVERT XLSX -> CSV
            #
            measure(
                timings,
                "convert_xlsx_to_csv",
                export_csv_files,
                csv_dir,
                xlsx_dir,
                rows_by_raw_file,
                datasets,
            )

            #
            # EXPORT COMBINED WORKBOOKS
            #
            measure(
                timings,
                "export_combined_workbooks",
                export_combined_workbooks,
                output_dir,
                rows_by_excel_file,
                datasets,
                get_excel_template_dir(),
            )

    finally:
        connection.close()

    print(f"\nExport folder: {output_dir}")

    print_timing_summary(
        timings,
        started_at,
    )


#
# CONFIG
#
def get_mapping_table_name() -> str:
    import os

    table_name = os.getenv(
        "TEMPLATE_MAPPING_TABLE",
        "template_mapping",
    ).strip()

    validate_identifier(table_name)

    return table_name
 
def get_output_dir() -> Path:
    import os

    path = Path(
        os.getenv("EXPORT_OUTPUT_DIR", "export")
    ).expanduser()

    return path if path.is_absolute() else BASE_DIR.parent / path


def get_excel_template_dir() -> Path | None:
    import os

    value = os.getenv(
        "EXCEL_TEMPLATE_DIR",
        "",
    ).strip()

    if not value:
        return None

    path = Path(value).expanduser()

    return path if path.is_absolute() else BASE_DIR.parent / path


def get_excel_header_template_path() -> Path | None:
    value = os.getenv(
        "EXCEL_HEADER_TEMPLATE_PATH",
        "",
    ).strip()

    if value:
        path = Path(value).expanduser()
        if not path.is_absolute():
            path = BASE_DIR.parent / path

        return path if path.exists() else None

    candidate = BASE_DIR.parent / "template" / "excel_header_template.xlsx"
    return candidate if candidate.exists() else None


def get_excel_file_filter() -> set[str]:
    import os

    value = os.getenv(
        "EXPORT_EXCEL_FILES",
        "",
    ).strip()

    if not value:
        return set()

    return {
        build_excel_output_file_name(file_name.strip())
        for file_name in value.split("|")
        if file_name.strip()
    }


#
# DATABASE
#
def fetch_mapping_rows(
    cursor,
    mapping_table: str,
) -> list[dict]:
    cursor.execute(f"SELECT * FROM {mapping_table}")

    mapping_rows = []

    for row in cursor.fetchall():
        database_name = text_value(
            row.get("DATABASE NAME")
        )

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
        if build_excel_output_file_name(
            text_value(row.get("EXCEL File"))
        ) in excel_file_filter
    ]


def database_object_exists(
    cursor,
    database_name: str,
) -> bool:
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


def load_datasets(
    cursor,
    mapping_rows: list[dict],
) -> dict[str, tuple[list[str], list[dict]]]:
    datasets = {}

    database_names = sorted({
        text_value(row.get("DATABASE NAME"))
        for row in mapping_rows
    })

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

        datasets[database_name] = (
            columns,
            rows,
        )

        print(
            f"Selected {database_name}: "
            f"{len(rows)} rows in "
            f"{format_duration(time.perf_counter() - started_at)}"
        )

    return datasets


#
# GROUPING
#
def group_mapping_rows_by_raw_file(
    mapping_rows: list[dict],
    timestamp: str,
) -> dict[str, list[dict]]:
    rows_by_file = defaultdict(list)

    for row in mapping_rows:
        output_file = build_output_file_name(
            text_value(row["Raw data Output File"]),
            timestamp,
        )

        rows_by_file[output_file].append(row)

    return dict(rows_by_file)


def group_mapping_rows_by_excel_file(
    mapping_rows: list[dict],
) -> dict[str, list[dict]]:
    rows_by_file = defaultdict(list)

    for row in mapping_rows:
        excel_file = build_excel_output_file_name(
            text_value(row["EXCEL File"])
        )

        if not excel_file:
            continue

        rows_by_file[excel_file].append(row)

    return {
        file_name: sorted(
            rows,
            key=sheet_sort_key,
        )
        for file_name, rows in rows_by_file.items()
    }


def sheet_sort_key(row: dict) -> tuple[int, str]:
    try:
        sheet_no = int(
            str(row.get("SHEET NO", "")).strip()
        )
    except ValueError:
        sheet_no = 999999

    return (
        sheet_no,
        text_value(row.get("EXCEL SHEET NAME")),
    )


#
# FILE NAME
#
def build_output_file_name(
    raw_output_file: str,
    timestamp: str,
) -> str:
    return (
        build_base_output_name(
            raw_output_file,
            timestamp,
        )
        + ".xlsx"
    )


def build_csv_output_file_name(
    raw_output_file: str,
    timestamp: str,
) -> str:
    return (
        build_base_output_name(
            raw_output_file,
            timestamp,
        )
        + ".csv"
    )


def build_excel_output_file_name(
    excel_file: str,
) -> str:
    file_name = sanitize_file_name(excel_file)

    if not file_name:
        return ""

    if not file_name.lower().endswith(".xlsx"):
        file_name += ".xlsx"

    return file_name


def build_base_output_name(
    raw_output_file: str,
    timestamp: str,
) -> str:
    file_name = raw_output_file.strip()

    file_name = file_name.replace(
        "<ddmmyyyyhhmiss>",
        timestamp,
    )

    if file_name.lower().endswith(".csv"):
        file_name = file_name[:-4]

    return sanitize_file_name(file_name)


def sanitize_file_name(file_name: str) -> str:
    return re.sub(
        r'[<>:"/\\|?*]+',
        "_",
        file_name,
    ).strip()


#
# EXPORT XLSX
#
def export_workbook(
    output_path: Path,
    rows: list[dict],
    datasets: dict[str, tuple[list[str], list[dict]]],
    sheet_name_column: str,
    header_template_workbook=None,
) -> None:
    started_at = time.perf_counter()

    workbook = Workbook()

    default_sheet = workbook.active
    workbook.remove(default_sheet)

    used_sheet_names = set()

    for row in rows:
        database_name = text_value(
            row["DATABASE NAME"]
        )

        if database_name not in datasets:
            print(
                f"Skip missing dataset "
                f"for {database_name}"
            )
            continue

        sheet_name = unique_sheet_name(
            clean_sheet_name(
                text_value(
                    row[sheet_name_column]
                )
            ),
            used_sheet_names,
        )

        worksheet = workbook.create_sheet(
            title=sheet_name
        )

        print(
            f"\n=== EXPORT "
            f"{database_name} -> "
            f"{output_path.name} / "
            f"{sheet_name} ==="
        )

        header_template_sheet_name = text_value(
            row.get("EXCEL HEADER TEMPLATE")
        )

        if header_template_workbook and header_template_sheet_name:
            write_dataset_to_template_worksheet(
                worksheet,
                datasets[database_name],
                header_template_workbook,
                header_template_sheet_name,
            )
        else:
            write_dataset_to_worksheet(
                worksheet,
                datasets[database_name],
            )

    if not workbook.sheetnames:
        print(f"Skip empty workbook: {output_path}")
        return

    workbook.save(output_path)

    print(
        f"Saved: {output_path} in "
        f"{format_duration(time.perf_counter() - started_at)}"
    )


def write_dataset_to_worksheet(
    worksheet,
    dataset: tuple[list[str], list[dict]],
) -> None:
    from openpyxl.styles import Alignment
    from openpyxl.utils import get_column_letter
    from wcwidth import wcswidth

    columns, rows = dataset

    wrap_alignment = Alignment(
        wrap_text=True,
        vertical="top",
    )

    column_widths = []

    #
    # HEADER
    #
    for column_index, column in enumerate(
        columns,
        start=1,
    ):
        cell = worksheet.cell(
            row=1,
            column=column_index,
        )

        cell.value = (
            "" if column is None
            else str(column)
        )

        cell.data_type = "s"
        cell.number_format = "@"
        cell.alignment = wrap_alignment

        width = max(
            wcswidth(str(column)),
            10,
        )

        column_widths.append(width)

    #
    # DATA
    #
    row_count = 0

    for row_index, row in enumerate(
        rows,
        start=2,
    ):
        max_lines = 1

        for column_index, column in enumerate(
            columns,
            start=1,
        ):
            value = excel_text_value(
                row[column]
            )

            cell = worksheet.cell(
                row=row_index,
                column=column_index,
            )

            text = (
                "" if value is None
                else str(value)
            )

            cell.value = text
            cell.data_type = "s"
            cell.number_format = "@"
            cell.alignment = wrap_alignment

            lines = text.splitlines() or [""]

            line_width = max(
                wcswidth(line)
                for line in lines
            )

            column_widths[column_index - 1] = max(
                column_widths[column_index - 1],
                min(line_width, 80),
            )

            max_lines = max(
                max_lines,
                len(lines),
            )

        worksheet.row_dimensions[row_index].height = (
            max_lines * 20
        )

        row_count += 1

    #
    # COLUMN WIDTH
    #
    for index, width in enumerate(
        column_widths,
        start=1,
    ):
        worksheet.column_dimensions[
            get_column_letter(index)
        ].width = min(width + 4, 100)

    print(f"Rows: {row_count}")

    # Finalize formatting: ensure all columns are text and auto-size
    force_text_and_autosize(worksheet, max_width=150)


#
# XLSX -> CSV
#
def export_csv_files(
    csv_dir: Path,
    xlsx_dir: Path,
    rows_by_file: dict[str, list[dict]],
    datasets: dict[str, tuple[list[str], list[dict]]],
) -> None:
    # Convert the raw xlsx exports from xlsx_dir into CSV.
    # Use MySQL dataset headers and rows whenever possible so CSV output
    # is not influenced by template header rows in the workbook.
    csv_started_at = time.perf_counter()

    processed_files = set()

    for xlsx_file_name, mapping_rows in rows_by_file.items():
        if xlsx_file_name in processed_files:
            continue

        processed_files.add(xlsx_file_name)

        started_at = time.perf_counter()

        xlsx_path = xlsx_dir / xlsx_file_name

        csv_file_name = (
            Path(xlsx_file_name).stem
            + ".csv"
        )

        csv_path = csv_dir / csv_file_name

        print(
            f"\n=== CONVERT "
            f"{xlsx_file_name} -> "
            f"{csv_file_name} ==="
        )

        if len(mapping_rows) == 1:
            database_name = text_value(
                mapping_rows[0]["DATABASE NAME"]
            )
            dataset = datasets.get(database_name)

            if dataset is not None:
                write_csv_from_dataset(
                    csv_path,
                    dataset,
                )
            else:
                convert_xlsx_to_csv(
                    xlsx_path,
                    csv_path,
                )
        else:
            # Fall back to workbook-based conversion for multi-sheet raw workbooks.
            convert_xlsx_to_csv(
                xlsx_path,
                csv_path,
            )

        print(
            f"CSV file time: "
            f"{format_duration(time.perf_counter() - started_at)}"
        )

    print(
        f"CSV files total: "
        f"{format_duration(time.perf_counter() - csv_started_at)}"
    )


def write_csv_from_dataset(
    csv_path: Path,
    dataset: tuple[list[str], list[dict]],
) -> None:
    columns, rows = dataset
    row_count = 0

    with csv_path.open(
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as csv_file:
        writer = csv.writer(csv_file)

        writer.writerow([
            "" if column is None else str(column)
            for column in columns
        ])

        row_count += 1

        for row in rows:
            writer.writerow([
                "" if row.get(column) is None else str(row.get(column))
                for column in columns
            ])
            row_count += 1

    print(f"Rows: {row_count}")
    print(f"Saved: {csv_path}")


def force_text_and_autosize(worksheet, max_width: int = 150) -> None:
    """Convert writable cells to text and auto-size columns (safe for merged cells).

    This intentionally does NOT delete any rows or modify merged ranges; it
    only sets `data_type` and `number_format` on non-merged placeholder cells
    and computes column widths based on visible text.
    """
    from openpyxl.utils import get_column_letter
    try:
        from wcwidth import wcswidth
    except Exception:
        def wcswidth(s):
            return len(s or "")

    # Compute widths and set text format where possible
    column_widths: dict[int, int] = {}

    try:
        from openpyxl.cell.cell import MergedCell
    except Exception:
        MergedCell = None

    for row in worksheet.iter_rows(min_row=1, max_row=worksheet.max_row):
        for cell in row:
            text = "" if cell.value is None else str(cell.value)
            col_index = cell.column
            width = max(1, wcswidth(text))
            prev = column_widths.get(col_index, 0)
            column_widths[col_index] = max(prev, min(width, max_width))

            if MergedCell is not None and isinstance(cell, MergedCell):
                continue

            try:
                cell.data_type = "s"
                cell.number_format = "@"
            except Exception:
                pass

    for col_index, width in column_widths.items():
        letter = get_column_letter(col_index)
        worksheet.column_dimensions[letter].width = min(width + 4, max_width)

    # if column_widths:
    #     print(f"Auto-sized {len(column_widths)} columns (max {max_width})")


def remove_first_row_for_template(worksheet) -> None:
    """Remove the first row by shifting rows 2..N up one row.

    This preserves merged ranges, styles and values by:
    - collecting merged ranges that include or are below row 2,
    - unmerging all ranges, copying cells from row r -> r-1 for r>=2,
    - deleting the final row, and re-applying adjusted merged ranges.
    """
    from openpyxl.utils import get_column_letter

    max_row = worksheet.max_row
    max_col = worksheet.max_column

    if max_row < 2:
        return

    # Collect merged ranges that should be shifted up
    shifted = []
    for mr in list(worksheet.merged_cells.ranges):
        # Only consider merges that touch row 2 or below (header template area)
        if mr.max_row >= 2:
            new_min_row = max(1, mr.min_row - 1)
            new_max_row = mr.max_row - 1
            shifted.append((mr.min_col, mr.max_col, new_min_row, new_max_row))

    # Unmerge all to make copying safe
    for mr in list(worksheet.merged_cells.ranges):
        try:
            worksheet.unmerge_cells(str(mr))
        except Exception:
            pass

    # Copy cells from row 2..max_row to row 1..max_row-1
    for r in range(2, max_row + 1):
        for c in range(1, max_col + 1):
            src = worksheet.cell(row=r, column=c)
            dst = worksheet.cell(row=r - 1, column=c)
            copy_cell(src, dst)

    # Delete the now-unused last row
    try:
        worksheet.delete_rows(max_row, 1)
    except Exception:
        pass

    # Re-apply shifted merges
    for min_col, max_col, min_row, max_row in shifted:
        # validate range
        if min_row <= max_row:
            try:
                worksheet.merge_cells(
                    f"{get_column_letter(min_col)}{min_row}:{get_column_letter(max_col)}{max_row}"
                )
            except Exception:
                pass

    print("Removed first row for template sheet (shifted content up)")


def finalize_worksheet_formatting(worksheet, start_row: int = 1, max_width: int = 150) -> None:
    """Apply final formatting to worksheet:
    - If row 1 is empty across all columns, delete it.
    - Set all cells to text format.
    - Auto-size columns based on visible values (max width cap).
    """
    from openpyxl.utils import get_column_letter
    try:
        from wcwidth import wcswidth
    except Exception:
        def wcswidth(s):
            return len(s or "")

    # If first row (row 1) is entirely empty, remove it.
    first_row_cells = next(worksheet.iter_rows(min_row=1, max_row=1), None)
    first_row_values = []
    if first_row_cells:
        for cell in first_row_cells:
            val = cell.value
            first_row_values.append(val)

    if first_row_values and all((v is None or str(v).strip() == "") for v in first_row_values):
        # delete first row (safe for merged cells/row dimensions)
        worksheet.delete_rows(1, 1)
        print("Removed empty first row")

    # Ensure all cells are text and compute column widths
    column_widths: dict[int, int] = {}
    for row in worksheet.iter_rows(min_row=1, max_row=worksheet.max_row):
        for cell in row:
            # Compute width from value first
            text = "" if cell.value is None else str(cell.value)
            col_index = cell.column
            width = max(1, wcswidth(text))
            prev = column_widths.get(col_index, 0)
            column_widths[col_index] = max(prev, min(width, max_width))

            # Skip applying writable properties to merged placeholder cells
            try:
                from openpyxl.cell.cell import MergedCell
            except Exception:
                MergedCell = None

            if MergedCell is not None and isinstance(cell, MergedCell):
                continue

            # Set as text (skip merged cell placeholders)
            try:
                cell.data_type = "s"
                cell.number_format = "@"
            except Exception:
                # some cell objects are read-only in certain cases
                pass

    # Apply column widths
    for col_index, width in column_widths.items():
        letter = get_column_letter(col_index)
        worksheet.column_dimensions[letter].width = min(width + 4, max_width)
    # if column_widths:
    #     print(f"Auto-sized {len(column_widths)} columns (max {max_width})")


def convert_xlsx_to_csv(
    xlsx_path: Path,
    csv_path: Path,
    sheet_name: str | None = None,
) -> None:
    workbook = load_workbook(
        xlsx_path,
        data_only=True,
    )

    worksheet = (
        workbook[sheet_name]
        if sheet_name
        else workbook.active
    )

    row_count = 0

    with csv_path.open(
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as csv_file:
        writer = csv.writer(csv_file)

        for row in worksheet.iter_rows(values_only=True):
            writer.writerow([
                ""
                if value is None
                else str(value)
                for value in row
            ])

            row_count += 1

    print(f"Rows: {row_count}")
    print(f"Saved: {csv_path}")


#
# COMBINED WORKBOOK
#
def export_combined_workbooks(
    output_dir: Path,
    rows_by_excel_file: dict[str, list[dict]],
    datasets: dict[str, tuple[list[str], list[dict]]],
    template_dir: Path | None,
) -> None:
    combined_started_at = time.perf_counter()

    header_template_path = get_excel_header_template_path()
    header_template_workbook = (
        load_workbook(header_template_path)
        if header_template_path
        else None
    )

    for excel_file, rows in rows_by_excel_file.items():
        file_started_at = time.perf_counter()

        output_path = output_dir / excel_file

        template_path = find_template_path(
            template_dir,
            excel_file,
        )

        if template_path:
            workbook = load_workbook(template_path)
        else:
            workbook = Workbook()

            if workbook.active:
                workbook.remove(workbook.active)

        used_sheet_names = set()

        print(f"\n=== EXPORT COMBINED {excel_file} ===")

        for row in rows:
            database_name = text_value(
                row["DATABASE NAME"]
            )

            if database_name not in datasets:
                continue

            sheet_name = clean_sheet_name(
                text_value(
                    row["EXCEL SHEET NAME"]
                )
            )

            worksheet = get_or_create_worksheet(
                workbook,
                sheet_name,
                used_sheet_names,
            )

            header_template_sheet_name = text_value(
                row.get("EXCEL HEADER TEMPLATE")
            )

            if header_template_workbook and header_template_sheet_name:
                write_dataset_to_template_worksheet(
                    worksheet,
                    datasets[database_name],
                    header_template_workbook,
                    header_template_sheet_name,
                )
            elif template_path:
                write_dataset_to_template_worksheet(
                    worksheet,
                    datasets[database_name],
                    None,
                    "",
                )
            else:
                write_dataset_to_worksheet(
                    worksheet,
                    datasets[database_name],
                )

        if not workbook.sheetnames:
            continue

        workbook.save(output_path)

        print(
            f"Saved: {output_path} in "
            f"{format_duration(time.perf_counter() - file_started_at)}"
        )

    print(
        "Combined workbooks total: "
        f"{format_duration(time.perf_counter() - combined_started_at)}"
    )


def find_template_path(
    template_dir: Path | None,
    excel_file: str,
) -> Path | None:
    if not template_dir:
        return None

    path = template_dir / excel_file

    return path if path.exists() else None


def get_or_create_worksheet(
    workbook,
    sheet_name: str,
    used_sheet_names: set[str],
):
    if sheet_name in workbook.sheetnames:
        used_sheet_names.add(sheet_name)
        return workbook[sheet_name]

    unique_name = unique_sheet_name(
        sheet_name,
        used_sheet_names,
    )

    return workbook.create_sheet(
        title=unique_name
    )


#
# TEMPLATE
#
def write_dataset_to_template_worksheet(
    worksheet,
    dataset: tuple[list[str], list[dict]],
    header_template_workbook,
    header_template_sheet_name: str,
) -> None:
    data_start_row = infer_template_data_start_row(
        worksheet
    )

    if (
        header_template_workbook
        and header_template_sheet_name
    ):
        data_start_row = copy_header_rows_from_excel_header_template(
            worksheet,
            header_template_workbook,
            header_template_sheet_name,
            dataset[0],
        )

    clear_rows_from(
        worksheet,
        data_start_row,
    )

    write_dataset_rows(
        worksheet,
        dataset,
        data_start_row,
        include_header=False,
    )

    # Ensure all cells are text and autosized (safe operation)
    force_text_and_autosize(worksheet, max_width=150)

    # For template-based exports, remove the first (helper) row used
    # for matching column names so the final sheet starts with the
    # template header rows (which begin at row 2).
    remove_first_row_for_template(worksheet)


def copy_header_rows_from_excel_header_template(
    worksheet,
    header_template_workbook,
    header_template_sheet_name: str,
    target_columns: list[str],
) -> int:
    if header_template_sheet_name not in header_template_workbook.sheetnames:
        print(
            f"Skip missing header template sheet: "
            f"{header_template_sheet_name}"
        )
        return infer_template_data_start_row(worksheet)

    source_ws = header_template_workbook[
        header_template_sheet_name
    ]

    source_header_end = 1
    for row_index in range(2, source_ws.max_row + 1):
        row_has_value = any(
            cell.value is not None
            for cell in source_ws[row_index]
        )

        if row_has_value:
            source_header_end = row_index
            continue

        if source_header_end > 1:
            break

    if source_header_end <= 1:
        return 2

    column_map = build_header_column_map(
        source_ws,
        target_columns,
    )

    if not column_map:
        return 2

    clear_rows_from(
        worksheet,
        2,
    )
    clear_merged_cells_in_range(
        worksheet,
        2,
        source_header_end,
    )

    for source_row in range(2, source_header_end + 1):
        row_dim = source_ws.row_dimensions.get(source_row)
        if row_dim is not None and row_dim.height is not None:
            worksheet.row_dimensions[source_row].height = (
                row_dim.height
            )

        for source_col, target_col in column_map.items():
            source_cell = source_ws.cell(
                row=source_row,
                column=source_col,
            )
            target_cell = worksheet.cell(
                row=source_row,
                column=target_col,
            )

            copy_cell(source_cell, target_cell)

    copy_header_merge_ranges(
        source_ws,
        worksheet,
        source_header_end,
        column_map,
    )
    copy_column_dimensions(
        source_ws,
        worksheet,
        column_map,
    )

    return source_header_end + 1


def build_header_column_map(
    header_ws,
    target_columns: list[str],
) -> dict[int, int]:
    normalized_targets: dict[str, list[int]] = {}

    for index, column in enumerate(target_columns, start=1):
        normalized = normalize_header_key(column)
        if not normalized:
            continue

        normalized_targets.setdefault(
            normalized,
            [],
        ).append(index)

    column_map: dict[int, int] = {}
    used_targets: set[int] = set()

    for source_col in range(1, header_ws.max_column + 1):
        normalized = normalize_header_key(
            header_ws.cell(
                row=1,
                column=source_col,
            ).value
        )

        if not normalized:
            continue

        candidates = normalized_targets.get(normalized)
        if not candidates:
            continue

        target_index = next(
            (
                candidate
                for candidate in candidates
                if candidate not in used_targets
            ),
            None,
        )

        if target_index is None:
            target_index = candidates[0]

        column_map[source_col] = target_index
        used_targets.add(target_index)

    return column_map


def normalize_header_key(value) -> str:
    return (
        ""
        if value is None
        else str(value).strip().lower()
    )


def copy_cell(source_cell, target_cell) -> None:
    target_cell.value = source_cell.value
    target_cell.data_type = source_cell.data_type
    target_cell.number_format = source_cell.number_format
    target_cell.font = copy(source_cell.font)
    target_cell.border = copy(source_cell.border)
    target_cell.fill = copy(source_cell.fill)
    target_cell.alignment = copy(source_cell.alignment)
    target_cell.protection = copy(source_cell.protection)

    if source_cell.comment:
        target_cell.comment = copy(source_cell.comment)

    if source_cell.hyperlink:
        target_cell.hyperlink = source_cell.hyperlink


def clear_merged_cells_in_range(
    worksheet,
    start_row: int,
    end_row: int,
) -> None:
    for merged_range in list(worksheet.merged_cells.ranges):
        if (
            merged_range.min_row <= end_row
            and merged_range.max_row >= start_row
        ):
            worksheet.unmerge_cells(
                str(merged_range)
            )


def copy_header_merge_ranges(
    source_ws,
    target_ws,
    source_header_end: int,
    column_map: dict[int, int],
) -> None:
    for merged_range in source_ws.merged_cells.ranges:
        if (
            merged_range.min_row < 2
            or merged_range.max_row > source_header_end
        ):
            continue

        source_columns = list(
            range(
                merged_range.min_col,
                merged_range.max_col + 1,
            )
        )
        mapped_columns = [
            column_map.get(col)
            for col in source_columns
        ]

        if any(col is None for col in mapped_columns):
            continue

        mapped_columns = sorted(set(mapped_columns))
        if (
            mapped_columns
            != list(range(
                min(mapped_columns),
                max(mapped_columns) + 1,
            ))
        ):
            continue

        target_range = (
            f"{get_column_letter(min(mapped_columns))}"
            f"{merged_range.min_row}:"
            f"{get_column_letter(max(mapped_columns))}"
            f"{merged_range.max_row}"
        )

        target_ws.merge_cells(target_range)


def copy_column_dimensions(
    source_ws,
    target_ws,
    column_map: dict[int, int],
) -> None:
    for source_col, target_col in column_map.items():
        source_letter = get_column_letter(source_col)
        target_letter = get_column_letter(target_col)
        source_dim = source_ws.column_dimensions.get(
            source_letter
        )

        if (
            source_dim is None
            or source_dim.width is None
        ):
            continue

        target_ws.column_dimensions[
            target_letter
        ].width = source_dim.width


def infer_template_data_start_row(
    worksheet,
) -> int:
    if not worksheet.merged_cells.ranges:
        return 2

    return (
        max(
            cell_range.max_row
            for cell_range
            in worksheet.merged_cells.ranges
        )
        + 1
    )


def clear_rows_from(
    worksheet,
    start_row: int,
) -> None:
    if worksheet.max_row >= start_row:
        worksheet.delete_rows(
            start_row,
            worksheet.max_row - start_row + 1,
        )


def write_dataset_rows(
    worksheet,
    dataset: tuple[list[str], list[dict]],
    start_row: int,
    include_header: bool,
) -> None:
    columns, rows = dataset

    row_index = start_row

    if include_header:
        for column_index, column in enumerate(
            columns,
            start=1,
        ):
            worksheet.cell(
                row_index,
                column_index,
                column,
            )

        row_index += 1

    row_count = 0

    for row in rows:
        for column_index, column in enumerate(
            columns,
            start=1,
        ):
            worksheet.cell(
                row_index,
                column_index,
                excel_text_value(row[column]),
            )

        row_index += 1
        row_count += 1

    print(f"Rows: {row_count}")


#
# UTILS
#
def clean_sheet_name(sheet_name: str) -> str:
    cleaned = INVALID_SHEET_CHARS.sub(
        "_",
        sheet_name.strip(),
    )

    return (cleaned or "Sheet1")[:31]


def unique_sheet_name(
    sheet_name: str,
    used_sheet_names: set[str],
) -> str:
    base_name = sheet_name[:31]

    candidate = base_name
    index = 2

    while candidate in used_sheet_names:
        suffix = f"_{index}"

        candidate = (
            base_name[: 31 - len(suffix)]
            + suffix
        )

        index += 1

    used_sheet_names.add(candidate)

    return candidate


def validate_identifier(
    identifier: str,
) -> None:
    if not SAFE_IDENTIFIER_PATTERN.fullmatch(
        identifier
    ):
        raise ValueError(
            f"Unsafe database object name: {identifier}"
        )


def text_value(value) -> str:
    return (
        ""
        if value is None
        else str(value).strip()
    )


def excel_text_value(value) -> str:
    return (
        ""
        if value is None
        else str(value)
    )


def measure(
    timings: list[tuple[str, float]],
    name: str,
    func,
    *args,
    **kwargs,
):
    started_at = time.perf_counter()

    try:
        return func(*args, **kwargs)

    finally:
        elapsed = time.perf_counter() - started_at

        timings.append((name, elapsed))

        print(
            f"\n=== {name} finished in "
            f"{format_duration(elapsed)} ==="
        )


def print_timing_summary(
    timings: list[tuple[str, float]],
    started_at: float,
) -> None:
    total = time.perf_counter() - started_at

    print("\n=== EXPORT TIMING SUMMARY ===")

    for name, elapsed in timings:
        print(
            f"{name}: "
            f"{format_duration(elapsed)}"
        )

    print(f"TOTAL: {format_duration(total)}")


def format_duration(seconds: float) -> str:
    minutes, secs = divmod(seconds, 60)

    hours, minutes = divmod(
        int(minutes),
        60,
    )

    if hours:
        return f"{hours}h {minutes}m {secs:.3f}s"

    if minutes:
        return f"{minutes}m {secs:.3f}s"

    return f"{secs:.3f}s"


if __name__ == "__main__":
    main()