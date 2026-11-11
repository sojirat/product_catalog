"""Exact PO/POP rules over source rows, with no local database."""
from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation
from datetime import datetime, timezone, timedelta
from itertools import islice
from time import monotonic
from validation_progress import stage, batch_progress

from validation_domain import SCHEMAS, UNIT, MODEL, MAIN, TYPE, VERSION, CV_DUPLICATE_KEY, parse_pairs
from validation_domain import PRODUCT_CHAR_COLUMNS, char_key, RULE_NUMBERS


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
        self.resource_spec_lookup = None
        self.product_master_lookup = None
        self.variant_master_lookup = None
        self.main_model_lookup = None
        self.main_model_passes = []
        self.selected_rules = list(RULE_NUMBERS)
        self.mat_code_catalog_lookup = None
        self.run_date = datetime.now(timezone(timedelta(hours=7))).date()
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
            names = ', '.join(SCHEMAS[table][0] + ' [' + table + ']' for table in missing)
            self.add(rule, 'REVIEW', 'MISSING_INPUT',
                     'ยังตรวจข้อนี้ได้ไม่ครบ เพราะข้อมูลต้นทางขาดหรืออ่านไม่สำเร็จ: ' + names +
                     ' ให้ตรวจไฟล์ต้นทางและรายละเอียดใน run.log ก่อนสรุปผลกฎนี้')
        return not missing

    def input_error(self, table, message, **values):
        self.add('INPUT', 'REVIEW', 'INPUT_UNCERTAIN',
                 'อ่านหรือใช้ข้อมูลจาก ' + SCHEMAS[table][0] + ' ไม่สำเร็จ: ' + message +
                 ' ให้ตรวจไฟล์ ชีต และแถวต้นทางที่ระบุ ก่อนนำผลตรวจที่ใช้ข้อมูลชุดนี้ไปสรุป', **values)

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

    def run(self, rules=None):
        self.selected_rules = sorted(set(rules)) if rules is not None else list(RULE_NUMBERS)
        if not self.selected_rules or any(number not in RULE_NUMBERS for number in self.selected_rules):
            raise ValueError('Select at least one rule between 1 and 15')
        stage(25, 'Building validation indexes')
        self.indexes()
        total=len(self.selected_rules)
        for position, number in enumerate(self.selected_rules,1):
            stage(25 + (position-1)*50/total, f'Checking Rule {number}/{max(RULE_NUMBERS)} (selected {position}/{total})')
            started = monotonic()
            first_issue = len(self.issues)
            getattr(self, f'rule{number}')()
            counts = Counter(issue['severity'] for issue in islice(self.issues, first_issue, None))
            stage(25 + position*50/total,
                  f'Rule {number}/{max(RULE_NUMBERS)} finished in {monotonic()-started:.1f}s; '
                  f'Error={counts["ERROR"]}, Review={counts["REVIEW"]}, Warning={counts["WARNING"]}')

    def rule11(self):
        if not self.has(11, 'v'):
            return
        channels = group(self.rows['ch'], 'pid')
        prices = group(self.rows['pt'], 'pid')
        for row in self.av:
            ids = row['cids'].split(',')
            cid = 'price_group-mh_mg00557'
            if cid not in ids:
                continue
            values = row['vals'].split(',')
            positions = [i for i, value in enumerate(ids) if value == cid]
            if len(ids) != len(values) or any(values[i] == '' for i in positions):
                self.finding(11, 'PRICE_GROUP_VALUE_INVALID', row, cid=cid,
                             reason='ไม่สามารถจับคู่ price_group กับ value ได้ เพราะจำนวนสมาชิกไม่เท่ากันหรือค่า price_group ว่าง')
                continue
            if not self.has(11, 'l'):
                return
            links = self.links_by_vid[row['vid']]
            if not links:
                self.finding(11, 'PRICE_GROUP_POP_COUNT', row, cid=cid,
                             reason='Variant ไม่มี POP ที่เชื่อมกัน')
                continue
            pids = sorted({link['pid'] for link in links})
            if not self.has(11, 'pt'):
                return
            invalid_prices = False
            for pid in pids:
                if pid in self.ex_pop:
                    continue
                items = prices[pid]
                if not items or any(item['price_type'] == '' for item in items):
                    self.finding(11, 'PRICE_GROUP_PRICE_TYPE_MISSING', row, pid=pid,
                                 reason='POP ไม่มีข้อมูล priceType')
                    invalid_prices = True
                elif len(items) != 1:
                    self.finding(11, 'PRICE_GROUP_PRICE_TYPE_MULTIPLE', row, pid=pid,
                                 reason='POP มีข้อมูลใน Product Offer Price มากกว่าหนึ่งแถว')
                    invalid_prices = True
            if invalid_prices:
                continue
            if len(links) > 1:
                if not self.has(11, 'pt'):
                    return
                matched = [prices[pid] for pid in pids]
                types = [items[0]['price_type'] for items in matched if len(items) == 1]
                if (len(pids) != len(links) or any(len(items) != 1 for items in matched)
                        or types.count('Onetime') != 1
                        or any(value not in ('Onetime', 'Pre-Booking') for value in types)):
                    self.finding(11, 'PRICE_GROUP_POP_TYPES', row, cid=cid,
                                 reason='Variant ที่เชื่อมหลาย POP ต้องมี Onetime หนึ่งตัว และที่เหลือเป็น Pre-Booking เท่านั้น โดยต้องพบข้อมูลแต่ละ POP หนึ่งแถว',
                                 related='; '.join(f"{pid}: {[p['price_type'] for p in prices[pid]]}" for pid in pids))
                    continue
            if not self.has(11, 'ch'):
                return
            for pid in pids:
                if pid in self.ex_pop:
                    continue
                found = channels[pid]
                if len(found) != 1:
                    self.finding(11, 'PRICE_GROUP_CHANNEL_COUNT', row, pid=pid, cid=cid,
                                 reason='POP มีมากกว่า 1 Channel' if found else 'POP ไม่มี Channel',
                                 related=f'จำนวนแถว Channel: {len(found)}')
                    continue
                channel = found[0]
                price_type = prices[pid][0]['price_type']
                expected_type = 'Pre-Booking' if channel['channel'] == 'Web Pre-Booking' else 'Onetime'
                if channel['channel'] in ('All', 'Web Staff', 'Web Pre-Booking') and price_type != expected_type:
                    self.finding(11, 'PRICE_GROUP_CHANNEL_PRICE_TYPE_MISMATCH', row, pid=pid,
                                 val=price_type, expected=expected_type,
                                 reason='priceType ของ POP ไม่ตรงกับ Channel',
                                 related=f"Channel: {channel['channel']}; priceType source: {prices[pid][0]['src']} row {prices[pid][0]['rn']}")
                    continue
                if channel['channel'] == 'Web Pre-Booking':
                    continue
                expected = {'All': 'EUP', 'Web Staff': 'STAFF'}.get(channel['channel'])
                if expected is None:
                    self.finding(11, 'PRICE_GROUP_CHANNEL_UNDEFINED', row, pid=pid, severity='REVIEW',
                                 reason='ยังไม่ได้กำหนดเกณฑ์ price_group สำหรับ Channel นี้',
                                 related=f"Channel: {channel['channel']}")
                    continue
                for i in positions:
                    if values[i] != expected:
                        self.finding(11, 'PRICE_GROUP_CHANNEL_MISMATCH', row, pid=pid, cid=cid,
                                     val=values[i], expected=expected,
                                     reason='ค่า price_group ไม่ตรงกับ Channel ของ POP',
                                     related=f"index: {i}; Channel: {channel['channel']}; source: {channel['src']} row {channel['rn']}")

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
        need = [r for r in self.am if not any(c['val'] != '' for c in self.chars_by_id[r['pid'], MODEL])]
        if not need or not self.has(6, 'l', 'v'):
            return
        for row in need:
            variants = [v for link in self.links_by_pid[row['pid']]
                        for v in self.variants_by_vid[link['vid']] if v['po'] not in self.ex_po]
            if not any(MODEL in v['cids'].split(',') for v in variants):
                self.finding(6, 'MODEL_MISSING', row, cid=MODEL,
                             reason='POP ไม่มี model ที่มีค่า และ Variant ที่เชื่อมกันทุกแถวไม่มี model-mh_mg00556 ใน specCharacteristics')

    def rule7(self):
        self.main_model_passes = []
        candidates = {}
        if not self.has(7, 'm', 'c'):
            return
        need = [r for r in self.am if not any(c['val'] != '' for c in self.chars_by_id[r['pid'], MAIN])]
        self.coverage['7_pass_at_pop'] = len(self.am) - len(need)
        for row in self.am:
            if not self.chars[row['pid']]:
                self.finding(7, 'NO_POP_CHARACTERISTICS', row, severity='WARNING')
        if not need or not self.has(7, 'l', 'v'):
            return
        for row in need:
            links = self.links_by_pid[row['pid']]
            if not links:
                self.finding(7, 'POP_LINK_MISSING', row)
                continue
            variants = []
            for vid in sorted({link['vid'] for link in links}):
                found = self.variants_by_vid[vid]
                if not found:
                    self.finding(7, 'VARIANT_MISSING', row, vid=vid)
                variants.extend(v for v in found if v['po'] not in self.ex_po)
            if any(MAIN in v['cids'].split(',') for v in variants):
                continue
            if not variants or not self.has(7, 'cv'):
                continue
            for po in sorted({v['po'] for v in variants}):
                chars = self.cv[po]
                if not chars:
                    self.finding(7, 'PO_CV_MISSING', row, po=po)
                device = next((c for c in chars if c['cid'] == TYPE and c['val'] == 'DEVICE'), None)
                if device and not any(c['cid'] == MAIN and c['val'] != '' for c in chars):
                    for variant in variants:
                        if variant['po'] == po:
                            candidates[variant['id'], row['pid']] = (variant, row['pid'])
        if not candidates:
            return
        codes = sorted({v['sku'] for v, pid in candidates.values() if v['sku'] != ''})
        try:
            if codes and self.main_model_lookup is None:
                raise RuntimeError('Main model lookup is not configured')
            masters = self.main_model_lookup(codes) if codes else {}
        except Exception as error:
            for variant, pid in candidates.values():
                self.finding(7, 'MAIN_MODEL_LOOKUP_UNAVAILABLE', variant, pid=pid, severity='REVIEW',
                             reason='ตรวจ PRODUCT_MST.MAIN_MODEL ไม่สำเร็จ จึงยังสรุปข้อ 7 ไม่ได้',
                             related=type(error).__name__)
            return
        for variant, pid in candidates.values():
            rows = masters.get(variant['sku'], []) if variant['sku'] else []
            if len(rows) > 1:
                self.finding(7, 'MAIN_MODEL_MASTER_MULTIPLE', variant, pid=pid, severity='REVIEW',
                             reason='พบ MAT_CODE ใน PRODUCT_MST หลายแถว ยังไม่มีเกณฑ์เลือก MAIN_MODEL', related=str(len(rows)))
            elif not rows or rows[0]['MAIN_MODEL'] not in (None, ''):
                self.finding(7, 'DEVICE_MAIN_MISSING', variant, pid=pid, cid=MAIN,
                             reason='ไม่มี main_model ใน POP, Variant และ PO ที่เป็น DEVICE และ ' +
                             ('ไม่พบ MAT_CODE ใน PRODUCT_MST' if not rows else 'PRODUCT_MST.MAIN_MODEL มีข้อมูล'),
                             expected="PRODUCT_MST.MAIN_MODEL IS NULL OR MAIN_MODEL = ''",
                             related=f"MAT_CODE={variant['sku']!r}; MAIN_MODEL={rows[0]['MAIN_MODEL']!r}" if rows else f"MAT_CODE={variant['sku']!r}")
            else:
                entry = dict.fromkeys(('src','sheet','po','pid','vid','sku','cid','name','val','expected','related'), '')
                entry.update({key:variant[key] for key in ('src','sheet','rn','po','vid','sku')})
                entry.update(id=len(self.main_model_passes)+1, rule='7', severity='PASS', code='MAIN_MODEL_NULL_ALLOWED',
                             reason='ไม่มี main_model ใน POP, Variant และ PO แต่ PRODUCT_MST.MAIN_MODEL เป็น NULL หรือข้อความว่าง จึงผ่าน',
                             pid=pid, cid=MAIN, related='PRODUCT_MST.MAIN_MODEL = '+('NULL' if rows[0]['MAIN_MODEL'] is None else repr(rows[0]['MAIN_MODEL'])), occurrences=1)
                self.main_model_passes.append(entry)
        self.coverage['7_main_model_null_pass_rows'] = len(self.main_model_passes)

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
                         related='แสดงแถวแรกของคู่ PO + ID + value นี้; ดูทุกแถวที่ซ้ำในชีต Rule 9 Sources')

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

    def rule10(self):
        self.duplicate_cv_rows = []
        if not self.has(10, 'cv'):
            return
        active = [row for row in self.rows['cv'] if row['po'] not in self.ex_po and row['val'] != '']
        for rows in group(active, *CV_DUPLICATE_KEY).values():
            if len(rows) > 1:
                self.duplicate_cv_rows.extend(rows)
                for row in rows:
                    self.finding(10, 'DUPLICATE_CV', row,
                                 related=f"valueType={row['value_type']}; จำนวนแถวในกลุ่ม: {len(rows)}")
        self.duplicate_cv_rows.sort(key=lambda row: tuple(row[f] for f in CV_DUPLICATE_KEY) + (row['id'],))
        self.coverage['10_checked_rows'] = len(active)
        self.coverage['10_duplicate_rows'] = len(self.duplicate_cv_rows)

    def rule12(self):
        if not self.has(12, 'cv'):
            return
        candidates = [row for row in self.rows['cv']
                      if row['po'] not in self.ex_po and '-rs_mg' in row['spec_id'] and row['val'] != '']
        pairs = group(candidates, 'po', 'spec_id')
        valid_pairs = {}
        for po, rows in group(candidates, 'po').items():
            specs = sorted({row['spec_id'] for row in rows})
            if len(specs) > 1:
                self.finding(12, 'MULTIPLE_RESOURCE_SPEC', rows[0], occurrences=len(rows),
                             related='Product Spec IDs: ' + ', '.join(specs))
            else:
                valid_pairs[po, specs[0]] = pairs[po, specs[0]]
        self.coverage['12_candidate_rows'] = len(candidates)
        self.coverage['12_candidate_pairs'] = len(pairs)
        self.coverage['12_checked_pairs'] = 0
        if not valid_pairs:
            return
        if self.resource_spec_lookup is None:
            self.add(12, 'REVIEW', 'RESOURCE_SPEC_LOOKUP_UNAVAILABLE',
                     'ยังตรวจ Resource Specification ไม่ครบ เพราะไม่มีผล query จากฐานข้อมูล ให้ตรวจการเชื่อมต่อและสิทธิ์อ่าน View แล้วรันใหม่')
            return
        try:
            found = self.resource_spec_lookup(sorted(valid_pairs))
        except Exception as error:
            self.add(12, 'REVIEW', 'RESOURCE_SPEC_LOOKUP_UNAVAILABLE',
                     'ตรวจ Resource Specification ไม่สำเร็จ ให้ตรวจ .env การเชื่อมต่อและสิทธิ์อ่าน View แล้วรันใหม่',
                     related='vw_catalog_offer_specification_characteristic; '+type(error).__name__)
            return
        self.coverage['12_checked_pairs'] = len(valid_pairs)
        for pair, rows in valid_pairs.items():
            if pair not in found:
                self.finding(12, 'INVALID_RESOURCE_SPEC', rows[0], occurrences=len(rows),
                             expected='พบ offer_id + specification_id ใน vw_catalog_offer_specification_characteristic',
                             related='Product Spec ID: '+pair[1])

    def rule13(self):
        if not self.has(13, 't'):
            return
        active = [row for row in self.rows['t'] if row['pid'] not in self.ex_pop]
        self.coverage['13_meta_rows'] = len(active)
        self.coverage['13_checked_rows'] = 0
        codes = sorted({row['sku'] for row in active if row['sku'] != ''})
        for number, row in enumerate(active, 1):
            batch_progress('Rule 13 Meta input scan', number, len(active), interval=10000)
            if row['sku'] == '':
                self.finding(13, 'META_MAT_CODE_EMPTY', row)
        if not codes:
            return
        try:
            if self.product_master_lookup is None:
                raise RuntimeError('Product Master lookup is not configured')
            masters = self.product_master_lookup(codes)
        except Exception as error:
            self.add(13, 'REVIEW', 'PRODUCT_MASTER_LOOKUP_UNAVAILABLE',
                     'ตรวจ Product Master ไม่สำเร็จ ให้ตรวจ .env การเชื่อมต่อและสิทธิ์อ่าน PRODUCT_MST แล้วรันใหม่',
                     related='PRODUCT_MST; '+type(error).__name__)
            return
        comparisons = [('commercial_name', 'commercialName', 'COMMERCIAL_NAME'),
                       ('sap_eng', 'sapDescriptionEng', 'SAP_DESCRIPTION'),
                       ('sap_tha', 'sapDescriptionTha', 'SAP_DESCRIPTION')]
        for number, row in enumerate(active, 1):
            batch_progress('Rule 13 Meta comparisons', number, len(active), interval=10000)
            if row['sku'] == '':
                continue
            matches = masters[row['sku']]
            if not matches:
                self.finding(13, 'PRODUCT_MASTER_MISSING', row)
            else:
                self.coverage['13_checked_rows'] += 1
                master = matches[0]
                for field, label, column in comparisons:
                    if field == 'commercial_name' and master['COMMERCIAL_NAME'] in (None, ''):
                        column = 'SAP_DESCRIPTION'
                    if row[field] != master[column]:
                        self.finding(13, 'META_PRODUCT_MASTER_MISMATCH', row,
                                     reason=f"matCode={row['sku']!r}: Meta POP.{label} = {row[field]!r} ไม่ตรงกับ PRODUCT_MST.{column} = {master[column]!r}",
                                     name=label, val=row[field], expected=repr(master[column]),
                                     related='PRODUCT_MST.'+column)

    def rule14(self):
        if not self.has(14, 'v', 'l', 'pv', 'c'):
            return
        variants = [row for row in self.rows['v'] if row['po'] not in self.ex_po]
        links = group(self.rows['l'], 'vid')
        prices = group(self.rows['pv'], 'pid')
        chars = group(self.rows['c'], 'pid')
        pending = []
        self.coverage['14_checked_variants'] = 0
        for row in variants:
            def error(code, reason, **values):
                self.finding(14, code, row, reason=reason, **values)
            pairs, state = parse_pairs(row['cids'], row['vals'])
            if state not in (None, 'BOTH_EMPTY'):
                error('VARIANT_CHAR_LIST_INVALID', 'จับคู่ Char ของ Variant ตาม index ไม่ได้: '+state)
                continue
            pids = sorted({link['pid'] for link in links[row['vid']] if link['pid'] not in self.ex_pop})
            if links[row['vid']] and not pids:
                continue
            missing = [pid for pid in pids if not prices[pid]]
            if missing:
                error('VARIANT_PRICE_POP_MISSING', 'ไม่พบ POP ที่ Variant อ้างอิงใน Product Offer Price', related=', '.join(missing))
                continue
            onetime = [price for pid in pids for price in prices[pid] if price['price_type'] == 'Onetime']
            if len(onetime) != 1:
                error('VARIANT_ONETIME_COUNT', f'Variant ต้องเชื่อมกับ POP priceType=Onetime หนึ่งแถว พบ {len(onetime)} แถว',
                      related=', '.join(pids))
                continue
            pop = onetime[0]
            char_list = defaultdict(set)
            for name, value in pairs + [(char['name'], char['val']) for char in chars[pop['pid']]]:
                if value != '':
                    char_list[char_key(name)].add(value)
            if row['sku'] == '':
                error('VARIANT_MASTER_SKU_EMPTY', 'Variant มี SKU ว่าง จึงค้น PRODUCT_MST ไม่ได้', pid=pop['pid'])
                continue
            pending.append((row, pop, char_list))
        if not pending:
            return
        try:
            if self.variant_master_lookup is None:
                raise RuntimeError('Variant master lookup is not configured')
            masters = self.variant_master_lookup(sorted({row['sku'] for row, _, _ in pending}))
        except Exception as exception:
            self.add(14, 'REVIEW', 'VARIANT_MASTER_LOOKUP_UNAVAILABLE',
                     'ตรวจ PRODUCT_MST / PRICE_MST ไม่สำเร็จ ให้ตรวจ .env และสิทธิ์อ่านตารางแล้วรันใหม่',
                     related=type(exception).__name__)
            return
        for number, (row, pop, char_list) in enumerate(pending, 1):
            batch_progress('Rule 14 Variant comparisons', number, len(pending), interval=1000)
            def error(code, reason, **values):
                self.finding(14, code, row, reason=reason, pid=pop['pid'], **values)
            reference = masters[row['sku']]
            products = reference['products']
            multiple_products = len(products) > 1
            if multiple_products:
                companies = char_list[char_key('company')]
                products = [product for product in products if product['COMPANY'] in companies]
            if not products:
                detail = (f' หลังเทียบ COMPANY กับ Char List company={sorted(companies)!r}' if multiple_products else '')
                error('VARIANT_PRODUCT_MASTER_COUNT', f'SKU={row["sku"]!r}: ไม่พบ PRODUCT_MST ที่ใช้ตรวจได้{detail}')
                continue
            self.coverage['14_checked_variants'] += 1
            for master in products:
                for column in PRODUCT_CHAR_COLUMNS:
                    source_name = 'storage_capacity' if column == 'CAPACITY' else column
                    actual = char_list[char_key(source_name)]
                    detail = 'PRODUCT_ID='+str(master['PRODUCT_ID'])
                    if column == 'MODEL' and actual:
                        if len(actual) != 1:
                            error('VARIANT_MODEL_REFERENCE_INVALID',
                                  f'model ต้องชี้ชื่อ Char หนึ่งชื่อ พบ {sorted(actual)!r}', name='MODEL',
                                  val=repr(sorted(actual)), expected=repr(master[column]), related=detail)
                            continue
                        reference_name = next(iter(actual))
                        target_key = char_key(reference_name)
                        actual = char_list[target_key]
                        if target_key == char_key('model'):
                            error('VARIANT_MODEL_REFERENCE_MISSING',
                                  f'model={reference_name!r}: ชี้กลับมาที่ model เอง',
                                  name='MODEL', val=reference_name, expected=repr(master[column]), related=detail)
                            continue
                        source_name = f'model -> {reference_name}'
                        if not actual:
                            source_name += ' (ไม่พบ Char ปลายทางที่มีค่า จึงต้องไม่มีค่า MODEL)'
                    detail += '; Char source='+source_name
                    expected = set() if master[column] in (None, '') else {master[column]}
                    if actual != expected:
                        error('VARIANT_MASTER_CHAR_MISMATCH',
                              f'Char {source_name}: Char List={sorted(actual)!r} ไม่ตรงกับ PRODUCT_MST.{column}={master[column]!r}',
                              name=column, val=repr(sorted(actual)), expected=repr(master[column]),
                              related=detail)
            groups = char_list[char_key('price_group')]
            if len(groups) != 1:
                error('VARIANT_PRICE_GROUP_COUNT', f'Char List ต้องมี price_group หนึ่งค่า พบ {sorted(groups)!r}')
                continue
            price_group = next(iter(groups))
            product_ids = list(dict.fromkeys(product['PRODUCT_ID'] for product in products))
            product_prices = ([dict(price, PRODUCT_ID=product_id)
                               for product_id in product_ids
                               for price in reference['prices_by_product'][product_id]] if multiple_products
                              else [dict(price, PRODUCT_ID=products[0]['PRODUCT_ID']) for price in reference['prices']])
            matching = [price for price in product_prices if price['PRICE_GROUP'] == price_group]
            if not matching:
                error('VARIANT_PRICE_MASTER_MISSING', f'ไม่พบ PRICE_MST ของ PRODUCT_ID={product_ids!r} และ PRICE_GROUP={price_group!r}')
                continue
            if len(matching) > 1:
                try:
                    dated = []
                    for price in matching:
                        value = price.get('EFFECTIVE_DATE')
                        date = None if value in (None, '') else (value if isinstance(value, datetime) else datetime.fromisoformat(str(value)))
                        if date is not None:
                            date = date.replace(tzinfo=timezone.utc) if date.tzinfo is None else date.astimezone(timezone.utc)
                        dated.append((date, price))
                    latest = max(date for date, price in dated if date is not None)
                    matching = [price for date, price in dated if date == latest]
                except (ValueError, TypeError):
                    error('VARIANT_PRICE_MASTER_MULTIPLE', 'เลือกแถวราคาล่าสุดไม่ได้ เพราะ EFFECTIVE_DATE ไม่มีค่าหรือรูปแบบไม่ถูกต้อง', severity='REVIEW', related=f'PRODUCT_ID={product_ids!r}')
                    continue
                if len(matching) != 1:
                    error('VARIANT_PRICE_MASTER_MULTIPLE', f'พบหลายแถวที่ EFFECTIVE_DATE ล่าสุดเท่ากัน: {latest.isoformat()}', severity='REVIEW', related=f'PRODUCT_ID={product_ids!r}')
                    continue
            inc_vat = matching[0]['INC_VAT']
            try:
                actual_price, expected_price = Decimal(str(pop['price_value'])), Decimal(str(inc_vat))
                if not actual_price.is_finite() or not expected_price.is_finite():
                    raise InvalidOperation
            except (InvalidOperation, ValueError):
                error('VARIANT_PRICE_INVALID', f'ราคาไม่ใช่ตัวเลขที่เปรียบเทียบได้: price_value={pop["price_value"]!r}, INC_VAT={inc_vat!r}')
                continue
            if actual_price != expected_price:
                error('VARIANT_PRICE_MISMATCH', f'POP.price_value={pop["price_value"]!r} ไม่ตรงกับ PRICE_MST.INC_VAT={inc_vat!r} ของ PRICE_GROUP={price_group!r}',
                      val=pop['price_value'], expected=str(inc_vat), related='PRODUCT_ID='+str(matching[0]['PRODUCT_ID'])+'; EFFECTIVE_DATE='+str(matching[0].get('EFFECTIVE_DATE')))

    def rule15(self):
        from rule15 import check_mat_code_coverage
        check_mat_code_coverage(self)

    def summary(self):
        rules = []
        for number in self.selected_rules:
            counts = Counter(i['severity'] for i in self.issues if i['rule'].split('.')[0] == str(number))
            errors, review = counts['ERROR'], counts['REVIEW']
            rules.append(dict(rule=number, status='FAIL' if errors else 'INCOMPLETE' if review else 'PASS',
                              error_cases=errors, review_cases=review, warning_cases=counts['WARNING'], complete=review == 0))
        return dict(version=VERSION, rules=rules, selected_rules=self.selected_rules,
                    skipped_rules=sorted(set(RULE_NUMBERS)-set(self.selected_rules)),
                    input_issues=sum(i['rule'] == 'INPUT' for i in self.issues),
                    inputs=self.inputs, coverage=self.coverage, source_counts={t: len(r) for t, r in self.rows.items()},
                    cv_blank_value_records=sum(r['val'] == '' for r in self.rows['cv']),
                    exclude_config={'po': len(self.ex_po), 'pop': len(self.ex_pop)},
                    excluded_source_rows={'po': sum(r['po'] in self.ex_po for r in self.rows['po']),
                                          'pop': sum(r['pid'] in self.ex_pop for r in self.rows['m']),
                                          'variants': sum(r['po'] in self.ex_po for r in self.rows['v'])},
                    comparison='exact, case-sensitive, no trim; no sampling',
                    counts_definition='Error cases are rule-specific. The same entity can fail multiple rules. Rule 9.4 counts distinct PO+ID+value, not original rows.')


