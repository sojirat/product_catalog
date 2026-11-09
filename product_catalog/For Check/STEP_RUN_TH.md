# ขั้นตอนรันตรวจข้อมูลจริงตามกฎ 1–14

คำสั่งตรวจข้อมูลหนึ่งครั้งจะเรียกกฎข้อ 1 ถึง 14 รวมข้อย่อยของข้อ 9 ให้อัตโนมัติ ไม่ต้องรันแยกทีละข้อ
หากไม่ระบุข้อมูลต้นทาง โปรแกรมจะอ่านรอบล่าสุดจาก `export/` ของโปรเจกต์โดยอัตโนมัติ
หากระบุชื่อโฟลเดอร์ จะอ่านรอบนั้นแทน หรือใช้ `--database` เพื่ออ่านจากฐานข้อมูล

## คำสั่งตรวจ 4 รูปแบบสำหรับ Mac และ Windows

ข้อ 14 รองรับ PRODUCT_MST หลายแถวต่อ SKU โดยกรอง COMPANY ด้วย company ใน Char List แล้วใช้ PRODUCT_ID ของทุกแถวที่ตรงกันค้นราคา หลังกรอง PRICE_GROUP จะเลือก EFFECTIVE_DATE ล่าสุดมาเทียบราคา หากใช้ CSV ให้เตรียมคอลัมน์ EFFECTIVE_DATE ใน PRICE_MST ด้วย เช่น `2026-11-09 10:58:00`

สำหรับข้อ 7 หากไม่พบ main_model ใน POP, Variant และ PO ที่เป็น DEVICE โปรแกรมจะใช้ SKU ตรวจ `PRODUCT_MST.MAIN_MODEL` เพิ่ม หากพบหนึ่งแถวที่เป็น NULL หรือข้อความว่าง `''` จะผ่านและสร้างรายงานแยก `Result_Rule7_NoMainModel_<วันเวลา>.xlsx` ในโฟลเดอร์ผลตรวจ เพื่อดู Variant ID ที่ไม่มี main model รายงานนี้สร้างเฉพาะเมื่อมีรายการที่ผ่านด้วยเงื่อนไขนี้ หากไม่พบ MAT_CODE หรือ MAIN_MODEL มีข้อมูล จะอยู่ใน Error Report ตามเดิม ข้อความที่มีเฉพาะช่องว่างยังถือว่ามีค่า

รันคำสั่งจากโฟลเดอร์หลักของโปรเจกต์ที่มี `Makefile` และโฟลเดอร์ `product_catalog` สำหรับ Mac ให้ติดตั้ง dependencies ด้วย `make setup-check` ก่อนใช้งานครั้งแรก ส่วน Windows ให้ติดตั้งตามหัวข้อเตรียม Python ด้านล่าง

โหมด database ใช้การเชื่อมต่อจาก `product_catalog/.env` หากเชื่อมต่อไม่ได้จะใช้ CSV ใน `Database/` อัตโนมัติ ส่วนโหมด CSV ระบุ `--csv` เพื่อไม่เชื่อมต่อฐานข้อมูล และต้องเตรียม `template_mapping.csv` พร้อม CSV ของ table/view ที่กฎที่เลือกต้องใช้ใน `Database/`

### 1. ตรวจทุกข้อ 1–14 ด้วย database

Mac:

```sh
make check-db
```

Windows PowerShell:

```powershell
& ".\product_catalog\For Check\run_check.cmd" --database
```

### 2. ตรวจทุกข้อ 1–14 ด้วย CSV

Mac:

```sh
make check-db CHECK_ARGS="--csv"
```

Windows PowerShell:

```powershell
& ".\product_catalog\For Check\run_check.cmd" --csv
```

บน Mac คำสั่ง `make check-db` ร่วมกับ `--csv` จะอ่าน CSV แทนฐานข้อมูล โดยไม่เปิดการเชื่อมต่อฐานข้อมูล

### 3. ตรวจหลายข้อในครั้งเดียวด้วย database

ตัวอย่างตรวจข้อ 10, 12, 13 และ 14:

Mac:

```sh
make check-db CHECK_ARGS="--rules 10 12 13 14"
```

Windows PowerShell:

```powershell
& ".\product_catalog\For Check\run_check.cmd" --database --rules 10 12 13 14
```

