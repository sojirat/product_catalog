# กฎที่ใช้ในโปรแกรม รุ่น 1.2.0

เอกสารนี้ยึดเลขข้อใน Prompt ฉบับรวมในแชต และอัปเดตข้อ 9.4 เป็น Error
ไม่ใช้เลขข้อจากชุดตรวจอื่นที่ชื่อคล้ายกัน

| ข้อ | ตรวจอะไร | Error |
|---|---|---|
| 1 | ทุก POP ใน POP master ต้องมีใน Meta POP `POP_metaExt_productInfo` | ไม่พบ POP |
| 2 | Variant.sku → Meta.matCode; Variant ID → link; POP ทั้งสองฝั่งต้องมีอย่างน้อยหนึ่งรายการตรงกัน | ไม่พบ SKU, ไม่พบ link หรือไม่มี POP ตรงกัน |
| 3 | ทุกแถว Meta ย้อน POP → linked Variant ทั้งหมด → SKU | ไม่มี link, มี Variant อ้างอิงที่หาไม่พบ หรือจำนวนแถว Variant ที่ SKU ตรง matCode ไม่เท่ากับหนึ่ง |
| 4 | `POP ID + Char Name` ใน Characteristics for Price | มากกว่าหนึ่งแถว รายงานทุกแถวในกลุ่ม |
| 5 | ทุก master POP ต้องมี `unit_name-mh_mg00562` ที่มีค่า | หายหรือ value ว่าง |
| 6 | model ต่อ POP และการค้นหา Char Name จาก model.value | model มากกว่าหนึ่งแถว หรือพบ Char Name เท่ากับ model.value มากกว่าหนึ่งแถว |
| 7 | main_model ใน POP ถ้าไม่มีค่าตรวจ PO สำรอง | ไม่มี PO, หลาย PO, ไม่พบ PO ใน Char_Value หรือ PO เป็น DEVICE แต่ไม่มี main_model ที่มีค่า |
| 8 | ทุกคู่ของ POP ต้องตรงกับ Char_Value ทั้ง PO, ID, Name, value ในแถวเดียวกัน | ไม่มี PO, หลาย PO หรือไม่พบแถวที่ตรงครบ |
| 9.1 | แยกรายการ comma ทั้งสอง Column แล้วจับคู่ตามลำดับ | จำนวนสมาชิกต่างกันหรือมีสมาชิกว่าง |
| 9.2 | ตรวจการอ้างอิงและความสอดคล้อง PO–Variant–POP | อ้างอิงหายหรือเจ้าของไม่สอดคล้อง |
| 9.3 | ทุกคู่ ID + value ที่ใช้ใน Variant/POP ต้องมีใน Char_Value ของ PO เดียวกัน | ไม่พบคู่ที่มีค่า |
| 9.4 | ย้อนทุกคู่ ID + value ที่ไม่ว่างใน Char_Value | ไม่มีการใช้ใน Variant หรือ POP ใดภายใต้ PO เดียวกัน |
| 9.5 | ตรวจ SKU ของกลุ่ม Variant ที่เชื่อม POP เดียวกัน | SKU ต่างกันผ่านด้านแยกแยะ Variant ห้าม Error เพียงเพราะ Characteristic เหมือนกัน |
| 9.6 | เทียบคู่ข้อมูลทั้งระดับ Variant และ POP ที่เชื่อมกัน | ID + value เดียวกันซ้ำทั้งสองระดับ |
| 10 | ตรวจแถวซ้ำใน Char_Value ภายใต้ Product Offer ID เดียวกัน | Characteristics ID + Characteristics Name + valueType + value ตรงกันมากกว่าหนึ่งแถว |

## ข้อ 2 และ 3

ข้อ 2 ทำตามลำดับการตรวจ และให้เหตุผลแรกที่ไม่ผ่านต่อแถว Variant
หลาย link หรือหลาย POP ต่อ matCode ยอมรับได้เมื่อมีอย่างน้อยหนึ่ง POP ตรงกัน
ข้อ 3 ใช้เงื่อนไขจำนวนแถวที่จับคู่ได้เท่ากับหนึ่งตาม Prompt ที่ตกลง
นับแถว Variant ต้นฉบับ ไม่ปล่อยให้ Join กับ link ซ้ำเพิ่มจำนวนเทียม
หาก Variant ID ที่ link อ้างอิงบางตัวหาย ต้องแจ้ง แม้ตัวอื่นจับคู่สำเร็จ

## ข้อ 6

เมื่อพบ model หนึ่งแถวและ value ไม่ว่าง ค้นหา Char Name เท่ากับ value ภายใน POP เดิม
พบศูนย์หรือหนึ่งแถวผ่าน พบมากกว่าหนึ่งแถวผิด
ถ้าไม่มี model หรือ value ว่าง ยังไม่มีเกณฑ์ตัดสินชัดเจน จึงเป็น Review และข้อ 6 ไม่แสดง Pass

