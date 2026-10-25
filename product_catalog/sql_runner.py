from pathlib import Path
import re


def execute_sql_file(cursor, path: Path) -> None:
    print(f"\n=== INSTALL {path.name} ===")

    for statement in split_sql_server_script(path.read_text()):
        cursor.execute(statement)

    print("Installed")


def split_sql_server_script(script: str) -> list[str]:
    """Split SQL Server batches.  GO is a client-side batch separator."""
    return [batch.strip() for batch in re.split(r"^\s*GO\s*$", script, flags=re.MULTILINE | re.IGNORECASE)
            if batch.strip() and not is_comment_only(batch)]


def flush_statement(buffer: list[str], statements: list[str]) -> None:
    statement = "\n".join(buffer).strip()
    buffer.clear()

    if not statement or is_comment_only(statement):
        return

    statements.append(statement)


def is_comment_only(statement: str) -> bool:
    lines = [line.strip() for line in statement.splitlines() if line.strip()]
    return bool(lines) and all(line.startswith("--") for line in lines)