### 4. ตรวจหลายข้อในครั้งเดียวด้วย CSV

ตัวอย่างตรวจข้อ 10, 12, 13 และ 14:

Mac:

```sh
make check-db CHECK_ARGS="--csv --rules 10 12 13 14"
```

Windows PowerShell:

```powershell
& ".\product_catalog\For Check\run_check.cmd" --csv --rules 10 12 13 14
```

เปลี่ยนเลขหลัง `--rules` เป็นข้อที่ต้องการตรวจ โดยคั่นด้วยช่องว่าง รองรับข้อ 1 ถึง 14 และข้อ 9 รวมข้อย่อย 9.1–9.6 หากไม่ระบุ `--rules` จะตรวจทุกข้อ 1–14

## ใช้ CSV ใน Database แทนฐานข้อมูล

หากระบุรอบ export ร่วมกับ `--csv` ข้อมูลหลักยังอ่านจาก Excel ของรอบนั้น ส่วน `--csv` ใช้แทนการเรียกฐานข้อมูล หาก Excel อ่านไม่สำเร็จ โปรแกรมจะหา CSV ชื่อเดียวกันในโฟลเดอร์ `csv` ของรอบนั้นก่อน หากไม่มี จะหา CSV ตามชื่อชนิดข้อมูล เช่น `PO_Product_Variants_*.csv` ในโฟลเดอร์เดียวกัน แม้ timestamp ต่างจาก Excel ต้องพบเพียงหนึ่งไฟล์ หากมีหลายไฟล์จะหยุดเพื่อไม่เดาไฟล์ที่ต้องใช้

รองรับชื่อไฟล์ที่ต่อท้ายด้วยเวลา เช่น `PRODUCT_MST_202611091058.csv` โดยใช้รูปแบบ `YYYYMMDDHHMM` หรือ `YYYYMMDDHHMMSS` โปรแกรมเลือก `<table>.csv` ก่อน หากไม่มีจึงเลือกไฟล์ timestamp ล่าสุดจากชื่อไฟล์ หากเวลาเท่ากันเลือกไฟล์ที่ระบุวินาที ใช้กฎเดียวกันกับทุก table/view รวม `template_mapping` และ `table_mapping` โดยไม่ต้องแก้คำสั่งรัน

วางไฟล์ `<ชื่อ table หรือ view>.csv` ใน `Database/` ที่ root ของโปรเจกต์ เช่น `PRODUCT_MST.csv`, `PRICE_MST.csv` และ `vw_catalog_offer_specification_characteristic.csv` แถวแรกต้องเป็นชื่อคอลัมน์ตามฐานข้อมูล ใช้ UTF-8 และใช้ `\N` สำหรับ SQL NULL ส่วนช่องว่างเปล่าคือข้อความว่าง

หากต้องการอ่านข้อมูลหลักทั้งหมดจาก CSV ให้เตรียม `template_mapping.csv` พร้อม CSV ของ table/view ที่ `DATABASE NAME` ระบุด้วย ไม่ต้องมี mapping เมื่ออ่านข้อมูลหลักจาก export และใช้เฉพาะข้อมูลอ้างอิงข้อ 12–14

รันจาก root ของโปรเจกต์บน Windows:

```powershell
# ตรวจทุกกฎจาก Database โดยไม่เชื่อมฐานข้อมูล
& ".\product_catalog\For Check\run_check.cmd" --csv

# ตรวจแยกข้อ หรือเลือกหลายข้อ
& ".\product_catalog\For Check\run_check.cmd" --csv --rules 13
& ".\product_catalog\For Check\run_check.cmd" --csv --rules 10 12 13 14

# อ่านข้อมูลหลักจาก export และใช้ CSV แทนการเรียกฐานข้อมูล
& ".\product_catalog\For Check\run_check.cmd" "30102026110649" --csv
& ".\product_catalog\For Check\run_check.cmd" "30102026110649" --csv --rules 13 14

# เลือกโฟลเดอร์ CSV อื่น
& ".\product_catalog\For Check\run_check.cmd" --csv --database-dir "D:\ReferenceData" --rules 13

# ลองฐานข้อมูลก่อน หากเชื่อมต่อไม่ได้จะใช้ Database อัตโนมัติ
& ".\product_catalog\For Check\run_check.cmd" --database --rules 13
```

บน Mac ใช้คำสั่ง:

