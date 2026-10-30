#!/usr/bin/env python3
"""PO/POP rules 1–9. Python 3.10+. Export or SQL Server input, exact comparisons, full scans.

Defaults to the latest project export. --database reads SQL Server using
product_catalog/.env. Validation runs in Python memory.
Exit codes: 0=all rules pass, 1=errors found, 2=incomplete or execution failure.
The current approved rule definitions are in RULES_TH.md.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import logging
import re
import sys
import zipfile
from datetime import datetime, timezone, timedelta
from pathlib import Path

from openpyxl import Workbook, load_workbook
from openpyxl.cell import WriteOnlyCell
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter

from validation_domain import VERSION, UNIT, MODEL, MAIN, TYPE, BLANK, SCHEMAS, parse_pairs
from validation_rules import RuleValidator

LOG = logging.getLogger("po_pop")


def digest(path):
 h = hashlib.sha256()
 with open(path, 'rb') as f:
  for b in iter(lambda: f.read(8 * 1024 * 1024), b''):
   h.update(b)
 return h.hexdigest()


class Validator(RuleValidator):
 def read_xlsx(self, path, table, sheet_name=None):
  base, required, fields = SCHEMAS[table]
  base = sheet_name or base
  wb = load_workbook(path, read_only=True, data_only=False)
  try:
   # A numbered split sheet is part of the same source, never a different entity.
   sheets = [s for s in wb if s.title == base or re.fullmatch(re.escape(base)+r' \(\d+\)',s.title)]
   if not sheets:
    self.input_error(table,'ไม่พบ Sheet '+base,src=str(path))
    return
   ok = True
   for sh in sheets:
    count = skipped = 0
    batch = []
    try:
     # Ignore unreliable Excel dimension metadata; iterate all actual XML cells.
     sh.reset_dimensions()
     it = sh.iter_rows()
     if table == 't':
      prefix = [next(it, ()) for _ in range(5)]
      locations = {}
      for ri, row in enumerate(prefix):
       for ci, cell in enumerate(row):
        if cell.value in required:
         locations.setdefault(cell.value, set()).add(ci)
      if any(len(locations.get(h,set())) != 1 for h in required):
       raise ValueError('Header Meta ต้องมี POP ID และ matCode ที่ไม่กำกวมใน 5 แถวแรก')
      ix = [next(iter(locations[h])) for h in required]
      # Exact supported BM template: type row 4, cardinality row 5.
      card = prefix[4][ix[1]].value if len(prefix[4])>ix[1] else None
      if not isinstance(card,str) or not card.startswith('Cardinality'):
       raise ValueError('รูปแบบ Header Meta ไม่ใช่ template 5 แถวที่รองรับ ห้ามเดาแถวเริ่มข้อมูล')
      start = 6
     else:
      header = [c.value for c in next(it, ())]
      if any(header.count(h)!=1 for h in required):
       raise ValueError('Column ขาดหรือซ้ำ: '+', '.join(h for h in required if header.count(h)!=1))
      ix = [header.index(h) for h in required]; start=2
     for rn,row in enumerate(it,start):
      if all(c.value in BLANK for c in row):
       skipped+=1; continue
      count+=1
      values=[]; valid=True
      for col in ix:
       cell=row[col] if col<len(row) else None
       value=cell.value if cell is not None else None
       if value is None: value=''
       if (cell is not None and cell.data_type in ('f','e')) or not isinstance(value,str):
        self.input_error(table,'ค่าที่ใช้เปรียบเทียบเป็นสูตร/error/ไม่ใช่ Text จึงไม่แปลงค่าเอง',src=str(path),sheet=sh.title,rn=rn,related=f'Column {col+1}; value={value!r}')
        valid=False;ok=False
       values.append(value)
      if valid: batch.append((str(path),sh.title,rn,*values))
      if len(batch)>=10000:
       self._insert(table,batch);batch=[]
     self._insert(table,batch)
    except (ValueError,KeyError,TypeError) as e:
     ok=False; self.input_error(table,str(e),src=str(path),sheet=sh.title)
    self.inputs.append({'source':str(path),'sheet':sh.title,'table':table,'records':count,'fully_blank_rows':skipped,'all_hidden_filtered_rows_included':True})
   if ok:self.ready.add(table)
   LOG.info('%s: %s rows',table,len(self.rows[table]))
 
  finally:
   wb.close()

 def read_cv_files(self, paths):
  ok=True;total=0
  for path in paths:
   try:
    if path.suffix.lower()=='.zip':
     with zipfile.ZipFile(path) as z:
      members=[i for i in z.infolist() if not i.is_dir()]
      if len(members)!=1 or not members[0].filename.lower().endswith('.csv'):
       raise ValueError('ZIP ต้องมี CSV หนึ่งไฟล์เท่านั้น กรุณาแยกไฟล์แล้วส่งหลาย --char-value paths')
      with z.open(members[0]) as raw:
       total+=self._csv(io.TextIOWrapper(raw,encoding='utf-8-sig',newline=''),str(path)+'::'+members[0].filename)
    elif path.suffix.lower()=='.csv':
     with path.open(encoding='utf-8-sig',newline='') as f:total+=self._csv(f,str(path))
    else:raise ValueError('--char-value รองรับ CSV หรือ ZIP เท่านั้น')
   except (ValueError,UnicodeError,csv.Error,zipfile.BadZipFile) as e:
    ok=False;self.input_error('cv',str(e),src=str(path))
  if ok:self.ready.add('cv')
  LOG.info('Char_Value: %s records',total)

 def _csv(self, f, source, table='cv'):
  reader=csv.reader(f,strict=True);header=next(reader,[])
  required=SCHEMAS[table][1]
  if any(header.count(h)!=1 for h in required):raise ValueError('Char_Value header ขาดหรือซ้ำ')
  ix=[header.index(h) for h in required];batch=[];count=skipped=0
  for rn,row in enumerate(reader,2):
   if len(row)!=len(header):raise ValueError(f'Record {rn}: {len(row)} columns, expected {len(header)}')
   if not any(v!='' for v in row):skipped+=1;continue
   count+=1;batch.append((source,SCHEMAS[table][0]+' CSV',rn,*[row[i] for i in ix]))
   if len(batch)>=10000:
    self._insert(table,batch);batch=[]
   if count%250000==0:LOG.info('Char_Value streamed %s records',count)
  self._insert(table,batch)
  self.inputs.append({'source':source,'sheet':SCHEMAS[table][0]+' CSV','table':table,'records':count,'fully_blank_rows':skipped,'row_numbering':'logical CSV record; header=1'})
  return count



REPORT_FIELDS=['id','rule','severity','code','reason','src','sheet','rn','po','pid','vid','sku','cid','name','val','expected','related','occurrences']
REPORT_HEADERS=['Case ID','Rule No','Severity','Error Code','Reason','Source File','Source Sheet','Source Row / Record','PO ID','POP ID','Variant ID','SKU / matCode','Characteristics ID','Char Name','value','Expected Condition','Related Evidence','Source Occurrence Count']


def export_report(v, path, severity, verify=True):
 """Write-only export supports Excel 2016; no formulas, no silent truncation.

 The user's request explicitly requires Python, hence openpyxl for portable
 standalone reporting. Split sheets before Excel's 1,048,576-row limit.
 """
 wb=Workbook(write_only=True)
 expected_hash=hashlib.sha256(); rowcounts={}
 body_alignment=Alignment(vertical='top',wrap_text=True)
 ws=None;sheetno=0;sheetrows=0
 def new_sheet(name,header):
  s=wb.create_sheet(name);s.freeze_panes='A2'
  for i in range(1,len(header)+1):s.column_dimensions[get_column_letter(i)].width=22
  for i in (5,6,9,11,16,17):
   if i<=len(header):s.column_dimensions[get_column_letter(i)].width=48
  cells=[]
  for x in header:
   c=WriteOnlyCell(s,x);c.data_type='s';c.font=Font(name='Calibri',bold=True,color='FFFFFF');c.fill=PatternFill('solid',fgColor='283E57');c.alignment=Alignment(wrap_text=True);cells.append(c)
  s.append(cells);rowcounts[name]=1
  LOG.info('Report %s: created sheet %s',path.name,name)
  expected_hash.update(json.dumps([name,header],ensure_ascii=False,separators=(',',':')).encode())
  return s
 def append(s,row):
  cells=[];values=[]
  for value in row:
   value='' if value is None else value
   if isinstance(value,str) and len(value)>32767:raise ValueError('Report cell exceeds Excel limit; data was not truncated')
   c=WriteOnlyCell(s,value)
   if isinstance(value,str):c.data_type='s'  # literal '=' is never a formula
   c.alignment=body_alignment;cells.append(c);values.append(value)
  s.append(cells);rowcounts[s.title]+=1
  if (rowcounts[s.title]-1)%10000==0:
   LOG.info('Report %s: %s written %s rows',path.name,s.title,rowcounts[s.title]-1)
  expected_hash.update(json.dumps([s.title,values],ensure_ascii=False,separators=(',',':')).encode())
 base='Error Detail' if severity=='ERROR' else 'Review Detail'
 ws=new_sheet(base,REPORT_HEADERS+['Detail Part']);sheetno=1;sheetrows=1
 selected = sorted((i for i in v.issues if (i['severity']=='ERROR') == (severity=='ERROR')), key=lambda i: (float(i['rule']) if i['rule']!='INPUT' else 0, i['id']))
 LOG.info('Report %s: writing %s cases',path.name,len(selected))
 for r in selected:
  row=[r[f] for f in REPORT_FIELDS]
  # Oversized evidence is continued, never silently truncated or discarded.
  parts=max([1]+[(len(x)+29999)//30000 for x in row if isinstance(x,str)])
  for part in range(parts):
   if sheetrows>=1000000:
    ws.auto_filter.ref=f'A1:S{sheetrows}';sheetno+=1;ws=new_sheet(base+' '+str(sheetno),REPORT_HEADERS+['Detail Part']);sheetrows=1
   vals=[x[part*30000:(part+1)*30000] if isinstance(x,str) and len(x)>30000 else x for x in row]
   append(ws,vals+[f'{part+1}/{parts}']);sheetrows+=1
 ws.auto_filter.ref=f'A1:S{sheetrows}'
 # Every repeated Char_Value row behind a 9.4 case is available, not a sample.
 if 'cv' in v.ready:
  ev=None;en=0;er=0;eh=['Case ID','Source File','Source Sheet','Source Record','PO ID','Characteristics ID','Char Name','value']
  from validation_rules import group
  LOG.info('Report %s: indexing %s Char_Value records for source evidence',path.name,len(v.rows['cv']))
  occurrences = group(v.rows['cv'], 'po', 'cid', 'val')
  LOG.info('Report %s: writing source evidence',path.name)
  for issue in sorted(selected, key=lambda i: i['id']):
   if issue['rule'] != '9.4':continue
   for cv in occurrences[issue['po'],issue['cid'],issue['val']]:
    if ev is None or er>=1000000:
     en+=1;ev=new_sheet('Source Occurrences'+(' '+str(en) if en>1 else ''),eh);er=1
    append(ev,[issue['id'], *[cv[f] for f in ('src','sheet','rn','po','cid','name','val')]]);er+=1
 LOG.info('Report %s: saving XLSX (%s rows including headers)',path.name,sum(rowcounts.values()))
 wb.save(path)
 LOG.info('Report %s: saved (%s bytes)',path.name,path.stat().st_size)
 if verify:
  LOG.info('Report %s: verifying every cell',path.name)
  actual=hashlib.sha256();rb=load_workbook(path,read_only=True,data_only=False)
  for s in rb:
   count=0
   for row in s.iter_rows():
    values=['' if c.value is None else c.value for c in row]
    if any(c.data_type=='f' for c in row):raise AssertionError('Unexpected formula in report')
    actual.update(json.dumps([s.title,values],ensure_ascii=False,separators=(',',':')).encode());count+=1
    if count%10000==0:LOG.info('Report %s: %s verified %s/%s rows',path.name,s.title,count,rowcounts[s.title])
   if count!=rowcounts[s.title]:raise AssertionError('Report row count mismatch')
   LOG.info('Report %s: %s verification complete (%s rows)',path.name,s.title,count)
  rb.close()
  if actual.digest()!=expected_hash.digest():raise AssertionError('Report cell-by-cell verification failed')
 LOG.info('Report %s: complete',path.name)
 return rowcounts


def config_read(path):
 conf=json.loads(path.read_text(encoding='utf-8-sig'))
 for key in ('exclude_po_ids','exclude_pop_ids'):
  ids=conf[key]
  if not isinstance(ids,list) or any(not isinstance(x,str) or not x or x!=x.strip() for x in ids) or len(ids)!=len(set(ids)):
   raise ValueError(key+': ต้องเป็นรายการ Text ไม่ซ้ำ ไม่มี whitespace รอบ ID')
 for key in ('missing_model','blank_model','duplicate_same_po_mapping','cross_level_different_value','same_or_blank_sku'):
  if conf.get(key) not in ('REVIEW','ERROR'):raise ValueError(key+': ใช้ REVIEW หรือ ERROR เท่านั้น')
 return conf


def main(argv=None):
 ap=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
 ap.add_argument('folder',nargs='?',type=Path,help='Export round name or path; omitted: latest round in the project export directory')
 ap.add_argument('--po',type=Path);ap.add_argument('--pop',type=Path);ap.add_argument('--meta',type=Path)
 ap.add_argument('--database',action='store_true',help='Read SQL Server using the project .env and template_mapping')
 ap.add_argument('--input-dir',type=Path,help='Export round name, round path or XLSX directory; use sibling csv for large Char_Value')
 ap.add_argument('--latest-export',type=Path,help='Use the latest DDMMYYYYHHMMSS export folder under this directory')
 ap.add_argument('--list-inputs',action='store_true',help='List resolved --input-dir files without running validation')
 ap.add_argument('--env',type=Path,default=Path(__file__).resolve().parent.parent/'.env')
 ap.add_argument('--check-connection',action='store_true',help='Test database connection without running validation')
 ap.add_argument('--char-value',type=Path,nargs='+',help='CSV/ZIP หนึ่งหรือหลายไฟล์; ไม่ระบุจะใช้ Sheet Char_Value ใน PO')
 ap.add_argument('--config',type=Path,default=Path(__file__).with_name('config.json'))
 ap.add_argument('--out',type=Path,default=Path(__file__).resolve().parents[2]/'results')
 args=ap.parse_args(argv)
 sources=None;cv_paths=None
 if args.folder:
  if any((args.input_dir,args.latest_export,args.database,args.po,args.pop,args.meta,args.check_connection)):
   ap.error('folder cannot be combined with another input mode')
  args.input_dir=args.folder
 if args.latest_export:
  if any((args.input_dir,args.database,args.po,args.pop,args.meta,args.check_connection)):
   ap.error('--latest-export cannot be combined with other input modes or --check-connection')
  from export_source import latest_export_input
  try:args.input_dir=latest_export_input(args.latest_export)
  except (OSError,ValueError) as error:ap.error(str(error))
  print(f'Using latest export: {args.input_dir}')
 elif args.input_dir or not any((args.database,args.po,args.pop,args.meta,args.check_connection)):
  from export_source import resolve_export_input
  try:args.input_dir=resolve_export_input(args.input_dir)
  except (OSError,ValueError) as error:ap.error(str(error))
  print(f'Using export: {args.input_dir}')
 if args.list_inputs and not args.input_dir:ap.error('--list-inputs requires --input-dir')
 if args.input_dir:
  if any((args.database,args.po,args.pop,args.meta,args.check_connection)):
   ap.error('--input-dir cannot be combined with --database, --check-connection, --po, --pop or --meta')
  from export_source import discover_export_inputs
  try:sources,cv_paths=discover_export_inputs(args.input_dir,args.char_value)
  except (OSError,ValueError) as error:ap.error(str(error))
  if args.list_inputs:
   for table,path in sources.items():print(f'{table}: {path}')
   for path in cv_paths:print(f'cv: {path}')
   return 0
 if args.check_connection:
  from database_source import check_connection
  try:check_connection(args.env);return 0
  except Exception as error:
   print(f'Database connection failed ({type(error).__name__}). Check the ODBC driver, network and .env settings.',file=sys.stderr);return 2
 if args.database and any((args.po,args.pop,args.meta,args.char_value)):
  ap.error('--database cannot be combined with file inputs')
 if not args.input_dir and not args.database and any((args.po,args.pop,args.meta,args.char_value)) and not all((args.po,args.pop,args.meta)):
  ap.error('File mode requires all of --po, --pop and --meta')
 now=datetime.now(timezone(timedelta(hours=7)));stamp=now.strftime('%d%m%Y%H%M%S')
 if args.input_dir:
  source_dir=args.input_dir.parent if args.input_dir.name.lower()=='xlsx' else args.input_dir
  out=args.out/('check_'+source_dir.name)/('run_'+stamp+'_'+now.strftime('%f'))
 else:
  out=args.out/('run_'+stamp)
 # Avoid collision or accidental overwrite when running twice within a second.
 out.mkdir(parents=True,exist_ok=False)
 logging.basicConfig(level=logging.INFO,format='%(asctime)s %(message)s',handlers=[logging.StreamHandler(),logging.FileHandler(out/'run.log',encoding='utf-8')])
 try:
  conf=config_read(args.config)
  paths=list(sources.values())+cv_paths if sources else ([] if args.database else [args.po,args.pop,args.meta]+(args.char_value or []))
  if len({str(p.resolve()) for p in paths})!=len(paths):raise ValueError('ระบุ input path ซ้ำ')
  for p in paths:
   if not p.is_file():raise FileNotFoundError(p)
  manifest={str(p.resolve()):digest(p) for p in paths}
  (out/'config_used.json').write_text(json.dumps(conf,ensure_ascii=False,indent=2),encoding='utf-8')
  v=Validator(conf)
  if sources:
   from export_source import read_export_inputs
   read_export_inputs(v,sources,cv_paths,args.env,on_source=lambda p:manifest.__setitem__(str(p),digest(p)))
  elif args.database:
   from database_source import read_database
   read_database(v,args.env)
  else:
   from csv_fallback import read_with_fallback
   register=lambda p:manifest.__setitem__(str(p),digest(p))
   for t in ('po','o','v','l'):read_with_fallback(v,args.po.resolve(),t,SCHEMAS[t][0],args.env,on_source=register)
   for t in ('m','c'):read_with_fallback(v,args.pop.resolve(),t,SCHEMAS[t][0],args.env,on_source=register)
   read_with_fallback(v,args.meta.resolve(),'t',SCHEMAS['t'][0],args.env,on_source=register)
   if args.char_value:v.read_cv_files([p.resolve() for p in args.char_value])
   else:read_with_fallback(v,args.po.resolve(),'cv',SCHEMAS['cv'][0],args.env,on_source=register)
  v.run()
  summary=v.summary();summary['input_sha256']=manifest;summary['run_time_bangkok']=now.isoformat()
  # Ensure the sources did not change while being read.
  if any(digest(Path(p))!=sha for p,sha in manifest.items()):raise RuntimeError('Input changed during validation')
  LOG.info('Exporting Error-only Excel report')
  summary['error_report_rows']=export_report(v,out/f'Result_check_PO_POP_01-09_ErrorOnly_{stamp}.xlsx','ERROR')
  if any(i['severity']!='ERROR' for i in v.issues):
   summary['review_report_rows']=export_report(v,out/f'Result_Review_Warning_{stamp}.xlsx','REVIEW')
  # Independent report serialization audit is mandatory (all cells, all sheets).
  summary['report_verification']='All written cells reopened and matched; no sampling'
  (out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
  lines=['PO/POP validation '+stamp]
  for r in summary['rules']:lines.append(f"Rule {r['rule']}: {r['status']} | Errors={r['error_cases']} | Review={r['review_cases']} | Warning={r['warning_cases']}")
  lines+=['Input issues: '+str(summary['input_issues']),'Report: '+str(out.resolve()),'CSV source row = logical record, header = 1.']
  (out/'summary.txt').write_text('\n'.join(lines),encoding='utf-8');print('\n'.join(lines))
  if summary['input_issues'] or any(r['review_cases'] for r in summary['rules']):return 2
  return 1 if any(r['error_cases'] for r in summary['rules']) else 0
 except Exception as e:
  LOG.exception('Validation did not complete')
  (out/'FAILED.json').write_text(json.dumps({'complete':False,'error':str(e),'type':type(e).__name__},ensure_ascii=False,indent=2),encoding='utf-8')
  return 2


if __name__=='__main__':
 sys.exit(main())
