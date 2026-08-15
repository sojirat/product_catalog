"""
DB diagnostic helper for the product_catalog project.
Run locally to collect `SHOW PROCESSLIST`, InnoDB transaction/lock info, and row counts.
Usage:
    python product_catalog/db_check.py [--env /path/to/.env] [--processlist-limit N]
"""
import argparse
import json
from pathlib import Path

from product_catalog.translation import load_database_config, connect_database
from product_catalog.export_template_mapping import BASE_DIR

DEFAULT_QUERIES = [
    ("SHOW FULL PROCESSLIST", None),
    ("SELECT * FROM information_schema.PROCESSLIST ORDER BY TIME DESC LIMIT %(limit)s", {'limit': 50}),
    ("SELECT trx_id, trx_mysql_thread_id, trx_started, trx_state, trx_query FROM information_schema.INNODB_TRX", None),
    ("SELECT * FROM information_schema.INNODB_LOCKS", None),
    ("SELECT * FROM information_schema.INNODB_LOCK_WAITS", None),
    ("SELECT COUNT(*) AS c FROM tbl_product_offering", None),
    ("SELECT COUNT(*) AS c FROM tbl_product_offering_variant", None),
    ("SELECT COUNT(*) AS c FROM tbl_product_offering_char_value", None),
    ("SELECT * FROM ingest_batch ORDER BY batch_id DESC LIMIT 5", None),
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
    parser.add_argument('--processlist-limit', type=int, default=50, help='Limit for information_schema.PROCESSLIST')
    args = parser.parse_args()

    config = load_database_config(args.env)
    print('Using DB:', config.database, 'host=', config.host)

    conn = connect_database(config)
    try:
        with conn.cursor() as cursor:
            print('\n--- SHOW FULL PROCESSLIST ---')
            cursor.execute('SHOW FULL PROCESSLIST')
            for row in cursor.fetchall():
                print(row)

            print('\n--- TOP PROCESSLIST (time desc) ---')
            cursor.execute('SELECT * FROM information_schema.PROCESSLIST ORDER BY TIME DESC LIMIT %s', (args.processlist_limit,))
            for row in cursor.fetchall():
                print(row)

            print('\n--- INNODB TRX (first 20) ---')
            try:
                cursor.execute('SELECT trx_id, trx_mysql_thread_id, trx_started, trx_state, trx_query FROM information_schema.INNODB_TRX LIMIT 20')
                trx = cursor.fetchall()
                for row in trx:
                    print(row)
            except Exception as e:
                print('INNODB_TRX not available or error:', e)

            print('\n--- INNODB LOCKS (first 50) ---')
            try:
                cursor.execute('SELECT * FROM information_schema.INNODB_LOCKS LIMIT 50')
                for row in cursor.fetchall():
                    print(row)
            except Exception as e:
                print('INNODB_LOCKS not available or error:', e)

            print('\n--- INNODB LOCK WAITS (first 50) ---')
            try:
                cursor.execute('SELECT * FROM information_schema.INNODB_LOCK_WAITS LIMIT 50')
                for row in cursor.fetchall():
                    print(row)
            except Exception as e:
                print('INNODB_LOCK_WAITS not available or error:', e)

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
                cursor.execute('SELECT * FROM ingest_batch ORDER BY batch_id DESC LIMIT 5')
                for row in cursor.fetchall():
                    print(row)
            except Exception as e:
                print('ingest_batch query error:', e)

    finally:
        conn.close()


if __name__ == '__main__':
    main()
