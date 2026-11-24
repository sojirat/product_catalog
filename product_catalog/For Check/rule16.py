"""Compare complete IDs for trailing running numbers present in both snapshots."""
import csv
import re
from collections import defaultdict
from pathlib import Path

ID_FILES = (
    ('Master Characteristics', 'master_characteristics', 'Characteristics ID'),
    ('Product Offer', 'ProductOffer', 'Product Id'),
    ('Product Offer Category', 'productOfferCategory', 'Category ID'),
    ('Product Offer Price', 'productOfferPrice', 'Product Offer Price ID'),
    ('Product Specification', 'product_specification', 'Spec ID'),
    ('Resource Specification', 'resource_specification', 'Spec ID'),
)


def read_ids(root, folder, prefix, column, on_source=None):
    paths = sorted((Path(root) / folder).glob(prefix + '_*.csv'))
    if len(paths) != 1:
        raise ValueError(f'Expected one {Path(root) / folder / (prefix + "_*.csv")}; found {len(paths)}')
    path = paths[0].resolve()
    if on_source:
        on_source(path)
    result = []
    with path.open(encoding='utf-8-sig', newline='') as stream:
        reader = csv.reader(stream, strict=True)
        header = next(reader, [])
        if header.count(column) != 1:
            raise ValueError(f'{path}: missing or duplicate column {column}')
        index = header.index(column)
        for number, row in enumerate(reader, 2):
            if not row:
                continue
            if len(row) != len(header):
                raise ValueError(f'{path}: invalid column count at record {number}')
            result.append((row[index], number))
    return path, result


def check_unique_ids(validator, current_root, old_root, on_source=None):
    v = validator
    if current_root is None:
        v.add(16, 'REVIEW', 'ID_SNAPSHOT_UNAVAILABLE',
              'ข้อ 16 ต้องระบุรอบ export เพื่อเทียบ CSV ปัจจุบันกับ Old ID')
        return
    v.coverage['16_matched_rows'] = 0
    v.coverage['16_changed_rows'] = 0
    v.coverage['16_unmatched_rows'] = 0
    v.coverage['16_without_running_rows'] = 0
    for folder, prefix, column in ID_FILES:
        try:
            old_path, old_rows = read_ids(old_root, folder, prefix, column, on_source)
            current_path, current_rows = read_ids(current_root, folder, prefix, column, on_source)
        except (OSError, ValueError, csv.Error) as error:
            v.add(16, 'REVIEW', 'ID_SNAPSHOT_UNAVAILABLE',
                  'อ่าน CSV สำหรับตรวจ Unique ID ไม่สำเร็จ', sheet=folder, related=str(error))
            continue
        old = defaultdict(dict)
        for value, number in old_rows:
            match = re.search(r'([0-9]+)$', value)
            if match:
                old[match.group()][value] = number
        for value, number in current_rows:
            match = re.search(r'([0-9]+)$', value)
            if not match:
                v.coverage['16_without_running_rows'] += 1
                continue
            running = match.group()
            previous = old.get(running)
            if not previous:
                v.coverage['16_unmatched_rows'] += 1
                continue
            v.coverage['16_matched_rows'] += 1
            if set(previous) != {value}:
                v.coverage['16_changed_rows'] += 1
                v.add(16, 'ERROR', 'UNIQUE_ID_CHANGED',
                      'running number เดิมมี Unique ID เปลี่ยนแปลง',
                      src=str(current_path), sheet=folder, rn=number, name=column,
                      val=value, expected=', '.join(sorted(previous)),
                      related=f'running={running}; Old ID source: {old_path}; records: {sorted(previous.values())}')
        v.inputs.extend([
            {'source': str(old_path), 'sheet': folder, 'table': '16_old_' + prefix, 'records': len(old_rows)},
            {'source': str(current_path), 'sheet': folder, 'table': '16_current_' + prefix, 'records': len(current_rows)},
        ])