```sh
make check-db CHECK_ARGS="--csv"
make check-db CHECK_ARGS="--csv --rules 13 14"
make check INPUT_DIR="30102026110649" CHECK_ARGS="--csv --rules 13"
```

ไม่ระบุ `--rules` หมายถึงตรวจทุกข้อ หากไฟล์ CSV ที่ต้องใช้ไม่ครบ โปรแกรมจะหยุดหรือรายงาน Review พร้อม `complete=false` ตามประเภทข้อมูล ดูกฎกลางใน `RULES_TH.md` และไฟล์ที่ใช้จริงใน `run.log` กับ `summary.json`

## รันบน Mac ด้วย make

เปิด Terminal ที่โฟลเดอร์หลักของโปรเจกต์ (โฟลเดอร์ที่มี `Makefile`):

```sh
cd /Users/milk/_AIS/product_catalog2
```

ติดตั้ง Python dependencies สำหรับตัวตรวจครั้งแรก หรือเมื่อ dependencies เปลี่ยน:

```sh
make setup-check
```

หากมี `.venv` และติดตั้ง dependencies ครบแล้ว ให้ข้ามขั้นตอนนี้ได้
ทุกคำสั่งด้านล่างเรียก Python จาก `.venv` ให้อัตโนมัติ ไม่ต้อง activate ก่อน

ตรวจข้อมูล export ครบกฎ 1–14:

```sh
make check
```

เมื่อไม่ระบุ `INPUT_DIR` จะเลือกรอบล่าสุดใน `export/` ตามวันเวลาในชื่อโฟลเดอร์รูปแบบ `DDMMYYYYHHMMSS`
แล้วใช้โฟลเดอร์ `xlsx` ของรอบนั้น โดยแสดง path ที่เลือกก่อนเริ่มตรวจ
หากไม่พบรอบ export หรือรอบล่าสุดไม่มีทั้ง `xlsx` และ `csv` จะหยุดพร้อมข้อความผิดพลาด รองรับรอบที่มีเฉพาะ `csv`

หากต้องการเลือกรอบเอง:

```sh
make check INPUT_DIR="30102026110649"
```

เปลี่ยนชื่อโฟลเดอร์เป็นรอบ export ที่ต้องการ ไม่ต้องใส่ `export/` และ `/xlsx`
ยังระบุ path ของโฟลเดอร์รอบ export หรือโฟลเดอร์ `xlsx` ได้ ทั้ง relative path จากตำแหน่งที่รันและ absolute path
ถ้า path มีช่องว่างให้ใส่เครื่องหมายคำพูดตามตัวอย่าง
เก็บโฟลเดอร์ `csv` ของรอบเดียวกันไว้ข้าง `xlsx` เพื่อใช้ fallback

คำสั่งอื่นที่ใช้ได้:

```sh
# ดูรายชื่อไฟล์ก่อนตรวจ
make check CHECK_ARGS="--list-inputs"

# ตรวจจากฐานข้อมูลโดยตรง ใช้ product_catalog/.env
make check-db

# ตรวจเฉพาะการเชื่อมต่อฐานข้อมูล
make check-connection

# ดูตัวเลือกทั้งหมดของโปรแกรม
make check CHECK_ARGS="--help"

# ทดสอบโค้ดด้วยข้อมูลจำลอง
make check-test
```

โหมดฐานข้อมูลและ CSV fallback ที่ค้น mapping จากฐานข้อมูล ต้องมี ODBC Driver ที่ตรงกับ `DB_DRIVER` ใน `product_catalog/.env`
Makefile ใช้การตั้งค่า OpenSSL สำหรับ ODBC บน Mac แบบเดียวกับคำสั่งรันหลักของโปรเจกต์

ผลตรวจจาก export อยู่ที่ `results/check_<ชื่อโฟลเดอร์ต้นทาง>/` ในโฟลเดอร์หลักของโปรเจกต์ ระดับเดียวกับ `export/`
เช่น `results/check_30102026201519/` โดยไม่มีโฟลเดอร์ `run_...` ซ้อนข้างใน
เมื่อตรวจซ้ำรอบ export เดิม ไฟล์ Excel จะแยกตามวันเวลาในชื่อไฟล์ ส่วน `summary.txt`, `summary.json`, `config_used.json` และ `run.log` จะเป็นข้อมูลรอบล่าสุด
ส่วนการตรวจจากฐานข้อมูลหรือไฟล์ที่ระบุแยกด้วย `--po` / `--pop` / `--meta` ยังใช้ `results/run_<วันเวลาที่รัน>/`
อ่านความหมายของไฟล์ผลลัพธ์และสถานะได้ในขั้นตอนที่ 3 ด้านล่าง

