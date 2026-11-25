"""Opt-in Pilot coverage through Variant and PO characteristics."""
import csv
import re
from datetime import datetime
from collections import defaultdict
from pathlib import Path

from validation_domain import char_key, parse_pairs

PILOT_HEADERS = ('No.', 'Commercial Name', 'PRODUCTTYPE', 'BRAND', 'MODEL')
REPORT_HEADERS = ('No.', 'Product Offer', 'Variant ID', 'Product Offer Price', 'PRODUCTTYPE', 'BRAND', 'MODEL')
DIAGNOSTIC_HEADERS = ('No.', 'Pilot Record', 'Product Offer', 'Variant ID', 'Product Offer Price',
                      'ขั้นตอน', 'สถานะ', 'ค่าที่ต้องการ', 'ค่าที่พบ', 'หลักฐาน / เหตุผล')


def read_pilot(directory, on_source=None):
    candidates = []
    for path in Path(directory).glob('pilot_*.csv'):
        match = re.fullmatch(r'pilot_([0-9]{14})\.csv', path.name)
        if match:
            candidates.append((datetime.strptime(match.group(1), '%d%m%Y%H%M%S'), path))
    if not candidates:
        raise ValueError(f'No pilot_DDMMYYYYHHMMSS.csv in {directory}')
    path = max(candidates)[1].resolve()
    if on_source:
        on_source(path)
    with path.open(encoding='utf-8-sig', newline='') as stream:
        reader = csv.reader(stream, strict=True)
        header = next(reader, [])
        if any(header.count(name) != 1 for name in PILOT_HEADERS):
            raise ValueError('Pilot header missing or duplicated')
        indices = [header.index(name) for name in PILOT_HEADERS]
        rows = []
        for number, row in enumerate(reader, 2):
            if not row:
                continue
            if len(row) != len(header):
                raise ValueError(f'Invalid Pilot column count at record {number}')
            record = dict(zip(PILOT_HEADERS, (row[i] for i in indices)))
            record['_rn'] = number
            rows.append(record)
    return path, rows


