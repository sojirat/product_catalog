"""
DB diagnostic helper for the product_catalog project.
Run locally to collect SQL Server request/lock information and row counts.
Usage:
    python product_catalog/db_check.py [--env /path/to/.env] [--processlist-limit N]
"""
import argparse
import json
from pathlib import Path

from product_catalog.translation import load_database_config, connect_database
from product_catalog.export_template_mapping import BASE_DIR

DEFAULT_QUERIES = [
    ("SELECT session_id, status, login_name, host_name, program_name FROM sys.dm_exec_sessions", None),
    ("SELECT TOP 50 * FROM sys.dm_exec_requests ORDER BY start_time DESC", None),
    ("SELECT TOP 50 * FROM sys.dm_tran_locks", None),
    ("SELECT COUNT(*) AS c FROM tbl_product_offering", None),
    ("SELECT COUNT(*) AS c FROM tbl_product_offering_variant", None),
    ("SELECT COUNT(*) AS c FROM tbl_product_offering_char_value", None),
    ("SELECT TOP 5 * FROM dbo.ingest_batch ORDER BY batch_id DESC", None),
]


def run_query(cursor, sql, params=None):
    cursor.execute(sql, params or ())
    try:
        rows = cursor.fetchall()
    except Exception:
        rows = None
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--env', type=Path, default=BASE_DIR / '.env', help='Path to .env file')
    parser.add_argument('--processlist-limit', type=int, default=50, help='Limit for SQL Server request output')
    args = parser.parse_args()

    config = load_database_config(args.env)
    print('Using DB:', config.database, 'host=', config.host)

    conn = connect_database(config)
    try:
        with conn.cursor() as cursor:
            print('\n--- SESSIONS ---')
            cursor.execute('SELECT session_id, status, login_name, host_name, program_name FROM sys.dm_exec_sessions')
            for row in cursor.fetchall():
                print(row)

            print('\n--- TOP REQUESTS (start time desc) ---')
            cursor.execute('SELECT TOP (?) * FROM sys.dm_exec_requests ORDER BY start_time DESC', (args.processlist_limit,))
            for row in cursor.fetchall():
                print(row)

            print('\n--- ACTIVE TRANSACTIONS (first 20) ---')
            try:
                cursor.execute('SELECT TOP 20 * FROM sys.dm_tran_active_transactions')
                trx = cursor.fetchall()
                for row in trx:
                    print(row)
            except Exception as e:
                print('Transaction DMV not available or error:', e)

            print('\n--- LOCKS (first 50) ---')
            try:
                cursor.execute('SELECT TOP 50 * FROM sys.dm_tran_locks')
                for row in cursor.fetchall():
                    print(row)
            except Exception as e:
                print('Lock DMV not available or error:', e)

            print('\n--- BLOCKED REQUESTS (first 50) ---')
            try:
                cursor.execute('SELECT TOP 50 * FROM sys.dm_exec_requests WHERE blocking_session_id <> 0')
                for row in cursor.fetchall():
                    print(row)
            except Exception as e:
                print('Blocked-request DMV not available or error:', e)

            print('\n--- COUNTS ---')
            for sql, params in [
                ('SELECT COUNT(*) AS c FROM tbl_product_offering', None),
                ('SELECT COUNT(*) AS c FROM tbl_product_offering_variant', None),
                ('SELECT COUNT(*) AS c FROM tbl_product_offering_char_value', None),
            ]:
                try:
                    cursor.execute(sql)
                    row = cursor.fetchone()
                    print(sql, row)
                except Exception as e:
                    print(sql, 'ERROR:', e)

            print('\n--- LATEST ingest_batch ---')
            try:
                cursor.execute('SELECT TOP 5 * FROM dbo.ingest_batch ORDER BY batch_id DESC')
                for row in cursor.fetchall():
                    print(row)
            except Exception as e:
                print('ingest_batch query error:', e)

    finally:
        conn.close()


if __name__ == '__main__':
    main()