## รันบน Windows

`run_check.cmd` และ `validate_po_pop.py` ใช้การเลือกโฟลเดอร์แบบเดียวกันกับ `make check`
โดยตำแหน่ง `export/` เริ่มต้นอ้างอิงจากที่ตั้งโปรเจกต์ ไม่ขึ้นกับโฟลเดอร์ที่เปิด Terminal:

ตัวอย่างนี้รันจากโฟลเดอร์หลัก `C:\Users\waree\OneDrive\Documents\GitHub\product_catalog`:

```powershell
# เลือกรอบล่าสุด
& ".\product_catalog\For Check\run_check.cmd"

# เลือกรอบตามชื่อโฟลเดอร์
& ".\product_catalog\For Check\run_check.cmd" "30102026110649"

# อ่านฐานข้อมูลโดยตรง
& ".\product_catalog\For Check\run_check.cmd" --database
```

หากระบุ `--input-dir` เป็น relative path จะอ้างอิงจากโฟลเดอร์ที่เปิด PowerShell เช่น จากโฟลเดอร์หลักใช้:

```powershell
& ".\product_catalog\For Check\run_check.cmd" --input-dir ".\export\30102026110649\xlsx"
```

หากเรียก Python โดยตรงจากโฟลเดอร์ `product_catalog\For Check` ใช้ `python validate_po_pop.py` เพื่อเลือกรอบล่าสุด
หรือ `python validate_po_pop.py 30102026110649` เพื่อเลือกรอบตามชื่อโฟลเดอร์

## 1. เปิด PowerShell และเข้าโฟลเดอร์โปรแกรม

คัดลอกคำสั่งนี้ไปรันได้จากทุกตำแหน่ง:

```powershell
cd "C:\Users\waree\OneDrive\Documents\GitHub\product_catalog\product_catalog\For Check"
```

ถ้าหน้าจอขึ้นต้นด้วย `PS ...\product_catalog\For Check>` อยู่แล้ว ให้ข้ามขั้นตอนนี้
คำสั่งในขั้นตอนถัดไปทั้งหมดใช้ตำแหน่งนี้เป็นจุดเริ่มต้น

## 2. รันตรวจทุกกฎด้วยคำสั่งเดียว

ตรวจทุก Rule ใช้คำสั่งเดิมโดยไม่ระบุ `--rules` หรือเลือกเฉพาะบางข้อได้จากโฟลเดอร์หลักของโปรเจกต์:

```powershell
# ตรวจทุกข้อ 1–14
& ".\product_catalog\For Check\run_check.cmd" "30102026110649"

# ตรวจเฉพาะข้อ 13
& ".\product_catalog\For Check\run_check.cmd" "30102026110649" --rules 13

# ตรวจหลายข้อในครั้งเดียว
& ".\product_catalog\For Check\run_check.cmd" "30102026110649" --rules 10 13 14

# ดูไฟล์ที่ต้องใช้สำหรับข้อที่เลือก
& ".\product_catalog\For Check\run_check.cmd" "30102026110649" --rules 10 14 --list-inputs
```

รองรับเลขข้อหลัก 1 ถึง 14 ข้อ 9 จะรวมทุกข้อย่อย 9.1–9.6 โดยโปรแกรมเรียงเลขข้อและข้ามเลขที่ระบุซ้ำ
อ่านเฉพาะไฟล์หรือข้อมูลที่ Rule ที่เลือกต้องใช้ และเชื่อม Product Master / Price Master เมื่อเลือกกฎที่ใช้ฐานข้อมูลเท่านั้น
summary แสดงผลเฉพาะกฎที่เลือก พร้อม `selected_rules` และ `skipped_rules` ใน summary.json กฎที่ไม่ได้เลือกไม่ถูกนับเป็น Pass
log แสดงเลขข้อจริงและจำนวนกฎที่เลือก เปอร์เซ็นต์ช่วงตรวจ Rule คิดจากจำนวนกฎที่เลือก