def check_pilot(v, pilot_rows, source):
    if not v.has(17, 'v', 'cv'):
        return
    models = defaultdict(list)
    malformed = 0
    for variant in v.av:
        pairs, error = parse_pairs(variant['cids'], variant['vals'])
        if error:
            malformed += 1
            continue
        for cid, model in pairs:
            if char_key(cid) != 'model':
                continue
            key = char_key(model)
            for characteristic, value in pairs:
                if char_key(characteristic) == key:
                    models[value].append(variant)
    po_values = defaultdict(set)
    po_sources = defaultdict(list)
    for row in v.rows['cv']:
        po_values[row['po'], char_key(row['name'])].add(row['val'])
        if char_key(row['name']) in ('producttype', 'brand'):
            po_sources[row['po'], char_key(row['name'])].append(f"{row['src']} record {row['rn']}")
    v.coverage['17_pilot_rows'] = len(pilot_rows)
    v.coverage['17_passed_pilot_rows'] = 0
    v.coverage['17_malformed_variant_rows'] = malformed
    for number, pilot in enumerate(pilot_rows, 2):
        matches = set()
        diagnostics = []
        def record(step, status, expected, actual='', evidence='', po='', vid='', pid=''):
            diagnostics.append((pilot['No.'], pilot.get('_rn', number), po, vid, pid,
                                step, status, expected, actual, evidence))
        def blocked(steps, evidence, po='', vid=''):
            for step in steps:
                expected = pilot[step]
                record(step, 'ยังไม่ตรวจ', expected, evidence=evidence, po=po, vid=vid)
        if not models[pilot['MODEL']]:
            record('MODEL', 'ไม่พบค่าที่ตรง', pilot['MODEL'],
                   evidence=f'ไม่พบ MODEL ผ่านการอ้างอิง model ใน Variant; Variant ที่จับคู่ comma ไม่ได้ {malformed} แถว')
            blocked(('PRODUCTTYPE', 'BRAND'), 'ยังไม่พบ Variant ที่ MODEL ตรง')
        for variant in models[pilot['MODEL']]:
            po = variant['po']
            vid = variant['vid']
            record('MODEL', 'พบค่าที่ตรง', pilot['MODEL'], repr(pilot['MODEL']),
                   f"{variant['src']} record {variant['rn']}", po, vid)
            for label, key in (('PRODUCTTYPE', 'producttype'), ('BRAND', 'brand')):
                actual = po_values[po, key]
                record(label, 'พบค่าที่ตรง' if pilot[label] in actual else 'ไม่พบค่าที่ตรง',
                       pilot[label], ', '.join(repr(value) for value in sorted(actual)) if actual else '(ไม่มีข้อมูล)',
                       '; '.join(po_sources[po, key]) or 'ไม่พบ characteristic ใน Char_Value ของ PO นี้', po, vid)
            if (pilot['PRODUCTTYPE'] not in po_values[po, 'producttype']
                    or pilot['BRAND'] not in po_values[po, 'brand']):
                continue
            matches.add((pilot['No.'], po, vid, '', pilot['PRODUCTTYPE'], pilot['BRAND'], pilot['MODEL']))
        if matches:
            v.pilot_matches.extend(sorted(matches))
            v.coverage['17_passed_pilot_rows'] += 1
        else:
            v.pilot_diagnostics.extend(diagnostics)
            failed = sorted({row[5] for row in diagnostics if row[6] == 'ไม่พบค่าที่ตรง'})
            v.add(17, 'ERROR', 'PILOT_NOT_FOUND',
                  'ไม่พบเส้นทางที่ผ่านครบ; ขั้นที่ไม่ตรง: ' + ', '.join(failed) + '; ดูชีต Rule 17 Detail เพื่อเทียบค่าที่ต้องการกับค่าที่พบแยกตาม PO/Variant',
                  src=str(source), sheet='Pilot', rn=pilot.get('_rn', number),
                  val=pilot['MODEL'], name=pilot['Commercial Name'],
                  related=f"No.={pilot['No.']}; PRODUCTTYPE={pilot['PRODUCTTYPE']}; BRAND={pilot['BRAND']}; รายละเอียดทีละขั้นอยู่ใน Rule 17 Detail")


def export_pilot(v, path, rows_per_sheet):
    from openpyxl import Workbook, load_workbook
    from openpyxl.cell import WriteOnlyCell
    workbook = Workbook(write_only=True)
    sheet = None
    for index, values in enumerate(v.pilot_matches):
        if index % rows_per_sheet == 0:
            part = index // rows_per_sheet + 1
            sheet = workbook.create_sheet('Pilot' if part == 1 else f'Pilot {part}')
            sheet.freeze_panes = 'A2'
            sheet.append(REPORT_HEADERS)
        cells = []
        for value in values:
            if len(value) > 32767:
                raise ValueError('Pilot report cell exceeds Excel limit')
            cell = WriteOnlyCell(sheet, value)
            cell.data_type = 's'
            cells.append(cell)
        sheet.append(cells)
    if not v.pilot_matches:
        workbook.create_sheet('Pilot').append(REPORT_HEADERS)
    workbook.save(path)
    actual = load_workbook(path, read_only=True)
    try:
        index = 0
        for sheet in actual:
            rows = sheet.values
            if tuple(next(rows)) != REPORT_HEADERS:
                raise AssertionError('Pilot report header differs')
            for row in rows:
                if tuple('' if value is None else value for value in row) != v.pilot_matches[index]:
                    raise AssertionError('Pilot report row differs')
                index += 1
        if index != len(v.pilot_matches):
            raise AssertionError('Pilot report row count differs')
    finally:
        actual.close()
    return len(v.pilot_matches)