## ข้อ 7

ตรวจ main_model ที่ POP ก่อน ถ้ามีค่าอย่างน้อยหนึ่งแถวถือว่าผ่านข้อนี้
มิฉะนั้นหา PO เดียวจาก Sheet Product Offer Price ในไฟล์ PO
หากมี `product_type-mh_mg00162 = DEVICE` ใน Char_Value ของ PO ต้องมี `main_model-mh_mg00554` ที่มีค่าอย่างน้อยหนึ่งแถว
PO ที่ไม่เป็น DEVICE ไม่บังคับ main_model ด้วย fallback นี้
POP ที่ไม่มี Characteristics for Price เลยเป็น Warning และยังตรวจ fallback ต่อ

## ข้อ 8

ใช้ Name ด้วย แตกต่างจากข้อ 9.3 ซึ่งใช้ ID + value
ไม่ใช้ valueType เป็นเงื่อนไข
Mapping หลายแถวแต่ PO เดียวกันเป็น Review เพราะเกณฑ์นี้ยังไม่ยืนยัน

## ข้อ 9

ค่าว่างใน Char_Value ไม่อยู่ในขอบเขตคู่ข้อมูลของข้อ 9 แต่ไม่ตัดออกจากการตรวจข้อ 7–8
ค่าว่างคือไม่มีค่าจริง ไม่แปลง whitespace ให้เป็นค่าว่าง
หนึ่งคู่ข้อ 9.4 คือ PO + Characteristics ID + value ไม่ซ้ำ การใช้ใน PO อื่นไม่นับ
SKU ต่างกันไม่ได้ยกเว้นข้อ 9.3/9.4 หรือการตรวจอ้างอิง
SKU เหมือนกันหรือว่างไม่เป็น Error อัตโนมัติ จัดเป็น Review เมื่อมีหลาย Variant ในกลุ่ม
กลุ่มหนึ่ง Variant ไม่มีคู่ให้เปรียบเทียบ SKU แยกนับใน coverage
ID เดียวแต่ value ต่างระหว่างสองระดับ หรือมีหลาย value ในระดับเดียวกัน เป็น Review จนกว่าจะยืนยันกฎ Override/หลายค่า

## ข้อ 10

อ่านชีต `Char_Value` ของ Product Offer หรือ CSV `PO_Char_Value` ผ่าน fallback เดียวกับข้ออื่น
ภายใน `Char Value.Product Offer ID` เดียวกัน ห้ามมีแถวที่ตรงกันครบทั้งสี่คอลัมน์มากกว่าหนึ่งแถว:

- `Char Value.Product Offer Characteristics ID`
- `Char Value.Product Offer Characteristics Name`
- `Char Value.valueType`
- `Char Value.value`

ตรวจเฉพาะแถวที่ `Char Value.value` มีค่า ข้ามแถวที่ value เป็นค่าว่าง
เปรียบเทียบตรงตัว ไม่ trim และแยกตัวพิมพ์ใหญ่เล็ก ไม่แปลง whitespace ให้เป็นค่าว่าง
Product Spec ID, Product Spec Name และ isDefault ไม่ใช่คีย์ตรวจซ้ำ แม้ต่างกันก็ยังผิดหากคีย์ตรงกันครบ
ใช้รายการ `exclude_po_ids` ตาม config เช่นเดียวกับกฎอื่น และต้องมีคอลัมน์ต้นทางครบทั้งแปดคอลัมน์
นับ Error ทุกแถวในกลุ่มที่ซ้ำ รวมแถวแรก

Error Report มีชีต `Rule 10` สำหรับรายละเอียดข้อผิดพลาด และเพิ่มชีตดังนี้:

- `All`: รายการ `Char Value.Product Offer ID` ที่ผิดข้อ 10 ไม่ซ้ำ เรียงตาม ID
- `Char duplicate detail`: ทุกแถวในกลุ่มที่ซ้ำ เรียงกลุ่มตาม `Char Value.Product Offer ID` พร้อมคอลัมน์ตามลำดับ ได้แก่ `Char Value.Product Offer ID`, `Char Value.Product Spec ID`, `Char Value.Product Spec Name`, `Char Value.Product Offer Characteristics ID`, `Char Value.Product Offer Characteristics Name`, `Char Value.valueType`, `Char Value.value`, `Char Value.isDefault`

## สรุปความครบถ้วน

ทุก Record ถูกอ่าน ไม่มี Sampling ข้อที่มี Review ยังคงแสดง `complete=false`
รายการ Review ไม่ถูกนับเป็น Error หรือ Pass โดยปริยาย
หนึ่งต้นเหตุอาจผิดหลายข้อ เช่น POP ไม่มี Characteristic ทำให้ข้อ 5 ผิดและข้อ 6 ยังตัดสินไม่ได้
ห้ามรวมจำนวน Error แล้วตีความเป็นจำนวน PO/POP ที่ไม่ซ้ำ
