"""Exact PO/POP rules over source rows, with no local database."""
from collections import Counter, defaultdict

from validation_domain import SCHEMAS, UNIT, MODEL, MAIN, TYPE, VERSION, parse_pairs


def group(rows, *fields):
    result = defaultdict(list)
    for row in rows:
        key = tuple(row[field] for field in fields)
        result[key[0] if len(key) == 1 else key].append(row)
    return result


class RuleValidator:
    def __init__(self, config):
        self.config = config
        self.rows = {table: [] for table in SCHEMAS}
        self.ready = set()
        self.coverage = {}
        self.inputs = []
        self.issues = []
        self.ex_po = set(config['exclude_po_ids'])
        self.ex_pop = set(config['exclude_pop_ids'])

    def _insert(self, table, batch):
        fields = ['src', 'sheet', 'rn', *SCHEMAS[table][2]]
        for values in batch:
            row = dict(zip(fields, values, strict=True))
            row['id'] = len(self.rows[table]) + 1
            self.rows[table].append(row)

    def add(self, rule, severity, code, reason, **values):
        issue = dict.fromkeys(('src', 'sheet', 'po', 'pid', 'vid', 'sku', 'cid',
                               'name', 'val', 'expected', 'related'), '')
        issue.update(id=len(self.issues) + 1, rule=str(rule), severity=severity,
                     code=code, reason=reason, rn=None, occurrences=1)
        issue.update(values)
        self.issues.append(issue)

    def finding(self, rule, code, row=None, severity='ERROR', reason=None, **values):
        evidence = {key: row[key] for key in ('src', 'sheet', 'rn', 'po', 'pid',
                    'vid', 'sku', 'cid', 'name', 'val') if row and key in row}
        evidence.update(values)
        self.add(rule, severity, code, reason or REASONS[code], **evidence)

    def has(self, rule, *tables):
        missing = sorted(set(tables) - self.ready)
        if missing:
            self.add(rule, 'REVIEW', 'MISSING_INPUT', 'ขาดหรืออ่านข้อมูลไม่สำเร็จ: ' + ', '.join(missing))
        return not missing

    def input_error(self, table, message, **values):
        self.add('INPUT', 'REVIEW', 'INPUT_UNCERTAIN', table + ': ' + message, **values)

    def indexes(self):
        self.am = [r for r in self.rows['m'] if r['pid'] not in self.ex_pop]
        self.av = [r for r in self.rows['v'] if r['po'] not in self.ex_po]
        self.ac = [r for r in self.rows['c'] if r['pid'] not in self.ex_pop]
        self.at = [r for r in self.rows['t'] if r['pid'] not in self.ex_pop]
        self.owners = group(self.rows['o'], 'pid')
        self.owner_po = {pid: {r['po'] for r in rows} for pid, rows in self.owners.items()}
        self.chars = group(self.rows['c'], 'pid')
        self.chars_by_id = group(self.rows['c'], 'pid', 'cid')
        self.chars_by_name = group(self.rows['c'], 'pid', 'name')
        self.cv = group(self.rows['cv'], 'po')
        self.allowed_pairs = {(r['po'], r['cid'], r['val']) for r in self.rows['cv'] if r['val'] != ''}
        self.exact_cv = {(r['po'], r['cid'], r['name'], r['val']) for r in self.rows['cv']}
        self.links_by_vid = group(self.rows['l'], 'vid')
        self.links_by_pid = group(self.rows['l'], 'pid')
        self.variants_by_vid = group(self.rows['v'], 'vid')
        self.active_by_sku = group(self.av, 'sku')
        self.meta_by_pid = group(self.rows['t'], 'pid')
        self.meta_by_sku = group(self.rows['t'], 'sku')

    def single_owner(self, pid):
        owners = self.owner_po.get(pid, set())
        return next(iter(owners)) if len(owners) == 1 else None

    def run(self):
        self.indexes()
        for number in range(1, 10):
            getattr(self, f'rule{number}')()

    def rule1(self):
        if self.has(1, 'm', 't'):
            for row in self.am:
                if not self.meta_by_pid[row['pid']]:
                    self.finding(1, 'MISSING_META', row)

    def rule2(self):
        if not self.has(2, 'v', 'l', 't'):
            return
        excluded = 0
        for row in self.av:
            links = self.links_by_vid[row['vid']]
            if links and all(link['pid'] in self.ex_pop for link in links):
                excluded += 1
                continue
            meta = self.meta_by_sku[row['sku']]
            if not meta:
                self.finding(2, 'SKU_NOT_FOUND', row)
            elif not links:
                self.finding(2, 'VARIANT_LINK_MISSING', row)
            elif not any(link['pid'] not in self.ex_pop and link['pid'] in
                         {m['pid'] for m in meta} for link in links):
                self.finding(2, 'POP_MISMATCH', row, expected='อย่างน้อย 1 POP ตรงกัน')
        self.coverage['2_excluded_only_links'] = excluded

    def rule3(self):
        if not self.has(3, 't', 'l', 'v'):
            return
        for row in self.at:
            links = self.links_by_pid[row['pid']]
            if not links:
                self.finding(3, 'POP_LINK_MISSING', row)
            for vid in sorted({link['vid'] for link in links}):
                if not self.variants_by_vid[vid]:
                    self.finding(3, 'VARIANT_MISSING', row, vid=vid)
            vids = {link['vid'] for link in links}
            count = sum(v['vid'] in vids for v in self.active_by_sku[row['sku']])
            if links and count != 1:
                self.finding(3, 'SKU_MATCH_COUNT', row, val=str(count), expected='1 แถวต้นฉบับ')

    def rule4(self):
        if self.has(4, 'c'):
            for row in self.ac:
                count = len(self.chars_by_name[row['pid'], row['name']])
                if count > 1:
                    self.finding(4, 'DUPLICATE_CHAR_NAME', row, related=f'จำนวนแถวในกลุ่ม: {count}')

    def rule5(self):
        if not self.has(5, 'm', 'c'):
            return
        masters = {r['pid'] for r in self.am}
        for row in self.am:
            if not self.chars_by_id[row['pid'], UNIT]:
                self.finding(5, 'UNIT_MISSING', row, cid=UNIT)
        for row in self.ac:
            if row['pid'] in masters and row['cid'] == UNIT and row['val'] == '':
                self.finding(5, 'UNIT_EMPTY', row)

    def rule6(self):
        if not self.has(6, 'm', 'c'):
            return
        masters = Counter(r['pid'] for r in self.am)
        for pid, multiplicity in masters.items():
            models = self.chars_by_id[pid, MODEL]
            count = len(models) * multiplicity
            if count > 1:
                for row in models:
                    self.finding(6, 'MODEL_MULTIPLE', row, related=f'จำนวน model: {count}')
            elif count == 1:
                model = models[0]
                if model['val'] == '':
                    self.finding(6, 'MODEL_EMPTY', model, severity=self.config['blank_model'])
                else:
                    names = self.chars_by_name[pid, model['val']]
                    if len(names) > 1:
                        for row in names:
                            self.finding(6, 'MODEL_CHAR_NAME_MULTIPLE', row,
                                         related=f"model source row: {model['rn']}")
        for row in self.am:
            if not self.chars_by_id[row['pid'], MODEL]:
                self.finding(6, 'MODEL_MISSING', row, cid=MODEL, severity=self.config['missing_model'])

    def rule7(self):
        if not self.has(7, 'm', 'c'):
            return
        need = [r for r in self.am if not any(c['val'] != '' for c in self.chars_by_id[r['pid'], MAIN])]
        self.coverage['7_pass_at_pop'] = len(self.am) - len(need)
        for row in self.am:
            if not self.chars[row['pid']]:
                self.finding(7, 'NO_POP_CHARACTERISTICS', row, severity='WARNING')
        if not self.has(7, 'o'):
            return
        for row in need:
            owners = self.owner_po.get(row['pid'], set())
            if not owners:
                self.finding(7, 'PO_MAPPING_MISSING', row)
            elif len(owners) > 1:
                self.finding(7, 'MULTIPLE_PO', row, related=f'จำนวน PO: {len(owners)}')
        if not self.has(7, 'cv'):
            return
        for row in need:
            po = self.single_owner(row['pid'])
            if po is None or po in self.ex_po:
                continue
            chars = self.cv[po]
            if not chars:
                self.finding(7, 'PO_CV_MISSING', row, po=po)
            device = next((c for c in chars if c['cid'] == TYPE and c['val'] == 'DEVICE'), None)
            if device and not any(c['cid'] == MAIN and c['val'] != '' for c in chars):
                self.finding(7, 'DEVICE_MAIN_MISSING', row, po=po, cid=MAIN,
                             expected='main_model มีค่าใน POP หรือ Char_Value ของ PO',
                             related=f"DEVICE source: {device['src']} record {device['rn']}")

    def rule8(self):
        if not self.has(8, 'm', 'o'):
            return
        for row in self.am:
            owners = self.owner_po.get(row['pid'], set())
            if not owners:
                self.finding(8, 'PO_MAPPING_MISSING', row)
            elif len(owners) > 1:
                self.finding(8, 'MULTIPLE_PO', row)
            elif len(self.owners[row['pid']]) > 1:
                self.finding(8, 'DUPLICATE_MAPPING', row, po=next(iter(owners)),
                             severity=self.config['duplicate_same_po_mapping'])
        if not self.has(8, 'c', 'cv'):
            return
        masters = {r['pid'] for r in self.am}
        for row in self.ac:
            po = self.single_owner(row['pid'])
            if po is not None and po not in self.ex_po and row['pid'] in masters:
                if (po, row['cid'], row['name'], row['val']) not in self.exact_cv:
                    self.finding(8, 'CV_EXACT_MISSING', row, po=po)

    def rule9(self):
        if not self.has('9.1', 'v'):
            return
        self.pairs = {}
        self.uncertain_po = set()
        for row in self.av:
            pairs, state = parse_pairs(row['cids'], row['vals'])
            self.pairs[row['id']] = pairs
            if state:
                self.uncertain_po.add(row['po'])
                severity = ('ERROR' if state in ('LENGTH_MISMATCH', 'EMPTY_MEMBER') else
                            'WARNING' if state == 'BOTH_EMPTY' else 'REVIEW')
                self.finding('9.1', state, row, severity=severity,
                             val=row['vals'], related=row['cids'])
        self.coverage['9_variant_pairs'] = sum(map(len, self.pairs.values()))
        if self.has('9.2', 'po'):
            masters = {r['po'] for r in self.rows['po']}
            for row in self.av:
                if row['po'] not in masters:
                    self.finding('9.2', 'VARIANT_PO_MISSING', row)
        if self.has('9.2', 'l', 'm', 'o'):
            masters = {r['pid'] for r in self.rows['m']}
            active_vid = group(self.av, 'vid')
            for row in self.rows['l']:
                if row['pid'] in self.ex_pop:
                    continue
                for condition, code in ((not self.variants_by_vid[row['vid']], 'LINK_VARIANT_MISSING'),
                                        (row['pid'] not in masters, 'LINK_POP_MISSING'),
                                        (row['pid'] not in self.owners, 'OWNER_MISSING'),
                                        (len(self.owner_po.get(row['pid'], set())) > 1, 'OWNER_MULTIPLE')):
                    if condition:
                        self.finding('9.2', code, row)
                po = self.single_owner(row['pid'])
                if po is not None and po not in self.ex_po:
                    for variant in active_vid[row['vid']]:
                        if variant['po'] != po:
                            self.finding('9.2', 'OWNER_MISMATCH', row, po=variant['po'],
                                         sku=variant['sku'], related=f'PO ของ POP: {po}')
        if self.has('9.3', 'cv'):
            for row in self.av:
                for pos, (cid, val) in enumerate(self.pairs[row['id']], 1):
                    if (row['po'], cid, val) not in self.allowed_pairs:
                        self.finding('9.3', 'VARIANT_PAIR_NOT_ALLOWED', row, cid=cid, val=val,
                                     related=f'ตำแหน่งสมาชิก: {pos}')
            if self.has('9.3', 'c', 'o'):
                for row in self.ac:
                    po = self.single_owner(row['pid'])
                    if po is not None and po not in self.ex_po and (po, row['cid'], row['val']) not in self.allowed_pairs:
                        self.finding('9.3', 'POP_PAIR_NOT_ALLOWED', row, po=po)
        self.rule94()
        self.rule95()
        self.rule96()

    def rule94(self):
        if not self.has('9.4', 'v', 'c', 'o', 'cv'):
            return
        used = {(v['po'], cid, val) for v in self.av for cid, val in self.pairs[v['id']]}
        for row in self.ac:
            po = self.single_owner(row['pid'])
            if po is not None and po not in self.ex_po:
                used.add((po, row['cid'], row['val']))
        for pid, owners in self.owner_po.items():
            if len(owners) > 1 and pid not in self.ex_pop:
                self.uncertain_po.update(owners)
        for key, rows in group(self.rows['cv'], 'po', 'cid', 'val').items():
            po, cid, val = key
            if val == '' or po in self.ex_po or key in used:
                continue
            uncertain = po in self.uncertain_po
            self.finding('9.4', 'UNUSED_UNCERTAIN' if uncertain else 'UNUSED_CHARACTERISTIC', rows[0],
                         severity='REVIEW' if uncertain else 'ERROR', occurrences=len(rows),
                         expected='ต้องมีการใช้คู่ ID + value ภายใต้ PO เดียวกัน',
                         related='Record แรกของคู่ข้อมูล; Source Occurrences เก็บทุก Record ที่ซ้ำ')

    def rule95(self):
        if not self.has('9.5', 'l', 'v'):
            return
        groups = defaultdict(list)
        for row in self.av:
            for pid in {l['pid'] for l in self.links_by_vid[row['vid']] if l['pid'] not in self.ex_pop}:
                groups[row['po'], pid].append(row)
        self.coverage['9_5_single_variant_groups'] = sum(len(rows) == 1 for rows in groups.values())
        self.coverage['9_5_distinct_sku_groups_pass'] = 0
        for (po, pid), rows in groups.items():
            n = len(rows)
            nsku = len({r['sku'] for r in rows})
            empty = sum(r['sku'] == '' for r in rows)
            if n > 1 and n == nsku and not empty:
                self.coverage['9_5_distinct_sku_groups_pass'] += 1
            elif n > 1:
                self.finding('9.5', 'SAME_OR_EMPTY_SKU', po=po, pid=pid,
                             severity=self.config['same_or_blank_sku'],
                             related=f'Variants={n}; distinct SKU={nsku}; blank SKU={empty}')

    def rule96(self):
        if not self.has('9.6', 'l', 'v', 'c'):
            return
        for row in self.av:
            pairs = self.pairs[row['id']]
            for pid in {l['pid'] for l in self.links_by_vid[row['vid']] if l['pid'] not in self.ex_pop}:
                for cid, val in pairs:
                    chars = self.chars_by_id[pid, cid]
                    if any(c['val'] == val for c in chars):
                        self.finding('9.6', 'DUPLICATE_LEVELS', row, pid=pid, cid=cid, val=val,
                                     related='POP มีคู่ ID + value เดียวกัน; ดู Characteristics for Price ของ POP นี้')
                    if any(c['val'] != val for c in chars):
                        self.finding('9.6', 'DIFFERENT_LEVEL_VALUES', row, pid=pid, cid=cid, val=val,
                                     severity=self.config['cross_level_different_value'])
            for cid, count in Counter(cid for cid, _ in pairs).items():
                if count > 1:
                    self.finding('9.6', 'MULTI_VARIANT_VALUES', row, cid=cid, severity='REVIEW',
                                 related=f'สมาชิกในกลุ่ม: {count}')
        for (pid, cid), rows in group(self.ac, 'pid', 'cid').items():
            n = len({r['val'] for r in rows})
            if n > 1:
                self.finding('9.6', 'MULTI_POP_VALUES', pid=pid, cid=cid, severity='REVIEW',
                             related=f'ค่าที่แตกต่างกัน: {n}')

    def summary(self):
        rules = []
        for number in range(1, 10):
            counts = Counter(i['severity'] for i in self.issues if i['rule'].split('.')[0] == str(number))
            errors, review = counts['ERROR'], counts['REVIEW']
            rules.append(dict(rule=number, status='FAIL' if errors else 'INCOMPLETE' if review else 'PASS',
                              error_cases=errors, review_cases=review, warning_cases=counts['WARNING'], complete=review == 0))
        return dict(version=VERSION, rules=rules, input_issues=sum(i['rule'] == 'INPUT' for i in self.issues),
                    inputs=self.inputs, coverage=self.coverage, source_counts={t: len(r) for t, r in self.rows.items()},
                    cv_blank_value_records=sum(r['val'] == '' for r in self.rows['cv']),
                    exclude_config={'po': len(self.ex_po), 'pop': len(self.ex_pop)},
                    excluded_source_rows={'po': sum(r['po'] in self.ex_po for r in self.rows['po']),
                                          'pop': sum(r['pid'] in self.ex_pop for r in self.rows['m']),
                                          'variants': sum(r['po'] in self.ex_po for r in self.rows['v'])},
                    comparison='exact, case-sensitive, no trim; no sampling',
                    counts_definition='Error cases are rule-specific. The same entity can fail multiple rules. Rule 9.4 counts distinct PO+ID+value, not original rows.')


