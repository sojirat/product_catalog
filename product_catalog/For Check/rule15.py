"""Reverse coverage: eligible Product Master rows must occur in Product Variants."""
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone

from validation_domain import char_key, parse_pairs
from validation_progress import batch_progress

BANGKOK = timezone(timedelta(hours=7))


def calendar_date(value):
    if value in (None, ''):
        return None
    if isinstance(value, datetime):
        return (value.astimezone(BANGKOK) if value.tzinfo else value).date()
    if isinstance(value, date):
        return value
    parsed = datetime.fromisoformat(value)
    return (parsed.astimezone(BANGKOK) if parsed.tzinfo else parsed).date()


def expiry_date(value):
    parsed = calendar_date(value)
    return None if parsed == date(1900, 1, 1) else parsed


def check_mat_code_coverage(validator):
    v = validator
    if not v.has(15, 'v'):
        return
    try:
        if v.mat_code_catalog_lookup is None:
            raise RuntimeError('Mat code catalog lookup is not configured')
        catalog = v.mat_code_catalog_lookup()
    except Exception as error:
        v.add(15, 'REVIEW', 'MAT_CODE_LOOKUP_UNAVAILABLE',
              'อ่าน PRODUCT_MST / PRICE_MST เพื่อตรวจความครบถ้วนของ MAT_CODE ไม่สำเร็จ',
              related=type(error).__name__)
        return
    today = v.run_date
    v.coverage['15_run_date_bangkok'] = today.isoformat()
    v.coverage['15_product_master_rows'] = len(catalog['products'])
    v.coverage['15_eligible_product_rows'] = 0
    v.coverage['15_checked_price_groups'] = 0
    v.coverage['15_excluded_po_products'] = 0
    variants = defaultdict(list)
    all_variants = defaultdict(list)
    for row in v.rows['v']:
        all_variants[row['sku']].append(row)
        if row['po'] not in v.ex_po:
            variants[row['sku']].append(row)
    prices = defaultdict(list)
    for row in catalog['prices']:
        prices[row['PRODUCT_ID']].append(row)
    group_cache = {}
    for number, product in enumerate(catalog['products'], 1):
        batch_progress('Rule 15 Product Master rows', number, len(catalog['products']), interval=1000)
        if product['PRODUCT_TYPE'] == 'SERVICE' or product['CATEGORY'] in (None, '', 'SAMM'):
            continue
        code = product['MAT_CODE']
        evidence = f"PRODUCT_ID={product['PRODUCT_ID']!r}; MAT_CODE={code!r}"
        def finding(name, reason, **values):
            v.add(15, values.pop('severity', 'ERROR'), name, reason, src='PRODUCT_MST',
                  sheet='PRODUCT_MST', rn=number, sku=code or '', related=evidence, **values)
        try:
            expiry = expiry_date(product['EXPIRE_DATE'])
            if expiry is not None and expiry < today:
                continue
            active = []
            for price in prices[product['PRODUCT_ID']]:
                if price['PRICE_ID'] in (None, ''):
                    continue
                start = calendar_date(price['EFFECTIVE_DATE'])
                end = expiry_date(price['EXPIRE_DATE'])
                if start is None:
                    raise ValueError('PRICE_MST.EFFECTIVE_DATE is missing')
                if start <= today and (end is None or end >= today):
                    active.append(price)
        except (ValueError, TypeError, OverflowError) as error:
            finding('MAT_CODE_DATE_INVALID', 'วันเวลาของสินค้า/ราคาไม่ครบหรือรูปแบบไม่ถูกต้อง จึงยังเลือก MAT_CODE เพื่อตรวจไม่ได้',
                    severity='REVIEW', expected='ISO date/datetime', val=str(error))
            continue
        if not active:
            continue
        v.coverage['15_eligible_product_rows'] += 1
        if code in (None, ''):
            finding('MAT_CODE_EMPTY', 'PRODUCT_MST ที่เข้าเงื่อนไขมี MAT_CODE ว่าง')
            continue
        matches = variants[code]
        if not matches:
            if all_variants[code]:
                v.coverage['15_excluded_po_products'] += 1
                continue
            finding('MAT_CODE_VARIANT_MISSING', 'ไม่พบ MAT_CODE ที่เข้าเงื่อนไขใน Product Variants.sku',
                    expected='MAT_CODE ต้องมีใน Product_Variants',
                    val=repr(sorted({str(price['PRICE_ID']) for price in active})))
            continue
        # The approved rule checks price_group only when SKU has several rows.
        if len(matches) == 1:
            continue
        if code not in group_cache:
            groups = set()
            uncertain = False
            for variant in matches:
                pairs, state = parse_pairs(variant['cids'], variant['vals'])
                if state not in (None, 'BOTH_EMPTY'):
                    uncertain = True
                    v.finding(15, 'MAT_CODE_VARIANT_CHAR_INVALID', variant,
                              reason='จับคู่ specCharacteristics กับ value ตาม index ไม่ได้: '+state)
                    continue
                groups.update(value for name, value in pairs if char_key(name) == 'pricegroup')
            group_cache[code] = groups, uncertain
        groups, uncertain = group_cache[code]
        for price_group in sorted({price['PRICE_GROUP'] for price in active}, key=lambda value: (value is not None, str(value))):
            v.coverage['15_checked_price_groups'] += 1
            if price_group in (None, ''):
                finding('MAT_CODE_PRICE_GROUP_EMPTY', 'ราคาที่มีผลอยู่มี PRICE_GROUP ว่าง จึงเทียบกับ Variant ไม่ได้')
            elif price_group not in groups:
                finding('MAT_CODE_PRICE_GROUP_MISSING', 'พบ Variant หลายแถว แต่ไม่มี price_group ตรงกับ PRICE_GROUP ของราคาที่มีผลอยู่',
                        severity='REVIEW' if uncertain else 'ERROR', val=price_group,
                        expected=f'Variant price_group = {price_group!r}')
