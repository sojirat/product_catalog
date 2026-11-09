"""Read table-named CSV snapshots with the validator's existing SELECT queries."""
import csv
import logging
import re
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime
from pathlib import Path

LOG = logging.getLogger('po_pop')
DEFAULT_DIRECTORY = Path(__file__).resolve().parents[2] / 'Database'
_source = ContextVar('database_csv_source', default=None)


class Source:
    def __init__(self, directory=DEFAULT_DIRECTORY, force_csv=False):
        self.directory = Path(directory)
        self.force_csv = force_csv
        self.offline = False
        self.connection = None
        self.on_source = None

    def csv_connection(self):
        if self.connection is None:
            self.connection = CsvConnection(self.directory, self.on_source)
            self.connection.shared = current_source() is self
        return self.connection, 'dbo'


@contextmanager
def source_mode(directory=DEFAULT_DIRECTORY, force_csv=False):
    source = Source(directory, force_csv)
    token = _source.set(source)
    try:
        yield source
    finally:
        if source.connection is not None:
            source.connection.database.close()
        _source.reset(token)


def current_source():
    return _source.get()


def quote(name):
    return '"' + name.replace('"', '""') + '"'


def resolve_csv(directory, table):
    files = [p for p in directory.glob('*') if p.is_file() and p.suffix.lower() == '.csv']
    exact = [p for p in files if p.stem.casefold() == table.casefold()]
    if exact:
        candidates = exact
    else:
        pattern = re.compile(re.escape(table) + r'_(\d{12}|\d{14})', re.I)
        dated = []
        for path in files:
            match = pattern.fullmatch(path.stem)
            if not match:
                continue
            stamp = match.group(1)
            try:
                time = datetime.strptime(stamp if len(stamp) == 14 else stamp + '00', '%Y%m%d%H%M%S')
            except ValueError:
                continue
            dated.append((time, len(stamp), path))
        if not dated:
            raise FileNotFoundError(directory / (table + '.csv'))
        latest = max((time, precision) for time, precision, path in dated)
        candidates = [path for time, precision, path in dated if (time, precision) == latest]
    if len(candidates) != 1:
        raise ValueError(f'Ambiguous CSV table: {table}: {candidates}')
    return candidates[0].resolve()


class CsvConnection:
    def __init__(self, directory, on_source=None):
        import sqlite3
        self.database = sqlite3.connect(':memory:')
        self.database.row_factory = sqlite3.Row
        self.directory = directory
        self.on_source = on_source
        self.loaded = set()
        self.shared = False

    def close(self):
        # A run shares its snapshot; source_mode owns the actual connection.
        if not self.shared:
            self.database.close()

    def cursor(self):
        return CsvCursor(self)

    def load(self, table):
        if table.casefold() in self.loaded:
            return
        path = resolve_csv(self.directory, table)
        if self.on_source:
            self.on_source(path)
        with path.open(encoding='utf-8-sig', newline='') as stream:
            reader = csv.reader(stream, strict=True)
            columns = next(reader, [])
            if not columns or any(not name for name in columns) or len({c.casefold() for c in columns}) != len(columns):
                raise ValueError(f'{path}: missing or duplicate column headers')
            # Product IDs are audit tie-breakers in rule 13, and numeric in SQL Server.
            definitions = ', '.join(quote(c) + (' INTEGER' if table.upper() in ('PRODUCT_MST','PRICE_MST') and c.upper() == 'PRODUCT_ID' else ' TEXT') for c in columns)
            self.database.execute(f'CREATE TABLE {quote(table)} ({definitions})')
            insert = f'INSERT INTO {quote(table)} VALUES ({",".join("?" for _ in columns)})'
            batch = []
            for number, row in enumerate(reader, 2):
                if len(row) != len(columns):
                    raise ValueError(f'{path}: CSV record {number}: expected {len(columns)} columns, got {len(row)}')
                batch.append(tuple(None if value == r'\N' else value for value in row))
                if len(batch) == 10000:
                    self.database.executemany(insert, batch)
                    batch.clear()
            self.database.executemany(insert, batch)
        # Reference lookups repeat for thousands of SKUs. Index the actual
        # filter/join keys so each query does not scan an entire CSV snapshot.
        for number, column in enumerate(columns):
            if column.casefold() in ('mat_code', 'product_id', 'offer_id', 'specification_id'):
                self.database.execute(f'CREATE INDEX {quote(table + "_lookup_" + str(number))} '
                                      f'ON {quote(table)} ({quote(column)})')
        self.loaded.add(table.casefold())
        LOG.info('CSV database table: %s', path)


class CsvCursor:
    def __init__(self, connection):
        self.connection = connection
        self.reader = connection.database.cursor()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.reader.close()

    def execute(self, sql, parameters=()):
        # Only SELECT statements authored by database_source/csv_fallback are supported.
        if not sql.lstrip().upper().startswith('SELECT '):
            raise ValueError('CSV source supports SELECT only')
        pattern = r'\b(FROM|JOIN)\s+((?:\[(?:[^\]]|\]\])+\]\.)*\[((?:[^\]]|\]\])+)\])'
        def table_name(match):
            table = match.group(3).replace(']]', ']')
            self.connection.load(table)
            return match.group(1) + ' ' + quote(table)
        query = re.sub(pattern, table_name, sql, flags=re.I)
        top = re.match(r'SELECT\s+TOP\s*\(1\)\s+', query, flags=re.I)
        if top:
            query = 'SELECT ' + query[top.end():] + ' LIMIT 1'
        self.reader.execute(query, parameters)
        self.description = self.reader.description
        return self

    def fetchone(self):
        row = self.reader.fetchone()
        return None if row is None else dict(row)

    def fetchall(self):
        return [dict(row) for row in self.reader.fetchall()]
