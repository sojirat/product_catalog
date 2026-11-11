# วิธีรันตรวจข้อมูล PO/POP ข้อ 1–15

เลือกอ่านเฉพาะหมวดของระบบที่ใช้ ทุกคำสั่งรันจากโฟลเดอร์หลักของโปรเจกต์ที่มี `Makefile`, `export` และโฟลเดอร์ `product_catalog`

ตัวอย่างใช้รอบ export `05112026131200` ให้เปลี่ยนเป็นชื่อรอบที่ต้องการ โดยไม่ต้องใส่ `export/` หรือ `/xlsx` รายละเอียดเงื่อนไขตรวจและ exclude list อยู่ใน [RULES_TH.md](RULES_TH.md)

## รันด้วย Mac

### 1. เตรียมก่อนรันครั้งแรก

เปิด Terminal แล้วเข้าโฟลเดอร์โปรเจกต์ เปลี่ยน path ให้ตรงกับเครื่อง:

```sh
cd "/path/to/product_catalog"
make setup-check
```

หากมี `.venv` และติดตั้ง dependencies ครบแล้ว ให้ข้าม `make setup-check` คำสั่ง make ใช้ Python จาก `.venv` ให้อัตโนมัติ ไม่ต้อง activate

เตรียมข้อมูลตามโหมดที่ใช้:

- **Database:** ตั้งค่าใน `product_catalog/.env` และติดตั้ง ODBC Driver ให้ตรงกับ `DB_DRIVER` หากเชื่อมต่อไม่ได้ โปรแกรมจะใช้ CSV ใน `Database/` แทน
- **CSV ใน Database:** วาง CSV ของ table/view ใน `Database/` ที่ root หากอ่านข้อมูลหลักทั้งหมดจาก CSV ต้องมี `template_mapping.csv` และไฟล์ที่ mapping ระบุด้วย ดู [วิธีเตรียม CSV](../../Database/README.md)
- **Export:** เก็บ `xlsx/` และ `csv/` ของรอบเดียวกันใน `export/<ชื่อรอบ>/` โปรแกรมอ่าน Excel ก่อนและใช้ CSV แทนเมื่อจำเป็น

### 2. เลือกคำสั่งตรวจ

```sh
# ตรวจทุกข้อ 1–15 ด้วย database
make check-db

# ตรวจทุกข้อ 1–15 ด้วย CSV ใน Database โดยไม่เชื่อมฐานข้อมูล
make check-db CHECK_ARGS="--csv"

# ตรวจหลายข้อด้วย database
make check-db CHECK_ARGS="--rules 7 14 15"

# ตรวจหลายข้อด้วย CSV ใน Database
make check-db CHECK_ARGS="--csv --rules 7 14 15"
```

แม้ชื่อคำสั่งเป็น `check-db` แต่เมื่อใส่ `--csv` จะใช้ CSV แทน ไม่เปิดการเชื่อมต่อฐานข้อมูล

เปลี่ยนเลขหลัง `--rules` เป็นข้อที่ต้องการ โดยคั่นด้วยช่องว่าง รองรับข้อ 1 ถึง 15 และข้อ 9 รวมข้อย่อย 9.1–9.6 หากไม่ใส่ `--rules` จะตรวจทุกข้อ

### 3. ตรวจจากไฟล์ export

```sh
# ตรวจรอบที่เลือก และใช้ CSV ใน Database แทนการเรียกฐานข้อมูล
make check INPUT_DIR="05112026131200" CHECK_ARGS="--csv"

# ตรวจเฉพาะข้อ 15 หรือหลายข้อ
make check INPUT_DIR="05112026131200" CHECK_ARGS="--csv --rules 15"
make check INPUT_DIR="05112026131200" CHECK_ARGS="--csv --rules 14 15"

# ตรวจ export รอบล่าสุด และเรียกฐานข้อมูลสำหรับข้อมูลอ้างอิง
make check

# ตรวจ export รอบล่าสุด และใช้ CSV สำหรับข้อมูลอ้างอิง
make check CHECK_ARGS="--latest-export ./export --csv"
```

เมื่อระบุรอบ export ร่วมกับ `--csv` ข้อมูลตั้งต้นยังอ่าน Excel ในรอบนั้นก่อน ส่วน `--csv` ใช้แทนการเรียกฐานข้อมูล ไม่ได้บังคับให้ข้อมูลตั้งต้นทั้งหมดอ่านจาก CSV