ระหว่างรัน หน้าจอและ `run.log` แสดง `[Overall ...%]` ตามขั้นตอน ได้แก่ อ่านข้อมูล 10–25%, ตรวจ Rule 1–14 ที่ 25–75%, ตรวจไฟล์ต้นทางและสร้างรายงาน 75–98% และเขียนสรุปเสร็จที่ 100%
แต่ละ Rule แสดงตอนเริ่ม ตอนจบ เวลาที่ใช้ และจำนวน Error / Review / Warning เปอร์เซ็นต์รวมเป็นสัดส่วนขั้นตอน ไม่ใช่เวลาโดยประมาณหรือสัดส่วนแถวทั้งหมด และ 100% หมายถึงรันเสร็จ ไม่ได้หมายถึงทุกกฎผ่าน
งาน query ข้อ 12–14 แสดงเปอร์เซ็นต์ย่อยจากคู่ข้อมูลหรือ SKU ที่ query เสร็จต่อจำนวนทั้งหมด ทุก 100 รายการ รวมรายการแรกและสุดท้าย ส่วนการอ่านไฟล์และสร้างรายงานแสดงจำนวนแถวที่ดำเนินการแล้ว การตรวจรายงานแสดงเปอร์เซ็นต์ต่อชีต

```powershell
& ".\run_check.cmd" --input-dir "..\..\export\30102026110649\xlsx"
```

คำสั่งนี้อ่านไฟล์ PO, POP, Variant, Characteristics และ Meta ในโฟลเดอร์ย่อยของ `xlsx`
แล้วตรวจตามกฎ 1–14 ใน `RULES_TH.md` โดยใช้รายการยกเว้นและระดับความรุนแรงจาก `config.json`

สำหรับ `Char_Value` ถ้าไม่มีไฟล์ XLSX โปรแกรมจะอ่าน CSV จาก:

```text
export\30102026110649\csv\Product Offer\PO_Char_Value_30102026110649.csv
```

รอจนโปรแกรมแสดงสรุป `Rule 1` ถึง `Rule 14` และกลับมาที่บรรทัด `PS ...>`
ถ้าโปรแกรมหยุดด้วยข้อผิดพลาดก่อนแสดงสรุปครบ ให้ดูขั้นตอนที่ 4
ระหว่างรันให้เก็บไฟล์ต้นทางไว้ที่เดิมและอย่าแก้ไขไฟล์เหล่านั้น

เมื่อใช้ข้อมูล export รอบใหม่ ให้เปลี่ยนเฉพาะ `30102026110649` ในคำสั่งเป็นชื่อโฟลเดอร์รอบนั้น
ใช้โฟลเดอร์ `xlsx` และ `csv` จาก export รอบเดียวกัน

## 3. เปิดผลตรวจ

ผลลัพธ์อยู่ในโฟลเดอร์ `results` ที่โฟลเดอร์หลักของโปรเจกต์ ระดับเดียวกับ `export`:

```text
results\check_<ชื่อโฟลเดอร์ต้นทาง>\
```

เปิดโฟลเดอร์ผลลัพธ์ได้ด้วย:

```powershell
explorer "..\..\results"
```

เลือกโฟลเดอร์ `check_...` ที่ตรงกับข้อมูลต้นทาง แล้วเปิดไฟล์ตามนี้:

| ไฟล์ | ใช้ดูอะไร |
| --- | --- |
| `summary.txt` | สรุปผลกฎ 1–14 และจำนวน Error / Review / Warning |
| `Result_check_PO_POP_01-14_ErrorOnly_*.xlsx` | รายละเอียดรายการที่เป็น Error |
| `Result_Review_Warning_*.xlsx` | รายการที่ต้องพิจารณาหรือเป็นคำเตือน มีเฉพาะเมื่อพบรายการเหล่านี้ |
| `summary.json` | จำนวนข้อมูลที่อ่าน สถิติ และไฟล์ต้นทางที่ใช้จริง รวมข้อมูล fallback |
| `run.log` | ลำดับการทำงานและข้อความผิดพลาด |