REASONS = {'MISSING_META': 'ไม่พบ POP ใน POP_metaExt_productInfo',
 'SKU_NOT_FOUND': 'ไม่มีข้อมูลใน Meta Extension POP (productInfo)',
 'VARIANT_LINK_MISSING': 'ไม่มีข้อมูลใน PO (Variant_ProductOffering_Price)',
 'POP_MISMATCH': 'ไม่ตรงกับ POP ใน Meta POP',
 'POP_LINK_MISSING': 'ไม่พบ Variant ที่เชื่อม POP',
 'VARIANT_MISSING': 'Variant ID ที่เชื่อม POP ไม่มีใน Product_Variants',
 'SKU_MATCH_COUNT': 'จำนวนแถว Variant ที่ SKU ตรง matCode ไม่เท่ากับ 1',
 'DUPLICATE_CHAR_NAME': 'Char Name ซ้ำภายใน POP',
 'UNIT_MISSING': 'ไม่พบ unit_name',
 'UNIT_EMPTY': 'unit_name มี value ว่าง',
 'MODEL_MULTIPLE': 'model มีมากกว่า 1 แถว',
 'MODEL_MISSING': 'ไม่พบ model: ยังไม่มีเกณฑ์ตัดสินที่ยืนยัน',
 'MODEL_EMPTY': 'model.value ว่าง: ยังไม่มีเกณฑ์ตัดสินที่ยืนยัน',
 'MODEL_CHAR_NAME_MULTIPLE': 'Char Name ที่ตรง model.value มีมากกว่า 1 แถว',
 'NO_POP_CHARACTERISTICS': 'POP ไม่มี Characteristics for Price แต่ยังตรวจ PO ต่อ',
 'PO_MAPPING_MISSING': 'ไม่พบ PO ของ POP นั้น',
 'MULTIPLE_PO': 'มีมากกว่า 1 PO',
 'PO_CV_MISSING': 'ไม่พบ PO ใน Char_Value',
 'DEVICE_MAIN_MISSING': 'PO เป็น DEVICE แต่ไม่มี main_model ที่มีค่าทั้งระดับ POP และ PO',
 'DUPLICATE_MAPPING': 'หลาย Mapping rows แต่เป็น PO เดียวกัน ต้องยืนยันเกณฑ์',
 'CV_EXACT_MISSING': 'ไม่พบ Char_Value ที่ตรง PO + Characteristics ID + Char Name + value '
                     'ในแถวเดียวกัน',
 'UNUSED_CHARACTERISTIC': 'คู่ข้อมูลใน Char_Value ไม่ถูกใช้ใน Variant หรือ POP ของ PO เดียวกัน',
 'UNUSED_UNCERTAIN': 'ยังยืนยันว่าไม่ได้ใช้ไม่ได้ เพราะ PO มีรายการ comma ที่อ่านไม่ได้หรือ '
                     'Mapping กำกวม',
 'SAME_OR_EMPTY_SKU': 'SKU ซ้ำหรือว่าง ไม่ใช่ Error อัตโนมัติ ต้องยืนยันการแยกแยะ Variant',
 'DUPLICATE_LEVELS': 'คู่ Characteristic เดียวกันซ้ำทั้ง Variant และ POP',
 'DIFFERENT_LEVEL_VALUES': 'ID เดียวกันแต่ value ต่างระหว่าง Variant และ POP ต้องยืนยันกฎ '
                           'Override/หลายค่า',
 'MULTI_VARIANT_VALUES': 'Characteristic มีหลายสมาชิกใน Variant เดียวกัน ต้องยืนยันกฎ',
 'MULTI_POP_VALUES': 'Characteristic มีหลาย value ใน POP เดียวกัน ต้องยืนยันกฎ',
 'VARIANT_PO_MISSING': 'PO ของ Variant ไม่มีใน ProductOffer',
 'LINK_VARIANT_MISSING': 'Variant ที่อ้างอิงไม่มีใน Product_Variants',
 'LINK_POP_MISSING': 'POP ที่อ้างอิงไม่มีใน POP master',
 'OWNER_MISSING': 'POP ที่เชื่อม Variant ไม่มี PO Mapping',
 'OWNER_MULTIPLE': 'POP ที่เชื่อม Variant มีหลาย PO',
 'OWNER_MISMATCH': 'PO ของ Variant ไม่ตรง PO ของ POP',
 'VARIANT_PAIR_NOT_ALLOWED': 'คู่ Characteristic ของ Variant ไม่พบใน Char_Value ที่มีค่า',
 'POP_PAIR_NOT_ALLOWED': 'คู่ Characteristic ของ POP ไม่พบใน Char_Value ที่มีค่า',
 'LENGTH_MISMATCH': 'จำนวน Characteristics และ value ไม่เท่ากัน',
 'EMPTY_MEMBER': 'มีสมาชิกว่างในรายการ comma',
 'BOTH_EMPTY': 'ทั้งสอง Column ว่าง',
 'AMBIGUOUS_QUOTES': 'มี quoted comma ภายในรายการ ต้องยืนยันรูปแบบการแยก'}