หากไม่ระบุ `INPUT_DIR` จะเลือกรอบล่าสุดตามชื่อโฟลเดอร์รูปแบบ `DDMMYYYYHHMMSS` ใน `export/` ข้อ 15 ต้องใช้เพียง Variant และข้อมูลอ้างอิง PRODUCT_MST/PRICE_MST ไม่ต้องมี Char_Value เมื่อเลือกตรวจเฉพาะข้อ 15

### 4. เปิดผลตรวจ

ผลจาก export อยู่ที่ `results/check_<ชื่อรอบ>/` ส่วนโหมด database หรือ CSV ที่ไม่ระบุ export อยู่ที่ `results/run_<วันเวลาที่รัน>/`

```sh
open results
```

| ไฟล์ | ใช้ดูอะไร |
|---|---|
| `summary.txt` | สรุปกฎที่เลือกและจำนวน Error / Review / Warning เริ่มอ่านไฟล์นี้ก่อน |
| `Result_check_PO_POP_01-15_ErrorOnly_*.xlsx` | รายละเอียด Error แยกตาม Rule |
| `Result_Review_Warning_*.xlsx` | รายการ Review และ Warning |
| `Result_Rule7_NoMainModel_*.xlsx` | Variant ที่ผ่านข้อ 7 เพราะ MAIN_MODEL ไม่มีข้อมูล |
| `summary.json` | จำนวนข้อมูล, coverage, วันที่ตรวจ และ SHA-256 ของไฟล์ต้นทาง |
| `config_used.json` | Config และ exclude list ที่ใช้จริง |
| `run.log` / `FAILED.json` | ลำดับการทำงาน / เหตุที่รอบตรวจหยุดก่อนเสร็จ |

สร้างรายงาน Excel เฉพาะเมื่อมีรายการของประเภทนั้น หากไม่มี Error จะไม่มี Error Report เมื่อตรวจ export รอบเดิมซ้ำ รายงาน Excel แยกตามเวลา ส่วน summary และ log เป็นรอบล่าสุด

`PASS` คือไม่มี Error หรือ Review, `FAIL` คือพบ Error, `INCOMPLETE` คือมี Review ที่ยังต้องตรวจต่อ เปอร์เซ็นต์ 100% หมายถึงรันเสร็จ ไม่ได้หมายถึงข้อมูลผ่านทุกกฎ

### 5. คำสั่งเสริมและการแก้ปัญหา

```sh
# ดูรายชื่อไฟล์ก่อนตรวจ
make check INPUT_DIR="05112026131200" CHECK_ARGS="--list-inputs"

# ทดสอบฐานข้อมูลจริง ไม่ใช้ CSV fallback
make check-connection

# เลือกโฟลเดอร์ CSV อื่น
make check-db CHECK_ARGS="--csv --database-dir /path/to/Database --rules 15"

# จำกัดแถวต่อชีตในรายงาน ไม่ตัดข้อมูลทิ้ง
make check INPUT_DIR="05112026131200" CHECK_ARGS="--csv --report-rows-per-sheet 50000"

# ดูตัวเลือกทั้งหมด / ทดสอบโค้ดด้วยข้อมูลจำลอง
make check CHECK_ARGS="--help"
make check-test
```

หากขึ้น `Expected exactly one ...; found 0` แสดงว่าไม่พบไฟล์ที่กฎที่เลือกต้องใช้ ให้ตรวจ path ที่ข้อความระบุ เช่น `PO_Char_Value_*.csv` หากพบหลายไฟล์โปรแกรมจะหยุดเพื่อไม่เดาไฟล์ที่จะใช้

เมื่อ Excel อ่านไม่ได้ โปรแกรมจะหา CSV ชื่อเดียวกันใน export รอบนั้นก่อน แล้วหาไฟล์ตาม prefix ของข้อมูลชนิดเดียวกันที่มีเพียงไฟล์เดียว หากยังไม่พบจึงใช้ `table_mapping` ซึ่งอ่านจาก CSV เมื่อใช้ `--csv` อย่านำข้อมูลคนละรอบมาแทนโดยไม่ตรวจสอบ

หาก CSV อ้างอิงหายหรือคอลัมน์ไม่ครบ อาจเกิด Review หรือหยุดรอบตรวจ ให้ดู `run.log` และ `FAILED.json` หากมี ข้อผิดพลาดก่อนเริ่มรันอาจยังไม่มีโฟลเดอร์ผลตรวจ

ข้อ 15 ใช้วันรันตามเวลาไทย และถือ EXPIRE_DATE วันที่ `1900-01-01` เป็นไม่มีวันหมดอายุทั้งสินค้าและราคา ดูคอลัมน์ที่ต้องใช้ใน [RULES_TH.md](RULES_TH.md)

