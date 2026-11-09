# CSV สำหรับใช้แทนฐานข้อมูล

วางไฟล์ UTF-8 ที่มีหัวคอลัมน์ในโฟลเดอร์นี้ ชื่อไฟล์รองรับ `<ชื่อ table หรือ view>.csv` และ `<ชื่อ table หรือ view>_<YYYYMMDDHHMM>.csv` หรือ timestamp ที่มีวินาที `YYYYMMDDHHMMSS` เช่น `PRODUCT_MST_202611091058.csv` ไม่ใส่ schema

โปรแกรมเลือกชื่อที่ไม่มี timestamp ก่อน หากไม่มีจึงเลือก timestamp ล่าสุดจากชื่อไฟล์ ไม่ใช้เวลาแก้ไขไฟล์ หากเวลาเท่ากันเลือกชื่อที่ระบุวินาที ใช้กฎเดียวกันกับไฟล์ mapping และทุก table/view ไม่ค้นโฟลเดอร์ย่อยหรือรวมหลายรอบเข้าด้วยกัน

หากอ่านข้อมูลหลักจาก CSV ด้วย ให้มี `template_mapping.csv` พร้อมคอลัมน์ mapping เดิม ได้แก่ `EXCEL SHEET NAME`, `DATABASE NAME`, `UNOIN`, `EXCEL File`, `isActive` และ CSV ของ table/view ที่ mapping ระบุ ค่า `isActive` ที่เป็น `0` หรือ `false` จะไม่ถูกใช้

แถวแรกเป็นชื่อคอลัมน์ตามฐานข้อมูล ค่าว่างเป็นข้อความว่าง ส่วน SQL NULL ให้เขียน `\N` เก็บเลขศูนย์นำหน้าและช่องว่างตามข้อมูลจริง เวลาอ้างอิงข้อ 13 ใช้รูปแบบ ISO และ timezone เดียวกัน พร้อมคอลัมน์ `system_updated_at`, `system_created_at`, `PRODUCT_ID` ที่เป็นตัวเลข

โปรแกรมอ่านเฉพาะไฟล์ที่กฎที่เลือกต้องใช้ หากไฟล์หรือคอลัมน์ไม่ครบจะรายงานว่าตรวจไม่สำเร็จ ไม่ถือว่าผ่าน

ตัวอย่างตรวจทุกกฎจาก root ของโปรเจกต์:

```powershell
& ".\product_catalog\For Check\run_check.cmd" --csv
```

ดูรายละเอียดใน [RULES_TH.md](../product_catalog/For%20Check/RULES_TH.md) และ [STEP_RUN_TH.md](../product_catalog/For%20Check/STEP_RUN_TH.md)
