from pathlib import Path


def execute_sql_file(cursor, path: Path) -> None:
    print(f"\n=== INSTALL {path.name} ===")

    for statement in split_mysql_script(path.read_text()):
        cursor.execute(statement)

    print("Installed")


def split_mysql_script(script: str) -> list[str]:
    delimiter = ";"
    buffer: list[str] = []
    statements: list[str] = []

    for raw_line in script.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()

        if stripped.upper().startswith("DELIMITER "):
            flush_statement(buffer, statements)
            delimiter = stripped.split(None, 1)[1]
            continue

        if stripped.endswith(delimiter):
            statement_line = line[: -len(delimiter)]
            buffer.append(statement_line)
            flush_statement(buffer, statements)
            continue

        buffer.append(line)

    flush_statement(buffer, statements)
    return statements


def flush_statement(buffer: list[str], statements: list[str]) -> None:
    statement = "\n".join(buffer).strip()
    buffer.clear()

    if not statement or is_comment_only(statement):
        return

    statements.append(statement)


def is_comment_only(statement: str) -> bool:
    lines = [line.strip() for line in statement.splitlines() if line.strip()]
    return bool(lines) and all(line.startswith("--") for line in lines)