รายงาน Excel ทั้ง Error และ Review/Warning แยกชีต `Rule 1` ถึง `Rule 14`
แต่ละชีตเก็บได้ไม่เกิน 1,000,000 แถวข้อมูล ไม่นับหัวตาราง เมื่อเกินจะสร้างชีตต่อ เช่น `Rule 10 2 (Errors 1000000)` หรือ `Rule 7 2` ในรายงาน Review/Warning พร้อมหัวตารางและตัวกรองใหม่
ใช้ขีดจำกัดเดียวกันกับ `Input Issues`, `All`, `Char duplicate detail` และ `Rule 9 Sources` โดยไม่ตัดข้อมูลทิ้ง
ปรับจำนวนแถวต่อชีตได้ตั้งแต่ 1 ถึง 1,048,575 เช่น:

```powershell
& ".\product_catalog\For Check\run_check.cmd" "30102026110649" --report-rows-per-sheet 50000
```

ตัวอย่างนี้รันจากโฟลเดอร์หลักของโปรเจกต์ การแบ่งชีตลดขนาดของแต่ละชีต แต่ข้อมูลทั้งหมดในไฟล์ยังเท่าเดิม และต้องรันใหม่เพื่อสร้างรายงานตามขีดจำกัดใหม่
คอลัมน์ `Reason` อธิบายสิ่งที่พบ เงื่อนไขที่ไม่ผ่านหรือยังสรุปไม่ได้ และจุดที่ควรตรวจต่อ
ใช้ร่วมกับคอลัมน์ ID, `Source File`, `Source Sheet`, `Source Row / Record` และ `Related Evidence` เพื่อค้นข้อมูลต้นทาง
การเทียบข้อมูลเป็นแบบตรงตัว แยกตัวพิมพ์ใหญ่–เล็ก และไม่ตัดช่องว่าง
โดยข้อย่อย 9.1–9.6 อยู่รวมใน `Rule 9` สร้างเฉพาะชีตที่มี Error หรือ Review/Warning ในรายงานนั้น
ไม่สร้างชีต `PASS` หรือชีตหลักฐานที่ไม่มีข้อมูล หากไม่มีรายการตรงกับประเภทรายงานเลย จะไม่สร้างไฟล์ XLSX ของประเภทนั้น
ชีตที่มีรายการ Error หรือ Review/Warning ใช้แท็บสีแดง
ชีตของกฎที่มี Error จะระบุจำนวนแถวต่อท้าย เช่น `Rule 7 (Errors 96)` โดยไม่นับหัวตาราง
หากข้อความยาวจนแบ่งเป็นหลายแถว ให้นับทุกแถวที่เขียนจริงในชีตนั้น ส่วนชีตหลักฐาน `Rule 9 Sources` ไม่รวมในจำนวนนี้
ดูผลครบทุกกฎ รวมกฎที่ผ่านได้ใน `summary.txt` และ `summary.json`
หลักฐานแถวต้นทางของข้อ 9.4 อยู่ในชีต `Rule 9 Sources` หากมีรายการ

ข้อ 10 แสดง Product Offer ID ที่พบแถวซ้ำในชีต `All` และทุกแถวที่ซ้ำในชีต `Char duplicate detail` เรียงกลุ่มตาม Product Offer ID พร้อมข้อมูลต้นทางทั้งแปดคอลัมน์
ปัญหาข้อมูลต้นทางแยกอยู่ในชีต `Input Issues` หากพบ

สถานะในสรุปมีความหมายดังนี้:

- `PASS`: กฎนั้นไม่มี Error และไม่มี Review ให้ดู Warning ที่อาจมีประกอบด้วย
- `FAIL`: กฎนั้นพบ Error ให้เปิดรายงาน Error ดูรายละเอียด
- `INCOMPLETE`: กฎนั้นมี Review ที่ต้องตรวจต่อ ยังสรุปว่าผ่านไม่ได้

การตรวจครบทุกกฎไม่ได้หมายความว่าข้อมูลต้องผ่านทุกกฎ ต้องอ่านผลสรุปด้วย

## 4. ถ้าไม่พบ XLSX หรืออ่าน XLSX ไม่สำเร็จ

ทุกชีตจะค้น XLSX ก่อน หากไม่พบไฟล์ จะค้น CSV ชื่อเดียวกันในโฟลเดอร์ย่อยของ `csv` ของรอบเดียวกันโดยตรง รวมถึงชีต Product_Variants, Variant_ProductOffering_Price และ Channel รองรับทั้งรอบที่มี XLSX ผสม CSV และรอบที่มีเฉพาะ CSV หากไม่พบทั้งสองรูปแบบจะหยุดพร้อมแจ้งข้อผิดพลาด