## รันด้วย Windows

### 1. เตรียมก่อนรันครั้งแรก

เปิด PowerShell แล้วเข้าโฟลเดอร์หลักของโปรเจกต์:

```powershell
cd "C:\Users\waree\OneDrive\Documents\GitHub\product_catalog"
```

หากเคยใช้ `run_check.cmd` ได้แล้ว ให้ข้ามการติดตั้ง หากยังไม่มี Python ให้ติดตั้งและเพิ่มใน PATH แล้วติดตั้ง dependencies ด้วย Python ตัวที่ใช้รัน:

```powershell
python --version
python -m pip install -r ".\product_catalog\For Check\requirements.txt"
```

`run_check.cmd` เลือก Python runtime ที่ตั้งไว้ในไฟล์ก่อน หากไม่พบจึงใช้ `python` ใน PATH หากแจ้งว่าไม่มีโมดูล ให้ติดตั้ง dependencies ด้วย Python ตัวเดียวกับที่ `run_check.cmd` เลือก

เตรียมข้อมูลตามโหมดที่ใช้:

- **Database:** ตั้งค่าใน `product_catalog/.env` และติดตั้ง ODBC Driver ให้ตรงกับ `DB_DRIVER` หากเชื่อมต่อไม่ได้ โปรแกรมจะใช้ CSV ใน `Database/` แทน
- **CSV ใน Database:** วาง CSV ของ table/view ใน `Database/` ที่ root หากอ่านข้อมูลหลักทั้งหมดจาก CSV ต้องมี `template_mapping.csv` และไฟล์ที่ mapping ระบุด้วย ดู [วิธีเตรียม CSV](../../Database/README.md)
- **Export:** เก็บ `xlsx/` และ `csv/` ของรอบเดียวกันใน `export/<ชื่อรอบ>/` โปรแกรมอ่าน Excel ก่อนและใช้ CSV แทนเมื่อจำเป็น

### 2. เลือกคำสั่งตรวจ

```powershell
# ตรวจทุกข้อ 1–15 ด้วย database
& ".\product_catalog\For Check\run_check.cmd" --database

# ตรวจทุกข้อ 1–15 ด้วย CSV ใน Database โดยไม่เชื่อมฐานข้อมูล
& ".\product_catalog\For Check\run_check.cmd" --csv

# ตรวจหลายข้อด้วย database
& ".\product_catalog\For Check\run_check.cmd" --database --rules 7 14 15

# ตรวจหลายข้อด้วย CSV ใน Database
& ".\product_catalog\For Check\run_check.cmd" --csv --rules 7 14 15
```

เปลี่ยนเลขหลัง `--rules` เป็นข้อที่ต้องการ โดยคั่นด้วยช่องว่าง รองรับข้อ 1 ถึง 15 และข้อ 9 รวมข้อย่อย 9.1–9.6 หากไม่ใส่ `--rules` จะตรวจทุกข้อ

### 3. ตรวจจากไฟล์ export

```powershell
# ตรวจรอบที่เลือก และใช้ CSV ใน Database แทนการเรียกฐานข้อมูล
& ".\product_catalog\For Check\run_check.cmd" "05112026131200" --csv

# ตรวจเฉพาะข้อ 15 หรือหลายข้อ
& ".\product_catalog\For Check\run_check.cmd" "05112026131200" --csv --rules 15
& ".\product_catalog\For Check\run_check.cmd" "05112026131200" --csv --rules 14 15

# ตรวจ export รอบล่าสุด และเรียกฐานข้อมูลสำหรับข้อมูลอ้างอิง
& ".\product_catalog\For Check\run_check.cmd"

# ตรวจ export รอบล่าสุด และใช้ CSV สำหรับข้อมูลอ้างอิง
& ".\product_catalog\For Check\run_check.cmd" --latest-export ".\export" --csv
```

เมื่อระบุรอบ export ร่วมกับ `--csv` ข้อมูลตั้งต้นยังอ่าน Excel ในรอบนั้นก่อน ส่วน `--csv` ใช้แทนการเรียกฐานข้อมูล ไม่ได้บังคับให้ข้อมูลตั้งต้นทั้งหมดอ่านจาก CSV

คำสั่งที่ไม่ระบุรอบจะเลือกรอบล่าสุดตามชื่อโฟลเดอร์รูปแบบ `DDMMYYYYHHMMSS` ใน `export/` ส่วน `--csv` เพียงตัวเดียวจะอ่านข้อมูลหลักจาก Database จึงต้องใช้ `--latest-export` หรือระบุรอบหากต้องการอ่าน export

