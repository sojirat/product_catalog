"""Opt-in coverage of Pilot MAT_CODE rows against exported Variant SKUs."""
import csv
import re
from datetime import datetime
from pathlib import Path


def read_mat_codes(directory, on_source=None):
    paths = sorted(Path(directory).glob('mat_code_*.csv'))
    if not paths:
        raise ValueError(f'No mat_code_*.csv in {directory}')
    if len(paths) == 1:
        path = paths[0]
    else:
        candidates = []
        for path in paths:
            match = re.fullmatch(r'mat_code_([0-9]{14})\.csv', path.name)
            if not match:
                raise ValueError('Multiple mat_code files require DDMMYYYYHHMMSS timestamps')
            candidates.append((datetime.strptime(match.group(1), '%d%m%Y%H%M%S'), path))
        path = max(candidates)[1]
    path = path.resolve()
    if on_source:
        on_source(path)
    rows = []
    with path.open(encoding='utf-8-sig', newline='') as stream:
        reader = csv.reader(stream, strict=True)
        header = next(reader, [])
        if header.count('MAT_CODE') != 1:
            raise ValueError('MAT_CODE header missing or duplicated')
        index = header.index('MAT_CODE')
        for number, row in enumerate(reader, 2):
            if not row:
                continue
            if len(row) != len(header):
                raise ValueError(f'Invalid column count at record {number}')
            rows.append((row[index], number))
    return path, rows


def check_mat_codes(v, path, rows):
    if not v.has(18, 'v'):
        return
    skus = {row['sku'] for row in v.rows['v'] if row['po'] not in v.ex_po and row['sku'] != ''}
    found = 0
    for code, number in rows:
        if code != '' and code in skus:
            found += 1
            continue
        v.add(18, 'ERROR', 'PILOT_MAT_CODE_MISSING' if code else 'PILOT_MAT_CODE_EMPTY',
              'ไม่พบ MAT_CODE ใน Product Variants.sku' if code else 'MAT_CODE ในไฟล์ Pilot ว่าง',
              src=str(path), sheet='Pilot MAT_CODE', rn=number, sku=code,
              val=code, expected='พบ Product Variants.sku ที่ตรงกันอย่างน้อยหนึ่งแถว')
    v.coverage.update({'18_mat_code_rows': len(rows), '18_found_rows': found,
                       '18_missing_rows': len(rows)-found})