หากพบ XLSX แต่อ่านไม่ได้หรือไม่พบชีต โปรแกรมจะค้น CSV ชื่อเดียวกันในโฟลเดอร์ย่อยเดียวกันของ `csv` ก่อน โดยไม่เชื่อมฐานข้อมูล หากไม่พบ CSV โดยตรง จึงค้น mapping จาก `UAT_CPC.table_mapping`
ด้วย `EXCEL File` และ `EXCEL SHEET NAME` ผ่าน connection ใน `product_catalog\.env`
แล้วค้นหา CSV ในโฟลเดอร์ `csv` ระดับเดียวกับ `xlsx`

การอ่าน CSV ชื่อเดียวกันโดยตรงไม่ต้องเชื่อมฐานข้อมูล ทั้งกรณีไม่มี XLSX และกรณีอ่าน XLSX ไม่สำเร็จ เฉพาะการค้น mapping สำรองเท่านั้นที่ต้องเชื่อมฐานข้อมูลและมี ODBC Driver ที่ตรงกับ `DB_DRIVER` ใน `.env`
ตรวจการเชื่อมต่อแยกได้ด้วย:

```powershell
& ".\run_check.cmd" --check-connection
```

คำสั่งนี้ตรวจเฉพาะ connection ไม่ได้ตรวจกฎ 1–14
หาก fallback ไม่สำเร็จ โปรแกรมจะหยุด ให้เปิด `FAILED.json` และ `run.log` ในโฟลเดอร์ผลลัพธ์รอบนั้น
หากเลือกไฟล์ต้นทางไม่ได้ตั้งแต่แรก ข้อผิดพลาดจะแสดงใน PowerShell และอาจยังไม่มีโฟลเดอร์ผลลัพธ์

## คำสั่งเสริมที่ไม่ใช่การตรวจข้อมูลจริง

หากต้องการดูรายชื่อไฟล์ที่จะใช้ก่อน โดยยังไม่อ่านข้อมูลมาตรวจ:

```powershell
& ".\run_check.cmd" --input-dir "..\..\export\30102026110649\xlsx" --list-inputs
```

ส่วนคำสั่งนี้เป็นการทดสอบโค้ดด้วยข้อมูลจำลอง ไม่ได้ตรวจข้อมูล export ของคุณ:

```powershell
py -m unittest discover -s . -p test_validator.py -v
```

หากต้องการตรวจข้อมูลจริงครบกฎ 1–14 ให้ใช้คำสั่งในขั้นตอนที่ 2

ข้อ 12 ใช้ฐานข้อมูลจาก `product_catalog/.env` หรือ `--env` เพื่ออ่าน View `vw_catalog_offer_specification_characteristic` แม้รันจาก export หากเชื่อมต่อหรือ query ไม่สำเร็จจะแสดง Review และยังตรวจข้อนี้ไม่ครบ ดูรายละเอียดใน `RULES_TH.md`

ข้อ 13 ใช้ฐานข้อมูลเดียวกันอ่าน `PRODUCT_MST` ตาม `matCode = MAT_CODE` แล้วเทียบ commercialName กับ COMMERCIAL_NAME และ sapDescriptionEng/sapDescriptionTha กับ SAP_DESCRIPTION โดย Excel เริ่มแถว 6 ส่วน CSV เริ่มถัดจากหัวตาราง ผลแสดงใน `Rule 13` เฉพาะเมื่อมี Error หรือ Review

ข้อ 14 รวม Char ของ Variant และ Onetime POP เทียบสิบคอลัมน์ใน PRODUCT_MST และใช้ PRODUCT_ID + price_group ตรวจ INC_VAT จาก PRICE_MST เทียบกับ price_value ของ POP ต้องมีคอลัมน์ price_value ใน Product Offer Price รองรับเซลล์ราคาแบบตัวเลขใน Excel กฎนี้บังคับ PRODUCT_MST หนึ่งแถวต่อ SKU และไม่ใช้การเลือกแถวล่าสุดแบบข้อ 13 ผลอยู่ในชีต `Rule 14` โดยใช้การแบ่งชีตและแสดงเฉพาะรายการปัญหาเช่นเดียวกับข้ออื่น