ข้อ 15 ต้องใช้เพียง Variant และข้อมูลอ้างอิง PRODUCT_MST/PRICE_MST ไม่ต้องมี Char_Value เมื่อเลือกตรวจเฉพาะข้อ 15

### 4. เปิดผลตรวจ

ผลจาก export อยู่ที่ `results\check_<ชื่อรอบ>\` ส่วนโหมด database หรือ CSV ที่ไม่ระบุ export อยู่ที่ `results\run_<วันเวลาที่รัน>\`

```powershell
explorer ".\results"
```

| ไฟล์ | ใช้ดูอะไร |
|---|---|
| `summary.txt` | สรุปกฎที่เลือกและจำนวน Error / Review / Warning เริ่มอ่านไฟล์นี้ก่อน |
| `Result_check_PO_POP_01-15_ErrorOnly_*.xlsx` | รายละเอียด Error แยกตาม Rule |
| `Result_Review_Warning_*.xlsx` | รายการ Review และ Warning |
| `Result_Rule7_NoMainModel_*.xlsx` | Variant ที่ผ่านข้อ 7 เพราะ MAIN_MODEL ไม่มีข้อมูล |
| `summary.json` | จำนวนข้อมูล, coverage, วันที่ตรวจ และ SHA-256 ของไฟล์ต้นทาง |
| `config_used.json` | Config และ exclude list ที่ใช้จริง |
| `run.log` / `FAILED.json` | ลำดับการทำงาน / เหตุที่รอบตรวจหยุดก่อนเสร็จ |

สร้างรายงาน Excel เฉพาะเมื่อมีรายการของประเภทนั้น หากไม่มี Error จะไม่มี Error Report เมื่อตรวจ export รอบเดิมซ้ำ รายงาน Excel แยกตามเวลา ส่วน summary และ log เป็นรอบล่าสุด

`PASS` คือไม่มี Error หรือ Review, `FAIL` คือพบ Error, `INCOMPLETE` คือมี Review ที่ยังต้องตรวจต่อ เปอร์เซ็นต์ 100% หมายถึงรันเสร็จ ไม่ได้หมายถึงข้อมูลผ่านทุกกฎ

### 5. คำสั่งเสริมและการแก้ปัญหา

```powershell
# ดูรายชื่อไฟล์ก่อนตรวจ
& ".\product_catalog\For Check\run_check.cmd" "05112026131200" --list-inputs

# ทดสอบฐานข้อมูลจริง ไม่ใช้ CSV fallback
& ".\product_catalog\For Check\run_check.cmd" --check-connection

# เลือกโฟลเดอร์ CSV อื่น
& ".\product_catalog\For Check\run_check.cmd" --csv --database-dir "D:\ReferenceData" --rules 15

# จำกัดแถวต่อชีตในรายงาน ไม่ตัดข้อมูลทิ้ง
& ".\product_catalog\For Check\run_check.cmd" "05112026131200" --csv --report-rows-per-sheet 50000

# ดูตัวเลือกทั้งหมด
& ".\product_catalog\For Check\run_check.cmd" --help
```

หากขึ้น `Expected exactly one ...; found 0` แสดงว่าไม่พบไฟล์ที่กฎที่เลือกต้องใช้ ให้ตรวจ path ที่ข้อความระบุ เช่น `PO_Char_Value_*.csv` หากพบหลายไฟล์โปรแกรมจะหยุดเพื่อไม่เดาไฟล์ที่จะใช้

เมื่อ Excel อ่านไม่ได้ โปรแกรมจะหา CSV ชื่อเดียวกันใน export รอบนั้นก่อน แล้วหาไฟล์ตาม prefix ของข้อมูลชนิดเดียวกันที่มีเพียงไฟล์เดียว หากยังไม่พบจึงใช้ `table_mapping` ซึ่งอ่านจาก CSV เมื่อใช้ `--csv` อย่านำข้อมูลคนละรอบมาแทนโดยไม่ตรวจสอบ

หาก CSV อ้างอิงหายหรือคอลัมน์ไม่ครบ อาจเกิด Review หรือหยุดรอบตรวจ ให้ดู `run.log` และ `FAILED.json` หากมี ข้อผิดพลาดก่อนเริ่มรันอาจยังไม่มีโฟลเดอร์ผลตรวจ

ข้อ 15 ใช้วันรันตามเวลาไทย และถือ EXPIRE_DATE วันที่ `1900-01-01` เป็นไม่มีวันหมดอายุทั้งสินค้าและราคา ดูคอลัมน์ที่ต้องใช้ใน [RULES_TH.md](RULES_TH.md)