REASONS = {
 'META_MAT_CODE_EMPTY': 'Meta POP มี matCode ว่าง จึงค้น PRODUCT_MST ด้วย MAT_CODE ไม่ได้',
 'PRODUCT_MASTER_MISSING': 'ไม่พบ matCode ของ Meta POP ใน PRODUCT_MST.MAT_CODE',
 'META_PRODUCT_MASTER_MISMATCH': 'ข้อมูล Meta POP ไม่ตรงกับ Product Master ให้เทียบคอลัมน์ใน Char Name กับคอลัมน์ PRODUCT_MST ใน Related Evidence โดย value คือค่าจาก Meta และ Expected Condition คือค่าจาก Product Master',
 'INVALID_RESOURCE_SPEC': 'Resource Specification ที่เลือกไม่ถูกต้อง ไม่พบคู่ Product Offer ID และ Product Spec ID ใน View vw_catalog_offer_specification_characteristic',
 'MULTIPLE_RESOURCE_SPEC': 'Product Offer ID เดียวมี Resource Specification ที่มี value มากกว่าหนึ่ง ID จึงเลือก Resource Specification เดียวเพื่อตรวจต่อไม่ได้',
 'DUPLICATE_CV': 'พบแถวซ้ำภายใน Product Offer ID เดียวกัน โดย Characteristics ID + Characteristics Name + valueType + value ตรงกันครบ ให้ตรวจทุกแถวในชีต Char duplicate detail',
 'MISSING_META': 'พบ POP ID นี้ในรายการหลัก Product Offer Price แต่ไม่พบ POP ID เดียวกันใน POP_metaExt_productInfo ให้ตรวจว่าข้อมูล Meta ของ POP นี้ตกหล่นหรือระบุ ID ต่างกัน',
 'SKU_NOT_FOUND': 'พบ Variant นี้ใน Product Variants แต่ไม่พบ matCode ที่ตรงกับ SKU ของ Variant ใน POP_metaExt_productInfo ให้ค้น SKU จากคอลัมน์ SKU / matCode ในข้อมูล Meta',
 'VARIANT_LINK_MISSING': 'พบ Variant และพบ SKU ใน POP_metaExt_productInfo แล้ว แต่ไม่พบ Variant ID เดียวกันใน Variant_ProductOffering_Price จึงหา POP ที่เชื่อมกับ Variant ไม่ได้ ให้ตรวจรายการเชื่อมและการสะกด Variant ID',
 'POP_MISMATCH': 'พบ SKU ใน POP_metaExt_productInfo และพบรายการเชื่อม Variant แล้ว แต่ POP ID จากรายการเชื่อมไม่ตรงกับ POP ใดของ matCode นั้น ให้เทียบ POP ID ใน Variant_ProductOffering_Price กับข้อมูล Meta ของ SKU นี้',
 'POP_LINK_MISSING': 'พบ POP นี้ใน POP_metaExt_productInfo แต่ไม่พบรายการเชื่อม POP ID เดียวกันใน Variant_ProductOffering_Price จึงย้อนหา Variant ของ POP นี้ไม่ได้ ให้ตรวจรายการเชื่อมของ POP ID ที่ระบุ',
 'VARIANT_MISSING': 'รายการเชื่อมของ POP นี้อ้างถึง Variant ID ที่ไม่มีใน Product Variants ให้ค้น Variant ID ที่ระบุ แล้วตรวจว่าข้อมูล Variant ตกหล่นหรือ ID ในรายการเชื่อมไม่ตรงกัน',
 'SKU_MATCH_COUNT': 'เมื่อตาม POP จากข้อมูล Meta ไปยัง Variant ที่เชื่อมกัน พบจำนวนแถว Variant ที่ SKU ตรงกับ matCode ไม่เท่ากับ 1 ดูจำนวนที่พบในคอลัมน์ value แล้วตรวจรายการเชื่อมและแถว Variant ที่ขาดหรือซ้ำ',
 'DUPLICATE_CHAR_NAME': 'พบ Char Name เดียวกันมากกว่า 1 แถวภายใน POP เดียวกันใน Characteristics for Price ให้ตรวจทุกแถวของ POP ID + Char Name นี้ จำนวนแถวในกลุ่มอยู่ใน Related Evidence',
 'UNIT_MISSING': 'พบ POP ในรายการหลัก แต่ไม่มี Characteristics ID ของ unit_name ใน Characteristics for Price ให้ตรวจรายการ unit_name ของ POP ID นี้ ตาม ID ที่ระบุในคอลัมน์ Characteristics ID',
 'UNIT_EMPTY': 'พบรายการ unit_name ของ POP นี้ใน Characteristics for Price แต่คอลัมน์ value ว่าง ให้ตรวจค่าหน่วยของแถวต้นทางที่ระบุ',
 'MODEL_MULTIPLE': 'เมื่อนับรายการ model ของ POP นี้ร่วมกับจำนวนแถว POP ในรายการหลัก ได้มากกว่า 1 รายการ ให้ตรวจแถว model ใน Characteristics for Price และ POP ID ที่ซ้ำในรายการหลัก ดูจำนวนที่นับได้ใน Related Evidence',
 'MODEL_MISSING': 'POP นี้ไม่มีรายการ model ใน Characteristics for Price จึงตรวจ model ต่อไม่ได้ ให้ตรวจว่าข้อมูลตกหล่นหรืออนุญาตให้ไม่มี model ปัจจุบันยังไม่มีเกณฑ์ยืนยันกรณีนี้ ระดับผลตรวจใช้ตาม config',
 'MODEL_EMPTY': 'พบรายการ model ของ POP นี้ แต่ value ว่าง จึงนำค่าไปตรวจ Char Name ต่อไม่ได้ ให้ตรวจแถว model ต้นทางและยืนยันว่าอนุญาตให้ว่างหรือไม่ ระดับผลตรวจใช้ตาม config',
 'MODEL_CHAR_NAME_MULTIPLE': 'นำ value ของ model ไปค้น Char Name ภายใน POP เดียวกันแล้วพบมากกว่า 1 แถว ให้ตรวจ Char Name ที่ซ้ำใน Characteristics for Price โดย Related Evidence ระบุแถวต้นทางของ model',
 'NO_POP_CHARACTERISTICS': 'พบ POP ในรายการหลัก แต่ไม่มีแถวใดของ POP นี้ใน Characteristics for Price ให้ตรวจว่าข้อมูล Characteristics ตกหล่นหรือไม่ โปรแกรมยังตรวจ main_model จาก PO ที่เชื่อมกันต่อ',
 'PO_MAPPING_MISSING': 'ไม่พบรายการเชื่อม POP ID นี้กับ PO ในข้อมูล Product Offer Price ฝั่ง PO จึงระบุ PO เจ้าของ POP เพื่อใช้ตรวจต่อไม่ได้ ให้ตรวจคู่ Product Offer ID + Product Offer Price ID ในข้อมูลต้นทาง',
 'MULTIPLE_PO': 'พบ POP ID นี้เชื่อมกับ PO ID ที่ต่างกันมากกว่า 1 ค่าในข้อมูล Product Offer Price ฝั่ง PO จึงเลือก PO เจ้าของเพียงรายการเดียวไม่ได้ ให้ตรวจว่า POP นี้ควรอยู่ภายใต้ PO ใด',
 'PO_CV_MISSING': 'POP นี้ไม่มี main_model ที่มีค่า และเมื่อย้อนหา PO เจ้าของแล้ว ไม่พบแถวของ PO ID นั้นใน Char_Value จึงตรวจข้อมูลสำรองของ PO ไม่ได้ ให้ตรวจข้อมูล Char_Value ของ PO ID ที่ระบุ',
 'DEVICE_MAIN_MISSING': 'POP นี้ไม่มี main_model ที่มีค่า และ PO เจ้าของมี product_type = DEVICE แต่ใน Char_Value ของ PO ก็ไม่มี main_model ที่มีค่า ให้ตรวจ main_model ใน Characteristics for Price ของ POP หรือ Char_Value ของ PO นี้',
 'DUPLICATE_MAPPING': 'พบรายการเชื่อม POP กับ PO มากกว่า 1 แถว แต่ทุกแถวอ้างถึง PO เดียวกัน ให้ตรวจแถวซ้ำในข้อมูล Product Offer Price ฝั่ง PO และยืนยันว่าอนุญาตให้มีหลายแถวหรือไม่ ระดับผลตรวจใช้ตาม config',
 'CV_EXACT_MISSING': 'พบ Characteristic ของ POP แต่ไม่พบแถวใน Char_Value ของ PO เจ้าของที่ตรงครบทั้ง PO ID + Characteristics ID + Char Name + value ในแถวเดียวกัน ให้เทียบค่าทั้งสี่คอลัมน์กับข้อมูลต้นทาง แม้ ID และ value ตรงแต่ชื่อแตกต่างก็ไม่ผ่านข้อนี้',
 'UNUSED_CHARACTERISTIC': 'พบคู่ Characteristics ID + value ที่มีค่าใน Char_Value ของ PO นี้ แต่ไม่พบการใช้คู่เดียวกันใน Variant หรือ Characteristics for Price ของ POP ภายใต้ PO เดียวกัน ให้ตรวจว่าคู่นี้ยังจำเป็นหรือขาดรายการใช้งาน การใช้ใน PO อื่นไม่นับ',
 'UNUSED_UNCERTAIN': 'ยังไม่พบการใช้คู่ Characteristics ID + value นี้ แต่ PO มีรายการ comma ของ Variant ที่แยกคู่ไม่ได้ หรือมี POP ที่เชื่อมหลาย PO จึงยังยืนยันว่าไม่ได้ใช้ไม่ได้ ให้ตรวจรายการที่กำกวมก่อนสรุปข้อนี้',
 'SAME_OR_EMPTY_SKU': 'มีหลาย Variant ภายใต้ PO เดียวกันที่เชื่อม POP เดียวกัน แต่ SKU บางรายการซ้ำหรือว่าง จึงใช้ SKU แยกแต่ละ Variant ได้ไม่ครบ ให้ตรวจ SKU ของกลุ่มนี้และยืนยันเกณฑ์การแยก Variant ดูจำนวนใน Related Evidence',
 'DUPLICATE_LEVELS': 'พบ Characteristics ID + value คู่เดียวกันทั้งใน Variant และ Characteristics for Price ของ POP ที่ Variant เชื่อมอยู่ จึงเป็นข้อมูลซ้ำระหว่างสองระดับ ให้เทียบคู่ที่ระบุ แล้วตรวจว่าควรกำหนดไว้ที่ระดับใด',
 'DIFFERENT_LEVEL_VALUES': 'Variant และ POP ที่เชื่อมกันมี Characteristics ID เดียวกัน แต่พบ value ที่ต่างกัน ให้เทียบ value ทั้งสองระดับและยืนยันว่าอนุญาตให้ Override หรือมีหลายค่าได้หรือไม่ ระดับผลตรวจใช้ตาม config',
 'MULTI_VARIANT_VALUES': 'ใน Variant เดียวกัน พบ Characteristics ID นี้มากกว่า 1 ตำแหน่งในรายการ comma โดย value อาจเหมือนหรือต่างกัน ให้ตรวจรายการ specCharacteristics และ value แล้วนำเกณฑ์หลายค่ามายืนยันก่อนสรุป',
 'MULTI_POP_VALUES': 'ใน POP เดียวกัน พบ Characteristics ID นี้มี value ต่างกันมากกว่า 1 ค่าใน Characteristics for Price ให้ตรวจทุกแถวของ POP ID + Characteristics ID นี้และยืนยันว่าอนุญาตให้มีหลายค่าหรือไม่',
 'VARIANT_PO_MISSING': 'Variant ระบุ PO ID ที่ไม่พบในรายการหลัก ProductOffer ให้ค้น PO ID ที่ระบุ แล้วตรวจว่ารายการ PO ตกหล่นหรือ Product Id ของ Variant อ้างอิงไม่ถูกต้อง',
 'LINK_VARIANT_MISSING': 'พบรายการใน Variant_ProductOffering_Price ที่อ้างถึง Variant ID ซึ่งไม่มีใน Product Variants ให้เทียบ Variant ID ระหว่างรายการเชื่อมกับข้อมูล Variant',
 'LINK_POP_MISSING': 'พบรายการใน Variant_ProductOffering_Price ที่อ้างถึง POP ID ซึ่งไม่มีในรายการหลัก Product Offer Price ให้ตรวจ POP ID ในรายการเชื่อมและข้อมูลหลักของ POP',
 'OWNER_MISSING': 'POP ที่รายการเชื่อม Variant อ้างถึง ไม่มีรายการระบุ PO เจ้าของในข้อมูล Product Offer Price ฝั่ง PO ให้ตรวจคู่ Product Offer ID + Product Offer Price ID ของ POP นี้',
 'OWNER_MULTIPLE': 'POP ที่รายการเชื่อม Variant อ้างถึง มี PO เจ้าของมากกว่า 1 ค่าในข้อมูล Product Offer Price ฝั่ง PO จึงระบุเจ้าของเดียวไม่ได้ ให้ตรวจรายการเชื่อม POP กับ PO',
 'OWNER_MISMATCH': 'PO ID ที่ระบุใน Variant ไม่ตรงกับ PO เจ้าของ POP ที่ Variant เชื่อมอยู่ ให้เทียบ PO ID ในรายงานกับ PO ของ POP ใน Related Evidence แล้วตรวจรายการเชื่อมทั้งสองฝั่ง',
 'VARIANT_PAIR_NOT_ALLOWED': 'Variant ใช้คู่ Characteristics ID + value ที่ไม่พบใน Char_Value ที่มีค่าของ PO เดียวกัน ให้ค้น PO ID + Characteristics ID + value ที่ระบุใน Char_Value โดย Related Evidence ระบุตำแหน่งคู่ในรายการ comma',
 'POP_PAIR_NOT_ALLOWED': 'Characteristic ของ POP ใช้คู่ Characteristics ID + value ที่ไม่พบใน Char_Value ที่มีค่าของ PO เจ้าของ ให้เทียบ PO ID + Characteristics ID + value ที่ระบุ ข้อนี้ไม่ใช้ Char Name เป็นเงื่อนไข',
 'LENGTH_MISMATCH': 'เมื่อแยกด้วย comma แล้ว จำนวน Characteristics ID ใน specCharacteristics ไม่เท่ากับจำนวนสมาชิกใน value ของ Variant จึงจับคู่ตามลำดับไม่ได้ ให้ตรวจทั้งสองคอลัมน์ โดยรายงานแสดงรายการ ID ใน Related Evidence และรายการค่าใน value',
 'EMPTY_MEMBER': 'รายการ specCharacteristics หรือ value ของ Variant มีสมาชิกว่าง เช่น comma ติดกัน หรือ comma ที่ต้นหรือท้ายรายการ จึงจับคู่ ID กับค่าได้ไม่ครบ ให้ตรวจรายการ ID ใน Related Evidence และรายการค่าใน value',
 'BOTH_EMPTY': 'Variant นี้ว่างทั้ง specCharacteristics และ value จึงไม่มีคู่ Characteristic ให้ตรวจในระดับ Variant ให้ยืนยันว่าตั้งใจไม่กำหนด Characteristic หรือข้อมูลตกหล่น',
 'AMBIGUOUS_QUOTES': 'พบสมาชิกที่ใส่เครื่องหมายคำพูดครอบข้อความซึ่งมี comma อยู่ภายใน จึงยังระบุไม่ได้ว่า comma นั้นเป็นส่วนของค่าหรือตัวแบ่งสมาชิก ให้ตรวจรายการ ID ใน Related Evidence และรายการค่าใน value แล้วกำหนดรูปแบบการแยกให้ชัดเจน',
}
