# -*- coding: utf-8 -*-
"""
Auto PO Grouper — จัดกลุ่ม PO จาก PRODUCT_MST (DB) โดยใช้ category_new (DB)

โหลดข้อมูลจาก DB:
  - category_new  ->  CAT_MAP / CAT_NODES
  - PRODUCT_MST   ->  DataFrame สำหรับ group_po()

Output:
  - บันทึก xlsx ลง export/<timestamp>/PO_GROUPED_<timestamp>.xlsx
  - Insert ชีท PO_Summary ลง DB table po_group (สร้างอัตโนมัติถ้ายังไม่มี)
"""

import os
import re
import sys
import json
import time
import hashlib
import unicodedata
import concurrent.futures as cf
from collections import Counter
from datetime import datetime
from pathlib import Path

import pandas as pd
import numpy as np
import requests

pd.set_option("display.max_colwidth", 70)
pd.set_option("display.width", 220)

# ---------------------------------------------------------------------------
# Path setup — เหมือน export_template_mapping.py
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
PACKAGE_DIR  = Path(__file__).resolve().parent
for _p in (str(PROJECT_ROOT), str(PACKAGE_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from translation import connect_database, load_database_config, load_env

BASE_DIR = PACKAGE_DIR

# ---------------------------------------------------------------------------
# 1. CONFIG
# ---------------------------------------------------------------------------
COL = {
    "product_id": "PRODUCT_ID", "mat_code": "MAT_CODE", "brand": "BRAND", "grade": "GRADE",
    "color": "COLOR", "capacity": "CAPACITY", "ptype": "PRODUCT_TYPE", "psubtype": "PRODUCT_SUBTYPE",
    "mch": "VALUATION_CLASS", "active": "ACTIVE_FLAG", "eff": "EFFECTIVE_DATE", "company": "COMPANY",
    "face_value": "FACE_VALUE", "mat_type": "MAT_TYPE", "category": "CATEGORY",
}

NAME_COLS = ["MAIN_MODEL", "MODEL", "COMMERCIAL_NAME", "SAP_DESCRIPTION"]

PO_STRATEGY = {
    "DEVICE": "series", "GADGET": "series", "GADGET/IOT": "series", "IOT": "series",
    "ACCESSORY": "brand_cat", "PREMIUM": "brand_cat", "FBB": "brand_cat", "OTHER": "brand_cat",
    "SIM": "category", "ESIM": "category", "SOFTSIM": "category",
    "SERVICE": "category", "TOPUP": "category", "CARD": "category",
}
DEFAULT_STRATEGY = "brand_cat"

FILTER_ACTIVE_ONLY   = False
FILTER_PRODUCT_TYPE  = None
EXCLUDE_PRODUCT_TYPES = {"FBB"}

NOISE = {"3G", "4G", "5G", "LTE", "WIFI", "WI-FI", "NR", "DUAL", "SIM", "DS",
         "TH", "THAI", "CTH", "NEW", "SET", "N/A", "NAN"}

FLAG_TOKENS    = {"BUNDLE": "BUNDLE_SIM", "LOCK": "LOCKED", "CDM": "CDM", "CDMSL": "CDM",
                  "CDMT": "CDM", "BS": "BUNDLE_SIM", "DEMO": "DEMO", "NT": "NT", "EE": "EE"}
EDITION_TOKENS = {"EDITION", "THOMBROWNE", "LEICA", "LIMITED", "COLLECTION", "ANNIVERSARY"}

TIER_SEED = {"PRO", "MAX", "PLUS", "MINI", "ULTRA", "LITE", "FE", "NEO", "SE", "AIR", "EDGE",
             "PRO+", "PLUS+", "PROMAX", "E", "XL", "GT", "TURBO", "ACE", "POWER", "PRIME",
             "FLIP", "FOLD", "YOUTH", "ACTIVE", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"}

NO_DIGIT_SERIES = {
    ("APPLE", "IPHONE X"), ("APPLE", "IPHONE XR"), ("APPLE", "IPHONE XS"), ("APPLE", "IPHONE XS MAX"),
    ("APPLE", "IPHONE AIR"), ("APPLE", "IPAD"), ("APPLE", "IPAD AIR"), ("APPLE", "IPAD PRO"), ("APPLE", "IPAD MINI"),
    ("ONEPLUS", "NORD"), ("ONEPLUS", "NORD CE"), ("REALME", "GT"), ("REALME", "GT MASTER"), ("REALME", "PAD"),
    ("HUAWEI", "MATEPAD"), ("HUAWEI", "MATE XT"), ("SAMSUNG", "GALAXY XCOVER"), ("XIAOMI", "REDMI PAD"),
}

NORMAL_GRADES = {"", "NORMAL", "N/A", "-"}
MERGE_ALL_NON_NORMAL_TO_GD = True

TIER_ORDER = {"Standard": 0, "E": 1, "Lite": 2, "SE": 3, "Mini": 4, "Neo": 5, "FE": 6, "Air": 7,
              "Plus": 8, "Pro": 9, "Pro+": 10, "Pro Max": 11, "Max": 12, "Ultra": 13}
BRAND_CASE = {"APPLE": "Apple", "OPPO": "Oppo", "SONY": "Sony", "SAMSUNG": "Samsung", "XIAOMI": "Xiaomi",
              "VIVO": "Vivo", "HUAWEI": "Huawei", "REALME": "Realme", "NOKIA": "Nokia", "HONOR": "Honor",
              "MOTOROLA": "Motorola", "INFINIX": "Infinix", "TECNO": "Tecno", "ASUS": "Asus", "GOOGLE": "Google",
              "ONEPLUS": "OnePlus", "NOTHING": "Nothing", "AIS GROUP": "AIS Group", "TP-LINK": "TP-Link"}
WORD_CASE = {"IPHONE": "iPhone", "IPAD": "iPad", "IMAC": "iMac", "XR": "XR", "XS": "XS", "SE": "SE", "GT": "GT"}

SPLIT_TRAILING_LETTER  = True
SERIES_LETTER_SUFFIX   = {"A", "C", "D", "E", "F", "G", "I", "P", "R", "S", "T", "U", "V", "X", "Z"}
STRIP_MODEL_SUFFIX     = True
MODEL_SUFFIX_STRIP     = {"5G", "4G", "3G", "2G", "LTE", "NR", "EE", "CORP", "DS"}
DROP_SERIES_WORDS      = {"GALAXY"}

SERIES_ALIAS = [
    ("HUAWEI", r"5586|58692|E5586",                                    "5586"),
    ("HONOR",  r"\bPAD ?8\b|PAD8|\bPAD ?X8B\b|PADX8B|\bX8A\b|\bX9A\b", "PAD 8"),
]

UNBRANDED_LABEL    = "(NO BRAND)"
UNBRANDED_IN_PO_ID = False
UNBRANDED_ALIASES  = {"", "NO BRAND", "NO BRAND / OTHER", "NOBRAND", "NO_BRAND",
                      "NONE", "N/A", "-", "OTHER", "OTHERS", "UNBRANDED"}
MIN_LEARN_SUPPORT  = 3

# ---------------------------------------------------------------------------
# 2. CATEGORY LOADER — column names ตรงกับ DB (category_new)
# ---------------------------------------------------------------------------
CAT_COLS = {
    "id":        "Category ID",
    "name":      "Category Name",
    "parent":    "Parent Category",
    "add_brand": "add_to_brand",
    "mch":       "group_mch_ids",
}
ROOT_PARENT_TOKENS = {"root", "", "nan", "none"}
DROP_ROOT_PREFIX   = "material_category_hierarchy"
GROUP_PATH_MODE    = "l1_leaf"   # "l1_leaf" | "full_chain"


def _norm_code(x):
    s = str(x).strip()
    if s in ("", "nan", "None"): return ""
    m = re.match(r"^(\d+)(?:\.0+)?$", s)
    if m: return m.group(1)
    try:    return str(int(float(s)))
    except Exception: return re.sub(r"\D", "", s)


def _split_refs(v):
    if v is None: return []
    s = str(v).strip()
    if s in ("", "nan", "None") or "ไม่มี" in s: return []
    return [c for c in (_norm_code(t) for t in re.split(r"[,\s;|]+", s)) if c]


def load_category_from_db(cursor) -> tuple[dict, dict]:
    """โหลด category_new จาก DB -> (CAT_MAP, CAT_NODES)"""
    cursor.execute("SELECT * FROM `category_new`")
    rows = cursor.fetchall()
    if not rows:
        return {}, {}

    # normalize column names
    c_id     = CAT_COLS["id"]
    c_name   = CAT_COLS["name"]
    c_parent = CAT_COLS["parent"]
    c_brand  = CAT_COLS["add_brand"]
    c_mch    = CAT_COLS["mch"]

    by_id: dict[str, dict] = {str(r[c_id]).strip(): r for r in rows if r.get(c_id)}

    def chain_ids(r):
        chain, cur_r, seen, guard = [], r, set(), 0
        while cur_r is not None and guard < 15:
            cid = str(cur_r[c_id]).strip()
            if cid in seen: break
            seen.add(cid); chain.append(cid); guard += 1
            p = str(cur_r[c_parent] or "").strip()
            if p.lower() in ROOT_PARENT_TOKENS: break
            cur_r = by_id.get(p)
        return list(reversed(chain))

    cat_map: dict[str, dict] = {}
    nodes:   dict[str, dict] = {}

    for r in rows:
        cid = str(r[c_id] or "").strip()
        if not cid: continue
        full = [x for x in chain_ids(r) if not x.startswith(DROP_ROOT_PREFIX)]
        if not full: continue
        l1, leaf = full[0], full[-1]
        gpath = full if GROUP_PATH_MODE == "full_chain" else ([l1, leaf] if l1 != leaf else [leaf])
        names = [str(by_id[x][c_name]).strip() if x in by_id else x for x in full]
        node = {
            "new_id":    cid,
            "new_name":  str(r.get(c_name) or "").strip(),
            "add_brand": str(r.get(c_brand) or "").strip().upper() == "Y",
            "l1": (names + ["", "", ""])[0],
            "l2": (names + ["", "", ""])[1],
            "l3": (names + ["", "", ""])[2],
            "chain":     full,
            "path":      " > ".join(gpath),
            "full_path": " > ".join(full),
            "codes":     _split_refs(r.get(c_mch)),
        }
        nodes[cid] = node
        for code in node["codes"]:
            if code in cat_map:
                print(f"  !! รหัส {code} อยู่ทั้ง {cat_map[code]['new_id']} และ {cid} -> ใช้ตัวหลัง")
            cat_map[code] = node

    return cat_map, nodes


# ---------------------------------------------------------------------------
# 3. AI (Typhoon) — optional; ข้ามถ้าไม่มี API key
# ---------------------------------------------------------------------------
def _load_ai_config() -> None:
    """อ่าน AI config จาก .env (load_env ต้องถูกเรียกก่อนแล้ว)"""
    global USE_AI_CATEGORY, USE_AI_SERIES
    global TYPHOON_API_KEY, TYPHOON_MODEL, TYPHOON_BASE_URL
    global AI_BATCH_SIZE, AI_WORKERS, AI_MAX_RETRY, AI_MIN_CONF
    global AI_SCOPE, AI_CACHE_PATH, AI_SERIES_MIN_CONF, AI_SERIES_CACHE_PATH

    TYPHOON_API_KEY      = os.environ.get("TYPHOON_API_KEY", "")
    TYPHOON_MODEL        = os.environ.get("TYPHOON_MODEL", "typhoon-v2.5-30b-a3b-instruct")
    TYPHOON_BASE_URL     = os.environ.get("TYPHOON_BASE_URL", "https://api.opentyphoon.ai/v1")
    AI_BATCH_SIZE        = int(os.environ.get("AI_BATCH_SIZE", "20"))
    AI_WORKERS           = int(os.environ.get("AI_WORKERS", "4"))
    AI_MAX_RETRY         = int(os.environ.get("AI_MAX_RETRY", "3"))
    AI_MIN_CONF          = float(os.environ.get("AI_MIN_CONF", "0.50"))
    AI_SCOPE             = os.environ.get("AI_SCOPE", "unmatched")
    AI_SERIES_MIN_CONF   = float(os.environ.get("AI_SERIES_MIN_CONF", "0.65"))

    cache_path        = os.environ.get("AI_CACHE_PATH", "typhoon_cat_cache.json")
    series_cache_path = os.environ.get("AI_SERIES_CACHE_PATH", "typhoon_series_cache.json")
    AI_CACHE_PATH        = str(PROJECT_ROOT / cache_path) if not Path(cache_path).is_absolute() else cache_path
    AI_SERIES_CACHE_PATH = str(PROJECT_ROOT / series_cache_path) if not Path(series_cache_path).is_absolute() else series_cache_path

    if not TYPHOON_API_KEY:
        USE_AI_CATEGORY = False
        USE_AI_SERIES   = False


USE_AI_CATEGORY      = True
USE_AI_SERIES        = True
load_env(BASE_DIR / ".env")
_load_ai_config()

AI_SYSTEM = (
    "คุณคือผู้เชี่ยวชาญจัดหมวดหมู่สินค้าโทรคมนาคม/ไอที ของ AIS\n"
    "หน้าที่: อ่านข้อมูลสินค้าแต่ละรายการ แล้วเลือก category ที่ถูกต้องที่สุด "
    "จาก 'รายการ category ที่อนุญาต' เท่านั้น ห้ามสร้าง category ใหม่เอง\n"
    "ยึดตัวสินค้าจริงจากชื่อสินค้าเป็นหลัก; รหัส SAP เดิม เป็นแค่ข้อมูลประกอบ\n"
    "ตอบเป็น JSON array อย่างเดียว ห้ามมีข้อความอื่นหรือ markdown fence"
)
AI_SERIES_SYSTEM = (
    "คุณคือผู้เชี่ยวชาญรุ่นสินค้ามือถือ/แท็บเล็ต/โน้ตบุ๊ก/อุปกรณ์เครือข่าย\n"
    "หน้าที่: อ่านชื่อสินค้าที่รหัสรุ่นอาจเพี้ยน/ติดกัน แล้วบอก 'ชื่อรุ่นหลัก (series)' ที่ควรใช้จัดกลุ่ม PO\n"
    "กฎ:\n"
    "- ยึดรุ่นสินค้าจริงจากความรู้ของคุณ (เช่น 'HW E5586-926' คือ Huawei รุ่น 5586)\n"
    "- ตัดสเปท/เครือข่าย/ช่องทาง (5G, 4G, RAM/ROM, EE, CORP, generation) ทิ้ง เหลือรหัสรุ่นหลัก\n"
    "- ถ้าตรงกับรุ่นใน 'series ที่มีอยู่แล้ว' ให้ตอบชื่อนั้นเป๊ะ ๆ เพื่อให้รวมกลุ่มกัน\n"
    "- series ต้องสั้น (ชื่อรุ่น) ไม่ใส่ยี่ห้อซ้ำ ไม่ใส่ความจุ/สี\n"
    "ตอบเป็น JSON array อย่างเดียว ห้ามมีข้อความอื่นหรือ markdown"
)


def _build_ai_candidates(nodes: dict) -> list[dict]:
    cands = list(nodes.values())
    parents = set()
    for n in cands:
        parents.update(n["chain"][:-1])
    leafish = [n for n in cands if n["new_id"] not in parents] or cands
    return sorted(leafish, key=lambda n: n["full_path"])


def _cand_block(ai_candidates: list[dict]) -> str:
    return "\n".join(
        f'- {n["new_id"]} | {n["new_name"]} | path: {n["full_path"]}' for n in ai_candidates
    )


def _build_prompt(batch: list[dict], ai_candidates: list[dict]) -> str:
    items = [{"i": i, "ชื่อสินค้า": u["name"], "แบรนด์": u["brand"],
              "type": u["ptype"], "subtype": u["psubtype"], "รหัส_sap_เดิม": u["mch"]}
             for i, u in enumerate(batch)]
    return (
        f"รายการ category ที่อนุญาต (เลือกได้เฉพาะ cat_id เหล่านี้):\n{_cand_block(ai_candidates)}\n\n"
        f"สินค้า:\n{json.dumps(items, ensure_ascii=False, indent=1)}\n\n"
        'ตอบกลับ JSON array รูปแบบ: [{"i":0,"cat_id":"handset-pc_mg50012","conf":0.95,"why":"เหตุผลสั้นๆ"}, ...]\n'
        "ต้องมีครบทุก i และ cat_id ต้องอยู่ในรายการที่อนุญาตเท่านั้น"
    )


def _typhoon_chat(messages: list[dict], model: str | None = None) -> str:
    r = requests.post(
        f"{TYPHOON_BASE_URL}/chat/completions",
        headers={"Authorization": f"Bearer {TYPHOON_API_KEY}", "Content-Type": "application/json"},
        json={"model": model or TYPHOON_MODEL, "messages": messages,
              "temperature": 0.0, "top_p": 0.95, "max_tokens": 4000},
        timeout=180,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def _parse_json_array(txt: str):
    t = re.sub(r"^```(?:json)?|```$", "", txt.strip(), flags=re.M).strip()
    m = re.search(r"\[.*\]", t, re.S)
    return json.loads(m.group(0) if m else t)


def _sig_key(u: dict) -> str:
    return hashlib.md5(
        "|".join([u["mch"], u["brand"], u["ptype"], u["psubtype"], u["name"]]).upper().encode()
    ).hexdigest()[:16]


def _classify_batch(args) -> dict[int, tuple]:
    batch, ai_candidates, ai_by_id, ai_by_name = args
    for attempt in range(AI_MAX_RETRY):
        try:
            txt = _typhoon_chat([{"role": "system", "content": AI_SYSTEM},
                                 {"role": "user",   "content": _build_prompt(batch, ai_candidates)}])
            out: dict[int, tuple] = {}
            for o in _parse_json_array(txt):
                i = int(o.get("i", -1))
                if not (0 <= i < len(batch)): continue
                node = ai_by_id.get(str(o.get("cat_id", "")).strip()) or \
                       ai_by_name.get(str(o.get("cat_name", "")).strip())
                if node is None: continue
                try:    conf = float(o.get("conf", 0.5))
                except Exception: conf = 0.5
                out[i] = (node, conf, str(o.get("why", ""))[:120])
            if out: return out
        except requests.exceptions.HTTPError as e:
            is_rate_limit = e.response is not None and e.response.status_code == 429
            wait = (30 if is_rate_limit else 2) * (attempt + 1)
            if attempt == AI_MAX_RETRY - 1:
                print(f"  batch fail: {type(e).__name__}: {str(e)[:90]}")
            else:
                print(f"  {'rate limit' if is_rate_limit else 'http error'} — retry {attempt+1}/{AI_MAX_RETRY} (wait {wait}s)")
            time.sleep(wait)
        except Exception as e:
            if attempt == AI_MAX_RETRY - 1:
                print(f"  batch fail: {type(e).__name__}: {str(e)[:90]}")
            time.sleep(2 * (attempt + 1))
    return {}


def ai_classify(units: list[dict], ai_candidates: list[dict], ai_nodes: dict) -> dict:
    ai_by_id   = {n["new_id"]:   n for n in ai_candidates}
    ai_by_name = {n["new_name"]: n for n in ai_candidates}
    cache: dict = {}
    if os.path.exists(AI_CACHE_PATH):
        try: cache = json.load(open(AI_CACHE_PATH, encoding="utf-8"))
        except Exception: cache = {}
    todo = [u for u in units if _sig_key(u) not in cache]
    print(f"AI: {len(units):,} | cache hit {len(units)-len(todo):,} | ยิง {len(todo):,}")
    batches = [(todo[i:i+AI_BATCH_SIZE], ai_candidates, ai_by_id, ai_by_name)
               for i in range(0, len(todo), AI_BATCH_SIZE)]
    ai_batch_delay = float(os.environ.get("AI_BATCH_DELAY", "2"))
    done = 0
    with cf.ThreadPoolExecutor(AI_WORKERS) as ex:
        for b_args, res in zip(batches, ex.map(_classify_batch, batches)):
            batch = b_args[0]
            for i, u in enumerate(batch):
                if i in res:
                    node, conf, why = res[i]
                    cache[_sig_key(u)] = {"cat_id": node["new_id"], "cat_name": node["new_name"],
                                          "path": node["path"], "conf": conf, "why": why}
            done += 1
            if done % 10 == 0 or done == len(batches):
                print(f"   {done}/{len(batches)} batches | cached {len(cache):,}")
                json.dump(cache, open(AI_CACHE_PATH, "w", encoding="utf-8"), ensure_ascii=False)
            if done < len(batches) and ai_batch_delay > 0:
                time.sleep(ai_batch_delay)
    json.dump(cache, open(AI_CACHE_PATH, "w", encoding="utf-8"), ensure_ascii=False)
    return cache


def _series_sig(u: dict) -> str:
    return hashlib.md5(
        ("S|" + u["brand"] + "|" + u["ptype"] + "|" + u["name"] + "|" + u["series"]).upper().encode()
    ).hexdigest()[:16]


def _build_series_prompt(batch: list[dict], existing: list[tuple]) -> str:
    ex: dict[str, list] = {}
    for br, sr in existing:
        ex.setdefault(br, [])
        if sr and sr not in ex[br]: ex[br].append(sr)
    ex_txt = "\n".join(f'  {b}: {", ".join(v[:40])}' for b, v in ex.items() if v) or "  (ไม่มี)"
    items = [{"i": i, "brand": u["brand"], "name": u["name"], "series_now": u["series"]}
             for i, u in enumerate(batch)]
    return (
        f"series ที่มีอยู่แล้ว (แยกตามยี่ห้อ) — ถ้าตรงรุ่นให้ใช้ชื่อเดิมนี้:\n{ex_txt}\n\n"
        f"สินค้าที่ต้องระบุ series:\n{json.dumps(items, ensure_ascii=False, indent=1)}\n\n"
        'ตอบ JSON array: [{"i":0,"series":"5586","conf":0.9,"why":"เหตุผลสั้นๆ"}, ...] ครบทุก i'
    )


def _classify_series_batch(args) -> dict[int, tuple]:
    batch, existing = args
    for attempt in range(AI_MAX_RETRY):
        try:
            txt = _typhoon_chat([{"role": "system", "content": AI_SERIES_SYSTEM},
                                 {"role": "user",   "content": _build_series_prompt(batch, existing)}])
            out: dict[int, tuple] = {}
            for o in _parse_json_array(txt):
                i = int(o.get("i", -1))
                if not (0 <= i < len(batch)): continue
                sr = str(o.get("series", "")).strip()
                if not sr: continue
                try:    conf = float(o.get("conf", 0.5))
                except Exception: conf = 0.5
                out[i] = (sr, conf, str(o.get("why", ""))[:120])
            if out: return out
        except Exception as e:
            if attempt == AI_MAX_RETRY - 1:
                print(f"  series batch fail: {type(e).__name__}: {str(e)[:80]}")
            time.sleep(2 * (attempt + 1))
    return {}


def ai_series_group(units: list[dict], existing: list[tuple]) -> dict:
    cache: dict = {}
    if os.path.exists(AI_SERIES_CACHE_PATH):
        try: cache = json.load(open(AI_SERIES_CACHE_PATH, encoding="utf-8"))
        except Exception: cache = {}
    todo = [u for u in units if _series_sig(u) not in cache]
    print(f"AI series: {len(units):,} | cache hit {len(units)-len(todo):,} | ยิง {len(todo):,}")
    batches = [(todo[i:i+AI_BATCH_SIZE], existing) for i in range(0, len(todo), AI_BATCH_SIZE)]
    with cf.ThreadPoolExecutor(AI_WORKERS) as ex:
        for (b, _), res in zip(batches, ex.map(_classify_series_batch, batches)):
            for i, u in enumerate(b):
                if i in res:
                    sr, conf, why = res[i]
                    cache[_series_sig(u)] = {"series": sr, "conf": conf, "why": why}
    json.dump(cache, open(AI_SERIES_CACHE_PATH, "w", encoding="utf-8"), ensure_ascii=False)
    return cache


# ---------------------------------------------------------------------------
# 4. Parser helpers
# ---------------------------------------------------------------------------
def clean(x):
    if x is None: return ""
    s = str(x)
    if s.strip().lower() in ("nan", "none", "null", "n/a", "-", ""): return ""
    return unicodedata.normalize("NFKC", s).strip()


def pick_name(row: dict) -> tuple[str, str]:
    for c in NAME_COLS:
        v = clean(row.get(c))
        if v: return v, c
    return "", "(none)"


def tokenize(name: str, capacity: str = "", color: str = "") -> list[str]:
    s = clean(name).upper()
    s = re.sub(r"[_/\\-]", " ", s)
    s = re.sub(r"\b\d+(GB|TB|MB)\b", " ", s)
    s = re.sub(r"\b(PRO|AIR|MINI)(\d+)\b", r"\1 \2", s)
    for w in clean(capacity).upper().split(): s = s.replace(w, " ")
    for w in clean(color).upper().split():
        if len(w) > 2: s = re.sub(rf"\b{re.escape(w)}\b", " ", s)
    return [t for t in (x.strip("()[]., ") for x in s.split()) if t and t not in NOISE]


def strip_flags(toks: list[str]) -> tuple[list[str], list[str], list[str]]:
    flags, eds, keep = [], [], []
    for t in toks:
        if t in FLAG_TOKENS:       flags.append(FLAG_TOKENS[t])
        elif t in EDITION_TOKENS:  eds.append(t.title())
        else:                      keep.append(t)
    return keep, sorted(set(flags)), sorted(set(eds))


def learn_tier_vocab(tok_list: list, brand_list: list) -> tuple[set, set]:
    seen = set()
    for b, toks in zip(brand_list, tok_list):
        i = next((k for k, t in enumerate(toks) if re.search(r"\d", t)), None)
        if i is None: continue
        stem = " ".join(toks[:i + 1])
        for t in toks[i + 1:]:
            if re.fullmatch(r"[A-Z+]{1,10}", t): seen.add((b, t, stem))
    per = Counter((b, t) for (b, t, _) in seen)
    learned = {t for (b, t), n in per.items() if n >= MIN_LEARN_SUPPORT}
    return TIER_SEED | learned, learned


def strip_model_suffix(tok: str) -> str:
    if not STRIP_MODEL_SUFFIX or not re.search(r"\d", tok): return tok
    m = re.match(r"^([A-Z]{2,}\d+)G\d+", tok)
    if m: return m.group(1)
    t, changed = tok, True
    while changed and re.search(r"\d", t):
        changed = False
        m = re.search(r"(AD[A-Z0-9]*)$", t)
        if m and re.search(r"\d", t[:m.start()]):
            t = t[:m.start()]; changed = True; continue
        for suf in sorted(MODEL_SUFFIX_STRIP, key=len, reverse=True):
            if t.endswith(suf) and len(t) > len(suf) and re.search(r"\d", t[:-len(suf)]):
                t = t[:-len(suf)]; changed = True; break
    return t or tok


def _finalize_series(series: list[str]) -> list[str]:
    series = [strip_model_suffix(t) for t in series]
    kept   = [t for t in series if t not in DROP_SERIES_WORDS]
    return kept or series


def parse_row(toks: list[str], vocab: set, brand: str) -> tuple[list[str], list[str], str]:
    if not toks: return [], [], "LOW"
    joined = " ".join(toks)
    for b, s in sorted(NO_DIGIT_SERIES, key=lambda x: -len(x[1])):
        if b == brand and (joined == s or joined.startswith(s + " ")):
            rest = joined[len(s):].split()
            if all(t in vocab for t in rest): return s.split(), rest, "HIGH"
    i = next((k for k, t in enumerate(toks) if re.search(r"\d", t)), None)
    if i is not None:
        series, tier = list(toks[:i + 1]), list(toks[i + 1:])
        series = _finalize_series(series)
        if SPLIT_TRAILING_LETTER and series:
            m = re.fullmatch(r"(\d+)([A-Z])", series[-1])
            if m and m.group(2) in SERIES_LETTER_SUFFIX:
                series[-1] = m.group(1); tier = [m.group(2)] + tier
        unknown = [t for t in tier if t not in vocab]
        return series, tier, ("HIGH" if not unknown else "MEDIUM")
    tier: list[str] = []
    while len(toks) > 1 and toks[-1] in vocab: tier.insert(0, toks.pop())
    return toks, tier, ("MEDIUM" if tier else "LOW")


def prettify(toks: list[str]) -> str:
    out = []
    for w in toks:
        if w in WORD_CASE: out.append(WORD_CASE[w])
        elif re.fullmatch(r"[A-Z]*\d+[A-Z]*", w): out.append(w)
        else: out.append(w.title())
    return " ".join(out)


def pretty_tier(toks: list[str]) -> str:
    if not toks: return "Standard"
    s = " ".join(toks)
    fix = {"PRO MAX": "Pro Max", "PROMAX": "Pro Max", "PRO PLUS": "Pro+", "PRO+": "Pro+", "XS MAX": "Max"}
    return fix.get(s, " ".join(t if re.fullmatch(r"[IVX]+", t) else t.title() for t in toks))


def norm_grade(v) -> str:
    s = clean(v).upper()
    if s in NORMAL_GRADES: return "NORMAL"
    return "GD" if MERGE_ALL_NON_NORMAL_TO_GD else s


# ---------------------------------------------------------------------------
# 5. Core — group_po()
# ---------------------------------------------------------------------------
def _norm_brand(b: str) -> str:
    s = str(b).strip().upper()
    if s in UNBRANDED_ALIASES or s in ("", "NAN", "NONE", UNBRANDED_LABEL.upper()): return ""
    return s


def make_group(node: dict | None, brand: str) -> str:
    if not node: return ""
    g = node["path"]
    if node.get("add_brand"):
        b = _norm_brand(brand)
        if b: g = g + " > " + b
    return g


def apply_series_alias(brand: str, name: str, series: str) -> tuple[str, bool]:
    hay = (str(name) + " " + str(series)).upper()
    bu  = str(brand).upper()
    for rb, pat, canon in SERIES_ALIAS:
        if rb.upper() == bu and re.search(pat, hay):
            return canon, True
    return series, False


def group_po(df: pd.DataFrame, cat_map: dict, cat_nodes: dict) -> dict[str, pd.DataFrame]:
    d = df.copy()
    d.columns = [str(c).strip() for c in d.columns]
    if COL["product_id"] not in d.columns:
        raise ValueError(f"ขาด {COL['product_id']}")
    have = [c for c in NAME_COLS if c in d.columns]
    if not have:
        raise ValueError(f"ต้องมีคอลัมน์ชื่ออย่างน้อย 1: {NAME_COLS}")
    print("ชื่อรุ่นที่ใช้ได้:", have)

    n0 = len(d)
    gg = lambda k: d[COL[k]].map(clean) if COL[k] in d.columns else pd.Series([""] * len(d), index=d.index)
    if FILTER_ACTIVE_ONLY and COL["active"] in d.columns:
        d = d[gg("active").str.upper() == "Y"]
    if FILTER_PRODUCT_TYPE and COL["ptype"] in d.columns:
        d = d[gg("ptype").str.upper() == FILTER_PRODUCT_TYPE.upper()]
    if EXCLUDE_PRODUCT_TYPES and COL["ptype"] in d.columns:
        d = d[~gg("ptype").str.upper().isin({t.upper() for t in EXCLUDE_PRODUCT_TYPES})]
    if len(d) != n0:
        print(f"filter: {n0:,} -> {len(d):,}")
    d = d.reset_index(drop=True)
    gg = lambda k: d[COL[k]].map(clean) if COL[k] in d.columns else pd.Series([""] * len(d), index=d.index)

    picked = [pick_name(r) for r in d.to_dict("records")]
    d["_name"], d["_name_src"] = [p[0] for p in picked], [p[1] for p in picked]

    d["_brand_raw"] = gg("brand").str.upper()
    d["_brand"]     = d["_brand_raw"].map(lambda b: UNBRANDED_LABEL if b.strip() in UNBRANDED_ALIASES else b)
    d["_capacity"], d["_color"] = gg("capacity"), gg("color")
    d["_mat_code"], d["_eff"]   = gg("mat_code"), gg("eff")
    d["_ptype"]    = gg("ptype").str.upper().replace("", "(NO TYPE)")
    d["_psubtype"] = gg("psubtype").str.upper().replace("", "(NO SUBTYPE)")
    d["_mch"]      = gg("mch").map(_norm_code)
    d["_grade"]    = d[COL["grade"]].map(norm_grade) if COL["grade"] in d.columns else "NORMAL"
    d["_strategy"] = d["_ptype"].map(lambda t: PO_STRATEGY.get(t, DEFAULT_STRATEGY))

    # STEP 1: DIRECT match
    d["_node"]    = d["_mch"].map(lambda m: cat_map.get(m))
    d["_matched"] = d["_node"].map(lambda n: n is not None)
    print(f"DIRECT match: {int(d['_matched'].sum()):,} / {len(d):,}"
          f"  | AI: {int((~d['_matched']).sum()):,}")

    # STEP 2: AI
    d["_ai_conf"] = np.nan
    d["_ai_why"]  = ""
    unmatched_mask = ~d["_matched"]
    ai_cache: dict = {}

    if USE_AI_CATEGORY and cat_nodes and (AI_SCOPE == "all" or unmatched_mask.any()):
        ai_candidates = _build_ai_candidates(cat_nodes)
        scope_mask = unmatched_mask if AI_SCOPE != "all" else pd.Series(True, index=d.index)
        units, seen = [], set()
        for idx in d.index[scope_mask]:
            u = {"name": d.at[idx, "_name"] or "(ไม่มีชื่อ)", "brand": d.at[idx, "_brand"],
                 "ptype": d.at[idx, "_ptype"], "psubtype": d.at[idx, "_psubtype"], "mch": d.at[idx, "_mch"]}
            k = _sig_key(u)
            if k not in seen: seen.add(k); units.append(u)
        ai_cache = ai_classify(units, ai_candidates, cat_nodes)

        def _look(idx):
            u = {"name": d.at[idx, "_name"] or "(ไม่มีชื่อ)", "brand": d.at[idx, "_brand"],
                 "ptype": d.at[idx, "_ptype"], "psubtype": d.at[idx, "_psubtype"], "mch": d.at[idx, "_mch"]}
            return ai_cache.get(_sig_key(u))

        for idx in d.index[scope_mask]:
            g = _look(idx)
            if not g: continue
            conf = g.get("conf", 0.0) or 0.0
            d.at[idx, "_ai_conf"] = conf
            d.at[idx, "_ai_why"]  = g.get("why", "")
            if (not d.at[idx, "_matched"]) and conf >= AI_MIN_CONF:
                node = cat_nodes.get(g["cat_id"])
                if node is not None: d.at[idx, "_node"] = node

    # STEP 3: ประกอบ group
    def _src(row):
        if row["_matched"]:       return "DIRECT"
        if row["_node"] is not None: return "AI"
        return "UNMATCHED"

    d["_group_src"] = d.apply(_src, axis=1)
    d["_new_id"]    = d["_node"].map(lambda n: n["new_id"]    if n else "")
    d["_new_name"]  = d["_node"].map(lambda n: n["new_name"]  if n else "")
    d["_add_brand"] = d["_node"].map(lambda n: "Y" if (n and n["add_brand"]) else ("N" if n else ""))
    d["_cat_path"]  = d["_node"].map(lambda n: n["path"]      if n else "")
    d["_full_path"] = d["_node"].map(lambda n: n["full_path"] if n else "")
    d["_cat_l1"]    = d["_node"].map(lambda n: n.get("l1", "") if n else "")
    d["_cat_l2"]    = d["_node"].map(lambda n: n.get("l2", "") if n else "")
    d["_cat_l3"]    = d["_node"].map(lambda n: n.get("l3", "") if n else "")
    d["_new_group"] = [make_group(n, br) for n, br in zip(d["_node"], d["_brand_raw"])]

    d["_cat_key"] = np.where(d["_new_name"] != "", d["_new_name"],
                    np.where(d["_psubtype"] != "(NO SUBTYPE)", d["_psubtype"], "MCH " + d["_mch"]))

    # series/tier
    toks = [tokenize(n, c, cl) for n, c, cl in zip(d["_name"], d["_capacity"], d["_color"])]
    stf  = [strip_flags(t) for t in toks]
    d["_toks"], d["_flags"], d["_edition"] = [x[0] for x in stf], [", ".join(x[1]) for x in stf], [", ".join(x[2]) for x in stf]

    is_ser = d["_strategy"] == "series"
    vocab, learned = learn_tier_vocab([t for t, s in zip(d["_toks"], is_ser) if s],
                                      [b for b, s in zip(d["_brand"], is_ser) if s])
    series_list, model_list, conf_list = [], [], []
    for tk, strat, br in zip(d["_toks"], d["_strategy"], d["_brand"]):
        if strat != "series":
            series_list.append(""); model_list.append("Standard"); conf_list.append("N/A"); continue
        s, t, c = parse_row(list(tk), vocab, br)
        series_list.append(prettify(s)); model_list.append(pretty_tier(t)); conf_list.append(c)
    d["_series"], d["_model"], d["_conf"] = series_list, model_list, conf_list

    d["_series_src"] = "parse"
    for idx in d.index[is_ser]:
        new, hit = apply_series_alias(d.at[idx, "_brand"], d.at[idx, "_name"], d.at[idx, "_series"])
        if hit: d.at[idx, "_series"] = new; d.at[idx, "_series_src"] = "alias"

    if USE_AI_SERIES:
        uncertain = is_ser & (d["_series_src"] == "parse") & (d["_conf"] != "HIGH")
        if uncertain.any():
            existing = sorted(set(d.loc[is_ser & (d["_conf"] == "HIGH"), ["_brand", "_series"]]
                                  .apply(lambda r: (r["_brand"], r["_series"]), axis=1)))
            sunits, sseen = [], set()
            for idx in d.index[uncertain]:
                u = {"brand": d.at[idx, "_brand"], "name": d.at[idx, "_name"] or "(ไม่มีชื่อ)",
                     "series": d.at[idx, "_series"], "ptype": d.at[idx, "_ptype"]}
                k = _series_sig(u)
                if k not in sseen: sseen.add(k); sunits.append(u)
            series_ai_cache = ai_series_group(sunits, existing)
            for idx in d.index[uncertain]:
                u = {"brand": d.at[idx, "_brand"], "name": d.at[idx, "_name"] or "(ไม่มีชื่อ)",
                     "series": d.at[idx, "_series"], "ptype": d.at[idx, "_ptype"]}
                g = series_ai_cache.get(_series_sig(u))
                if g and g.get("series") and (g.get("conf", 0) or 0) >= AI_SERIES_MIN_CONF:
                    d.at[idx, "_series"] = g["series"]; d.at[idx, "_series_src"] = "ai"
                    d.at[idx, "_ai_why"] = (d.at[idx, "_ai_why"] or g.get("why", ""))

    d["_network"] = [(re.search(r"\b(3G|4G|5G)\b", clean(n).upper()).group(1)
                      if re.search(r"\b(3G|4G|5G)\b", clean(n).upper()) else "N/A") for n in d["_name"]]

    # ประกอบ PO_ID
    po_id_list, po_key_list = [], []
    for br, sr, gr, strat, ck, tp in zip(d["_brand"], d["_series"], d["_grade"],
                                          d["_strategy"], d["_cat_key"], d["_ptype"]):
        nobrand = (br == UNBRANDED_LABEL) and not UNBRANDED_IN_PO_ID
        bp  = "" if nobrand else BRAND_CASE.get(br, br.title())
        j   = lambda *xs: " ".join(x for x in xs if x).strip()
        if strat == "series" and sr:
            key  = sr if (not nobrand and sr.upper().startswith(br.split()[0])) else j(bp, sr)
            name = key + "_SERIES"
        elif strat == "series":
            key  = j(bp, ck, "(UNPARSED)"); name = key
        elif strat == "brand_cat":
            key  = j(bp, ck); name = key
        else:
            key  = j(tp, ck); name = key
        if gr != "NORMAL": name += "_" + gr
        po_key_list.append(key)
        po_id_list.append(re.sub(r"[^A-Z0-9]+", "_", name.upper()).strip("_"))
    d["_po_id"], d["_po_key"] = po_id_list, po_key_list

    join = lambda s: ", ".join(dict.fromkeys(x for x in map(str, s) if x not in ("", "nan")))
    ids  = lambda s: ",".join(sorted(map(str, s)))

    summary = (
        d.groupby(["_po_id", "_new_group", "_ptype", "_strategy", "_brand", "_po_key", "_grade"], as_index=False)
        .agg(
            new_group=("_new_group", join), group_source=("_group_src", join),
            add_to_brand=("_add_brand", join), new_cat_id=("_new_id", join),
            new_cat_name=("_new_name", join), cat_path=("_cat_path", join),
            full_path=("_full_path", join), mch=("_mch", join),
            models=("_model", lambda s: ", ".join(sorted(set(s), key=lambda x: TIER_ORDER.get(x, 99)))),
            model_count=("_model", "nunique"), names=("_name", join), name_source=("_name_src", join),
            subtypes=("_psubtype", join), networks=("_network", join), capacities=("_capacity", join),
            colors=("_color", join), flags=("_flags", join), edition=("_edition", join),
            variant_count=(COL["product_id"], "count"), product_ids=(COL["product_id"], ids),
            mat_codes=("_mat_code", join),
            valid_from=("_eff", lambda s: min([x for x in s if x], default="")),
            confidence=("_conf", lambda s: "N/A" if set(s) == {"N/A"} else
                        ("HIGH" if set(s) <= {"HIGH"} else ("LOW" if "LOW" in set(s) else "MEDIUM"))),
        )
        .rename(columns={
            "_po_id": "PO_ID", "_new_group": "NEW_GROUP", "_ptype": "PRODUCT_TYPE",
            "_strategy": "STRATEGY", "_brand": "BRAND", "_po_key": "PO_KEY", "_grade": "GRADE",
        })
        .drop(columns=["new_group"])
        .sort_values(["PRODUCT_TYPE", "BRAND", "PO_KEY", "GRADE"])
    )
    summary.insert(0, "No", range(1, len(summary) + 1))
    cols = summary.columns.tolist()
    cols.insert(2, cols.pop(cols.index("NEW_GROUP")))
    summary = summary[cols]

    variant = pd.DataFrame({
        "PRODUCT_ID":   d[COL["product_id"]], "PO_ID": d["_po_id"], "NEW_GROUP": d["_new_group"],
        "GROUP_SOURCE": d["_group_src"], "ADD_TO_BRAND": d["_add_brand"],
        "PRODUCT_TYPE": d["_ptype"], "STRATEGY": d["_strategy"], "BRAND": d["_brand"],
        "PO_KEY": d["_po_key"], "SERIES": d["_series"], "SERIES_SOURCE": d["_series_src"],
        "GRADE": d["_grade"], "MODEL": d["_model"],
        "NETWORK": d["_network"], "CAPACITY": d["_capacity"], "COLOR": d["_color"],
        "FLAGS": d["_flags"], "EDITION": d["_edition"], "SUBTYPE": d["_psubtype"], "MCH": d["_mch"],
        "NEW_CAT_ID": d["_new_id"], "NEW_CAT_NAME": d["_new_name"],
        "CAT_PATH": d["_cat_path"], "FULL_PATH": d["_full_path"],
        "CAT_L1": d["_cat_l1"], "CAT_L2": d["_cat_l2"], "CAT_L3": d["_cat_l3"],
        "AI_CONF": d["_ai_conf"], "AI_WHY": d["_ai_why"],
        "MAT_CODE": d["_mat_code"], "NAME": d["_name"], "NAME_SRC": d["_name_src"],
        "CONFIDENCE": d["_conf"],
    }).sort_values(["PRODUCT_TYPE", "PO_ID", "MODEL"])

    by_type  = (summary.groupby(["PRODUCT_TYPE", "STRATEGY"], as_index=False)
                .agg(po=("PO_ID", "count"), variants=("variant_count", "sum"))
                .sort_values("variants", ascending=False))
    by_brand = (summary.groupby("BRAND", as_index=False)
                .agg(po=("PO_ID", "count"), variants=("variant_count", "sum"))
                .sort_values("po", ascending=False))
    by_group = (variant.groupby(["NEW_GROUP", "GROUP_SOURCE"], as_index=False)
                .agg(variants=("PRODUCT_ID", "count"), pos=("PO_ID", "nunique"))
                .sort_values("variants", ascending=False))

    qa = pd.DataFrame([
        ("แถวทั้งหมด", len(d)), ("PO ที่ได้", len(summary)),
        ("group ที่ได้ (nunique)", int(variant.NEW_GROUP.replace("", np.nan).nunique())),
        ("PRODUCT_TYPE ที่เจอ", d["_ptype"].nunique()),
        ("type ที่ยังไม่ประกาศใน PO_STRATEGY", join(sorted(set(d["_ptype"]) - set(PO_STRATEGY)))),
        ("match DIRECT (group_mch_ids)", int((variant.GROUP_SOURCE == "DIRECT").sum())),
        ("match ด้วย AI (Typhoon)", int((variant.GROUP_SOURCE == "AI").sum())),
        ("ยัง UNMATCHED (ไม่มี group)", int((variant.GROUP_SOURCE == "UNMATCHED").sum())),
        ("group ที่ต่อ BRAND (add_to_brand=Y)", int((variant.ADD_TO_BRAND == "Y").sum())),
        ("group ที่ไม่ต่อ BRAND (add_to_brand=N)", int((variant.ADD_TO_BRAND == "N").sum())),
        ("แถวที่ไม่มีชื่อเลย", int((variant.NAME == "").sum())),
        ("แถวที่ไม่มีแบรนด์", int((variant.BRAND == UNBRANDED_LABEL).sum())),
        ("PRODUCT_TYPE ที่ถูกตัดออก", join(sorted(EXCLUDE_PRODUCT_TYPES))),
        ("CONFIDENCE HIGH", int((variant.CONFIDENCE == "HIGH").sum())),
        ("CONFIDENCE MEDIUM", int((variant.CONFIDENCE == "MEDIUM").sum())),
        ("CONFIDENCE LOW", int((variant.CONFIDENCE == "LOW").sum())),
        ("N/A (ไม่ต้อง parse series)", int((variant.CONFIDENCE == "N/A").sum())),
        ("PO ที่มี variant เดียว", int((summary.variant_count == 1).sum())),
        ("tier ที่เรียนรู้เอง", len(learned)),
        ("series รวมด้วย SERIES_ALIAS", int((variant.SERIES_SOURCE == "alias").sum())),
        ("series รวมด้วย AI", int((variant.SERIES_SOURCE == "ai").sum())),
    ], columns=["METRIC", "VALUE"])

    ai_rows = variant[variant.GROUP_SOURCE == "AI"]
    cat_review = (
        ai_rows.groupby(["MCH", "NEW_CAT_ID", "NEW_CAT_NAME"], as_index=False)
        .agg(variants=("PRODUCT_ID", "count"), example=("NAME", "first"),
             why=("AI_WHY", "first"), avg_conf=("AI_CONF", "mean"), group=("NEW_GROUP", "first"))
        .sort_values("variants", ascending=False)
    ) if len(ai_rows) else pd.DataFrame(
        columns=["MCH", "NEW_CAT_ID", "NEW_CAT_NAME", "variants", "example", "why", "avg_conf", "group"]
    )

    sr_rows = variant[variant.SERIES_SOURCE.isin(["alias", "ai"])]
    series_review = (
        sr_rows.groupby(["BRAND", "SERIES", "SERIES_SOURCE"], as_index=False)
        .agg(variants=("PRODUCT_ID", "count"), po=("PO_ID", "nunique"),
             examples=("NAME", lambda s: " | ".join(dict.fromkeys(s))[:120]),
             why=("AI_WHY", "first"))
        .sort_values(["SERIES_SOURCE", "variants"], ascending=[True, False])
    ) if len(sr_rows) else pd.DataFrame(
        columns=["BRAND", "SERIES", "SERIES_SOURCE", "variants", "po", "examples", "why"]
    )

    return {
        "QA": qa, "By_Type": by_type, "By_Brand": by_brand, "By_Group": by_group,
        "PO_Summary": summary, "Cat_Review": cat_review, "Series_Review": series_review,
        "PO_Variant": variant,
        "Review":    variant[variant.CONFIDENCE.isin(["LOW", "MEDIUM"])].copy(),
        "Unmatched": variant[variant.GROUP_SOURCE == "UNMATCHED"].copy(),
        "Unnamed":   variant[variant.NAME.eq("")].copy(),
        "Tier_Vocab": pd.DataFrame({
            "TIER_TOKEN": sorted(vocab),
            "SOURCE": ["learned" if t in learned else "seed" for t in sorted(vocab)],
        }),
    }


# ---------------------------------------------------------------------------
# 6. Export xlsx -> export/<timestamp>/
# ---------------------------------------------------------------------------
def export_xlsx(out: dict[str, pd.DataFrame], output_dir: Path, timestamp: str) -> Path:
    from openpyxl.styles import Font, PatternFill, Alignment

    output_dir.mkdir(parents=True, exist_ok=True)
    dst = output_dir / f"PO_GROUPED_{timestamp}.xlsx"

    with pd.ExcelWriter(dst, engine="openpyxl") as xw:
        for sheet_name, sdf in out.items():
            sdf.to_excel(xw, sheet_name=sheet_name, index=False)
            ws = xw.sheets[sheet_name]
            for c in ws[1]:
                c.font      = Font(name="Arial", bold=True, color="FFFFFF", size=10)
                c.fill      = PatternFill("solid", fgColor="1F3864")
                c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            for col in ws.columns:
                w = max((len(str(x.value or "")) for x in col))
                ws.column_dimensions[col[0].column_letter].width = min(max(w + 2, 10), 50)
            ws.freeze_panes = "A2"

    print(f"\nSaved: {dst} ({dst.stat().st_size // 1024} KB)")
    return dst


# ---------------------------------------------------------------------------
# 7. Insert PO_Summary -> DB table po_group
# ---------------------------------------------------------------------------
PO_GROUP_COLUMNS = [
    "No", "PO_ID", "NEW_GROUP", "PRODUCT_TYPE", "STRATEGY", "BRAND", "PO_KEY", "GRADE",
    "group_source", "add_to_brand", "new_cat_id", "new_cat_name", "cat_path", "full_path",
    "mch", "models", "model_count", "names", "name_source", "subtypes", "networks",
    "capacities", "colors", "flags", "edition", "variant_count", "product_ids",
    "mat_codes", "valid_from", "confidence",
]


def ensure_po_group_table(cursor, connection) -> None:
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS po_group (
            id            INT AUTO_INCREMENT PRIMARY KEY,
            No            INT,
            PO_ID         VARCHAR(512),
            NEW_GROUP     TEXT,
            PRODUCT_TYPE  VARCHAR(100),
            STRATEGY      VARCHAR(50),
            BRAND         VARCHAR(255),
            PO_KEY        VARCHAR(512),
            GRADE         VARCHAR(50),
            group_source  VARCHAR(50),
            add_to_brand  VARCHAR(10),
            new_cat_id    VARCHAR(255),
            new_cat_name  VARCHAR(255),
            cat_path      TEXT,
            full_path     TEXT,
            mch           TEXT,
            models        TEXT,
            model_count   INT,
            names         MEDIUMTEXT,
            name_source   TEXT,
            subtypes      TEXT,
            networks      TEXT,
            capacities    TEXT,
            colors        TEXT,
            flags         TEXT,
            edition       TEXT,
            variant_count INT,
            product_ids   MEDIUMTEXT,
            mat_codes     TEXT,
            valid_from    VARCHAR(50),
            confidence    VARCHAR(20),
            created_at    DATETIME(3) DEFAULT CURRENT_TIMESTAMP(3)
        ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
    """)
    connection.commit()
    print("po_group table ready")


def insert_po_summary(cursor, connection, summary: pd.DataFrame) -> int:
    if summary.empty:
        return 0

    # ทำ column name lowercase เพื่อ map กับ DB
    df = summary.copy()
    df.columns = [c.lower() for c in df.columns]
    # แปลง uppercase ที่ต้องการกลับ
    rename_map = {c.lower(): c for c in PO_GROUP_COLUMNS}
    df = df.rename(columns=rename_map)

    cols_present = [c for c in PO_GROUP_COLUMNS if c in df.columns]
    placeholders = ", ".join(["%s"] * len(cols_present))
    col_names    = ", ".join([f"`{c}`" for c in cols_present])
    sql = f"INSERT INTO po_group ({col_names}) VALUES ({placeholders})"

    rows = 0
    for _, row in df.iterrows():
        values = []
        for c in cols_present:
            v = row[c]
            if v is None or (isinstance(v, float) and np.isnan(v)):
                values.append(None)
            else:
                values.append(str(v) if not isinstance(v, (int, float)) else v)
        cursor.execute(sql, values)
        rows += 1

    connection.commit()
    return rows


# ---------------------------------------------------------------------------
# 8. main()
# ---------------------------------------------------------------------------
def main() -> None:
    env_path = BASE_DIR / ".env"
    load_env(env_path)
    config     = load_database_config(env_path)
    connection = connect_database(config)

    timestamp = datetime.now().strftime("%d%m%Y%H%M%S")
    export_dir = PROJECT_ROOT / os.getenv("EXPORT_OUTPUT_DIR", "export") / timestamp

    try:
        with connection.cursor() as cursor:
            # --- โหลด category_new จาก DB ---
            print("\n=== LOAD category_new from DB ===")
            cat_map, cat_nodes = load_category_from_db(cursor)
            print(f"CAT_MAP={len(cat_map)} | CAT_NODES={len(cat_nodes)}")
            if not cat_map:
                print("!! CAT_MAP ว่าง — ตรวจสอบ table category_new")

            # --- โหลด PRODUCT_MST จาก DB ---
            print("\n=== LOAD PRODUCT_MST from DB ===")
            cursor.execute("SELECT * FROM PRODUCT_MST")
            columns = [col[0] for col in cursor.description]
            rows    = cursor.fetchall()
            df = pd.DataFrame([{c: r[c] for c in columns} for r in rows])
            print(f"PRODUCT_MST: {len(df):,} แถว / {df.shape[1]} คอลัมน์")

            # --- จัดกลุ่ม PO ---
            print("\n=== GROUP PO ===")
            out = group_po(df, cat_map, cat_nodes)
            print(out["QA"].to_string(index=False))

            # --- Export xlsx -> export/<timestamp>/ ---
            print("\n=== EXPORT XLSX ===")
            export_xlsx(out, export_dir, timestamp)

            # --- Insert PO_Summary -> DB po_group ---
            print("\n=== INSERT po_group ===")
            ensure_po_group_table(cursor, connection)
            inserted = insert_po_summary(cursor, connection, out["PO_Summary"])
            print(f"Inserted {inserted:,} rows into po_group")

    finally:
        connection.close()


if __name__ == "__main__":
    main()
