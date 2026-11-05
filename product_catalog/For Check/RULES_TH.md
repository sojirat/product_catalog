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
| 6 | model ที่มีค่าใน POP แล้วตรวจ Variant ที่เชื่อมกัน | POP ไม่มีค่า model และทุก Variant ไม่มี model-mh_mg00556 |
| 7 | main_model ใน POP แล้วตรวจ Variant ก่อนตรวจ Char_Value ของ PO จาก Variant | ไม่พบ link/Variant หรือ Char_Value หรือ PO เป็น DEVICE แต่ยังไม่มี main_model ที่มีค่า |
| 8 | ทุกคู่ของ POP ต้องตรงกับ Char_Value ทั้ง PO, ID, Name, value ในแถวเดียวกัน | ไม่มี PO, หลาย PO หรือไม่พบแถวที่ตรงครบ |
| 9.1 | แยกรายการ comma ทั้งสอง Column แล้วจับคู่ตามลำดับ | จำนวนสมาชิกต่างกันหรือมีสมาชิกว่าง |
| 9.2 | ตรวจการอ้างอิงและความสอดคล้อง PO–Variant–POP | อ้างอิงหายหรือเจ้าของไม่สอดคล้อง |
| 9.3 | ทุกคู่ ID + value ที่ใช้ใน Variant/POP ต้องมีใน Char_Value ของ PO เดียวกัน | ไม่พบคู่ที่มีค่า |
| 9.4 | ย้อนทุกคู่ ID + value ที่ไม่ว่างใน Char_Value | ไม่มีการใช้ใน Variant หรือ POP ใดภายใต้ PO เดียวกัน |
| 9.5 | ตรวจ SKU ของกลุ่ม Variant ที่เชื่อม POP เดียวกัน | SKU ต่างกันผ่านด้านแยกแยะ Variant ห้าม Error เพียงเพราะ Characteristic เหมือนกัน |
| 9.6 | เทียบคู่ข้อมูลทั้งระดับ Variant และ POP ที่เชื่อมกัน | ID + value เดียวกันซ้ำทั้งสองระดับ |
| 10 | ตรวจแถวซ้ำใน Char_Value ภายใต้ Product Offer ID เดียวกัน | Characteristics ID + Characteristics Name + valueType + value ตรงกันมากกว่าหนึ่งแถว |
| 11 | price_group ของ Variant ต้องตรงกับ Channel ของ POP | ไม่มี link, กลุ่มหลาย POP มี priceType ผิดรูปแบบ, Channel ไม่ครบหนึ่งแถว หรือ price_group ไม่ตรง Channel |
| 12 | Resource Specification ที่มี value ของ PO ต้องพบใน View ตามคู่ offer_id + specification_id | PO เดียวเลือกหลาย Resource Specification หรือไม่พบคู่ใน View |
| 13 | เทียบ Meta POP กับ PRODUCT_MST ตาม matCode = MAT_CODE | matCode ว่าง, ไม่พบ MAT_CODE หรือชื่อไม่ตรง Product Master |
| 14 | รวม Char จาก Variant และ Onetime POP เทียบ Product Master และ Price Master | Char ไม่ตรง, Onetime POP หรือ PRODUCT_MST ไม่ครบหนึ่งแถว หรือราคาไม่ตรง |

## ข้อ 2 และ 3

ข้อ 2 ทำตามลำดับการตรวจ และให้เหตุผลแรกที่ไม่ผ่านต่อแถว Variant
หลาย link หรือหลาย POP ต่อ matCode ยอมรับได้เมื่อมีอย่างน้อยหนึ่ง POP ตรงกัน
ข้อ 3 ใช้เงื่อนไขจำนวนแถวที่จับคู่ได้เท่ากับหนึ่งตาม Prompt ที่ตกลง
นับแถว Variant ต้นฉบับ ไม่ปล่อยให้ Join กับ link ซ้ำเพิ่มจำนวนเทียม
หาก Variant ID ที่ link อ้างอิงบางตัวหาย ต้องแจ้ง แม้ตัวอื่นจับคู่สำเร็จ

## ข้อ 6

1. ตรวจ `model-mh_mg00556` ที่ POP ใน Characteristics for Price ถ้ามี value อย่างน้อยหนึ่งแถวถือว่าผ่าน แม้มีหลายแถว
2. ถ้าไม่มีแถวที่มีค่า ใช้ `Product Offer Price ID` ค้นหาในไฟล์ Product Offer Price ชีต `Variant_ProductOffering_Price` คอลัมน์ `variantProductOfferingPrice.productOfferingPrice`
3. นำ `variantProductOfferingPrice.variantId` ทั้งหมดที่ได้ ไปค้นหาในชีต `Product_Variants` คอลัมน์ `Product Variants.variantId` และตรวจทุกแถวที่พบ
4. แยก `Product Variants.specCharacteristics` ด้วย `,` แล้วค้นหาสมาชิกที่ตรงกับ `model-mh_mg00556` ทั้งตัว ถ้ามีอย่างน้อยหนึ่งแถวถือว่าผ่าน ถ้าทุกแถวไม่มี หรือไม่พบ Variant ที่ใช้ตรวจ ให้แจ้ง Error

ตัวอย่าง `Product Variants.specCharacteristics`:

```text
color-mh_mg00524,company-mh_mg00551,device_dummy-mh_mg00656,apple_watch_3_series-mh_mg00846,model-mh_mg00556,price_group-mh_mg00557
```

ตัวอย่างนี้ผ่านข้อ 6 เพราะมี `model-mh_mg00556` หลัง split ด้วย comma
ยกเลิกการตรวจจำนวนแถว model และการค้นหา Char Name จาก model.value ตามกฎเดิม

## ข้อ 7

1. ตรวจ `main_model-mh_mg00554` ที่ POP ใน Characteristics for Price ถ้ามี value อย่างน้อยหนึ่งแถวถือว่าผ่าน
2. ถ้าไม่มีแถวที่มีค่า ใช้ `Product Offer Price ID` ค้นหาในไฟล์ Product Offer Price ชีต `Variant_ProductOffering_Price` คอลัมน์ `variantProductOfferingPrice.productOfferingPrice`
3. นำ `variantProductOfferingPrice.variantId` ทั้งหมดที่ได้ ไปค้นหาในชีต `Product_Variants` คอลัมน์ `Product Variants.variantId` และตรวจทุกแถวที่พบ
4. แยก `Product Variants.specCharacteristics` ด้วย `,` แล้วค้นหาสมาชิกที่ตรงกับ `main_model-mh_mg00554` ทั้งตัว ถ้ามีอย่างน้อยหนึ่งแถวถือว่าผ่าน ตัวอย่างในข้อ 6 ไม่มีสมาชิกนี้ จึงต้องตรวจขั้นตอนถัดไป
5. ถ้าทุกแถวไม่มี ให้นำ `Product Variants.Product Id` ของทุก PO ที่พบ ไปค้นหาในชีต `Char_Value` คอลัมน์ `Char Value.Product Offer ID`
6. หาก PO นั้นมี `product_type-mh_mg00162 = DEVICE` ต้องมี `main_model-mh_mg00554` ที่มี value อย่างน้อยหนึ่งแถวใน Char_Value ของ PO เดียวกัน หากยังไม่มี ให้แจ้ง Error ตรวจแต่ละ PO แยกกันเมื่อพบหลาย PO

PO ที่ไม่เป็น DEVICE ไม่บังคับ main_model ด้วย fallback นี้
หากไม่พบ link, Variant ที่อ้างอิง หรือข้อมูล PO ใน Char_Value ให้แจ้ง Error
POP ที่ไม่มี Characteristics for Price เลยเป็น Warning และยังตรวจ fallback ต่อ
การเทียบ ID หลัง split เป็นแบบตรงตัว ไม่ค้นหาเพียงบางส่วนและไม่ตัดช่องว่าง

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

## ข้อ 11 ตรวจสอบว่า Price Type เลือก POP ถูกต้อง

ตรวจทีละแถวของไฟล์ Product Offer ชีต `Product_Variants` ตามลำดับดังนี้:

1. Split `Product Variants.specCharacteristics` ด้วย `,` แล้วค้นหาสมาชิก `price_group-mh_mg00557` แบบตรงตัว หากไม่มีให้ข้ามแถวนี้
2. จำ index ของสมาชิกที่พบ แล้ว split `Product Variants.value` ด้วย `,` เพื่อเลือกค่าที่ index เดียวกัน โดยเริ่มนับ index จาก 0 เช่น `color,price_group-mh_mg00557` คู่กับ `RED,EUP` จะได้ index 1 และค่า `EUP`
3. ใช้ `Product Variants.variantId` ค้นหาในชีต `Variant_ProductOffering_Price` คอลัมน์ `variantProductOfferingPrice.variantId` หากพบหนึ่งแถว ให้นำ POP ไปตรวจ priceType ก่อนตรวจ Channel หากพบมากกว่าหนึ่งแถว ให้นำ POP ID ทั้งหมดไปค้นในไฟล์ Product Offer Price ชีต `Product Offer Price` คอลัมน์ `Product Offer Price ID` โดยต้องพบข้อมูลของแต่ละ POP หนึ่งแถว และมี `priceType = Onetime` หนึ่ง POP ส่วน POP ที่เหลือทั้งหมดต้องเป็น `priceType = Pre-Booking` หากตรงรูปแบบนี้ ให้นำ POP ID ทุกตัวไปตรวจ Channel แยกกัน หากไม่ตรงให้แจ้ง Error รวมถึงกรณีไม่พบ POP, ข้อมูล POP ซ้ำ หรือ link อ้าง POP เดิมซ้ำ
4. นำ POP ID ทุกตัวไปค้นในไฟล์ Product Offer Price ชีต `Product Offer Price` คอลัมน์ `Product Offer Price ID` และเก็บ `priceType` ของแต่ละ POP หากไม่พบ POP หรือ priceType ว่าง ให้แจ้ง Error ว่า `POP ไม่มีข้อมูล priceType` ก่อนตรวจ Channel หากพบข้อมูล POP ซ้ำให้แจ้ง Error
5. นำ `variantProductOfferingPrice.productOfferingPrice` จากแถวนั้น ไปค้นหา `POP_ID` ในไฟล์ Product Offer Price ชีต `Channel` ต้องพบหนึ่งแถว ถ้าเกินหนึ่งแถวแจ้ง Error ว่า `POP มีมากกว่า 1 Channel`
6. ถ้า `ProductOfferPrice.Channel = All` ค่า price_group ที่เลือกต้องเป็น `EUP` และ `priceType` ของ POP ต้องเป็น `Onetime` หากไม่ตรงเงื่อนไขใดให้แจ้ง Error
7. ถ้า `ProductOfferPrice.Channel = Web Staff` ค่า price_group ที่เลือกต้องเป็น `STAFF` และ `priceType` ของ POP ต้องเป็น `Onetime` หากไม่ตรงเงื่อนไขใดให้แจ้ง Error
8. ถ้า `ProductOfferPrice.Channel = Web Pre-Booking` ค่า `priceType` ของ POP ต้องเป็น `Pre-Booking` หากตรงให้ผ่าน โดยไม่บังคับค่า price_group หากไม่ตรงให้แจ้ง Error

หากไม่มี link หรือไม่มี Channel ให้แจ้ง Error หากจำนวนสมาชิกของ specCharacteristics และ value ไม่เท่ากัน หรือค่า price_group ว่าง ให้แจ้ง Error
หากพบ price_group หลายตำแหน่ง ให้ตรวจค่าของทุกตำแหน่ง หาก Channel เป็นค่าอื่นนอกเหนือจากสามค่าที่กำหนด ให้เป็น Review
เทียบค่าตรงตัว แยกตัวพิมพ์ใหญ่เล็ก ไม่ตัดช่องว่าง ใช้รายการยกเว้น PO/POP ตาม config เช่นเดียวกับกฎอื่น

โหมด export อ่าน Channel จาก `xlsx/Product Offer Price/pop_channel_*.xlsx` ชีต `Channel` โดยต้องมีคอลัมน์ `POP_ID` และ `ProductOfferPrice.Channel`
หากไม่พบไฟล์ XLSX ให้ค้น CSV ชื่อเดียวกันในโฟลเดอร์ `csv` ของรอบ export เดียวกัน ทุกชีตใช้เงื่อนไขนี้ รวมถึง Product_Variants, Variant_ProductOffering_Price และ Channel หากพบ XLSX แต่อ่านหรือหาชีตไม่สำเร็จ ให้ใช้ CSV fallback ผ่าน mapping เดิม หากไม่พบทั้ง XLSX และ CSV ให้หยุดพร้อมแจ้งข้อผิดพลาด
โหมดไฟล์รวมอ่านชีต Channel จากไฟล์ `--pop` และโหมดฐานข้อมูลอ่านผ่าน template mapping
ผลตรวจอยู่ในชีต `Rule 11` ของรายงาน และแสดงใน summary เช่นเดียวกับข้ออื่น

## ข้อ 12 ตรวจสอบการเลือกใช้ Resource Specification ของ PO

อ่าน `Char_Value` จาก Product Offer หรือ CSV `PO_Char_Value` ผ่าน fallback เดิม แล้วตรวจตามลำดับ:

1. ข้าม PO ใน `exclude_po_ids` เลือกเฉพาะแถวที่ `Char Value.Product Spec ID` มีข้อความ `-rs_mg` และ `Char Value.value` ไม่ว่าง ไม่ trim ค่าและไม่แปลง whitespace ให้เป็นค่าว่าง
2. จัดกลุ่มตาม `Char Value.Product Offer ID` แถวที่เหลือของ PO เดียวกันต้องมี Product Spec ID เดียวกัน หากพบหลาย ID ให้แจ้ง Error `MULTIPLE_RESOURCE_SPEC` พร้อมรายการ ID ที่พบ
3. ใช้คู่ Product Offer ID + Product Spec ID ไม่ซ้ำ ไป query View `vw_catalog_offer_specification_characteristic` ใน schema จาก `.env` โดยเทียบ `offer_id` และ `specification_id` ด้วย SQL parameters ตรวจแต่ละคู่ครั้งเดียว แม้มี Characteristic หลายแถว
4. หากไม่พบคู่ ให้แจ้ง Error `INVALID_RESOURCE_SPEC` ว่า `Resource Specification ที่เลือกไม่ถูกต้อง` หนึ่งรายการต่อคู่ พร้อม PO ID, Product Spec ID ใน Related Evidence, แถวต้นทางตัวอย่าง และจำนวนแถวต้นทางใน Source Occurrence Count หากพบถือว่าผ่าน

ใช้ฐานข้อมูลจาก `--env` หรือ `product_catalog/.env` ทั้งโหมด export ไฟล์รวม และโหมดฐานข้อมูล
หากไม่มีคู่ที่ต้องตรวจ ไม่เชื่อมฐานข้อมูล หาก query หรือเชื่อมต่อไม่สำเร็จให้เป็น Review และ `complete=false` ไม่สรุปว่าเลือก Resource Specification ผิด
ผลอยู่ในชีต `Rule 12` ของ Error หรือ Review/Warning ตามระดับปัญหา เฉพาะเมื่อมีรายการ และแสดงผลใน summary เช่นเดียวกับข้ออื่น

## ข้อ 13 ตรวจสอบ Meta POP เทียบกับ Product Master

อ่าน Meta Extension POP ชีต `POP_metaExt_productInfo` หรือชีต raw export `metaExtension POP` ตามรูปแบบเดิม
สำหรับ Excel ใช้ข้อมูลตั้งแต่แถว 6 เป็นต้นไป โดยค้นคอลัมน์จากหัวตารางในห้าแถวแรก ส่วน CSV ใช้ข้อมูลถัดจากหัวตาราง ไม่ข้ามห้าแถวข้อมูล
ต้องมีคอลัมน์ `Product Offer Price ID`, `matCode`, `commercialName`, `sapDescriptionEng`, `sapDescriptionTha`

ข้าม POP ใน `exclude_pop_ids` แล้วนำ matCode ไม่ซ้ำไป query `PRODUCT_MST` ใน schema จาก `.env` ด้วย SQL parameter `MAT_CODE = matCode` หนึ่งครั้งต่อรหัส และตรวจทุกแถว Meta ที่ใช้รหัสนั้น:

- `COMMERCIAL_NAME` ต้องตรงกับ `commercialName` หาก `COMMERCIAL_NAME` เป็น NULL หรือข้อความว่าง ให้ใช้ `SAP_DESCRIPTION` เทียบกับ `commercialName` แทน โดย Reason และ Related Evidence ระบุคอลัมน์ที่ใช้เทียบจริง ข้อความที่มีเฉพาะช่องว่างยังถือว่ามีค่าตามกฎไม่ trim
- `SAP_DESCRIPTION` ต้องตรงกับ `sapDescriptionEng`
- `SAP_DESCRIPTION` ต้องตรงกับ `sapDescriptionTha`

ทั้งชื่อภาษาอังกฤษและภาษาไทยเทียบกับ `SAP_DESCRIPTION` คอลัมน์เดียวกันตามกฎที่กำหนด
เปรียบเทียบข้อความตรงตัว แยกตัวพิมพ์ใหญ่เล็ก ไม่ trim ค่า และไม่ข้ามชื่อที่ว่าง ค่า NULL จากฐานข้อมูลไม่เท่ากับข้อความว่าง
matCode ว่างหรือไม่พบ MAT_CODE เป็น Error หากพบหลายแถวใน PRODUCT_MST ให้เลือกแถวล่าสุดเพียงแถวเดียวด้วย `TOP (1)` และเรียง `COALESCE(system_updated_at, system_created_at) DESC, system_created_at DESC, PRODUCT_ID DESC` โดยใช้เวลาอัปเดตล่าสุด หากไม่มีให้ใช้เวลาสร้าง และใช้ PRODUCT_ID ตัดสินเมื่อเวลาเท่ากัน ไม่แจ้ง Review เพียงเพราะมี MAT_CODE ซ้ำ
เมื่อค่าต่างกัน แจ้ง Error แยกตามช่องในชีต `Rule 13` พร้อม POP ID, matCode, แถวต้นทาง, ชื่อช่อง, ค่าจาก Meta และค่าที่คาดหวังจาก Product Master
ช่อง Reason ระบุ matCode และค่าที่เทียบกันโดยตรง เช่น `matCode='001': Meta POP.commercialName = 'Phone' ไม่ตรงกับ PRODUCT_MST.COMMERCIAL_NAME = 'Phone 128GB'` โดยใช้เครื่องหมายคำพูดครอบข้อความเพื่อให้เห็นค่าว่างและช่องว่าง และแสดงค่า NULL จากฐานข้อมูลเป็น `None`
หากเชื่อมต่อหรือ query ไม่สำเร็จ ให้เป็น Review และ `complete=false` ไม่สรุปว่าข้อมูล Meta ผิด
รองรับ XLSX และ CSV fallback เดียวกับกฎอื่น ใช้ `product_catalog/.env` หรือ `--env` ทั้งโหมด export ไฟล์รวม และฐานข้อมูล

## ข้อ 14 ตรวจสอบ Char จาก Variant เทียบกับ Product Master และ Price Master

1. อ่าน `Product_Variants` จับคู่ `Product Variants.specCharacteristics` กับ `Product Variants.value` ตาม index ของสมาชิกที่แยกด้วย comma หากจำนวนไม่เท่ากันหรือมีสมาชิกว่าง ให้แจ้ง Error
2. ตาม variantId ไปที่ `Variant_ProductOffering_Price` แล้วนำ POP ID ทั้งหมดไปค้นชีต `Product Offer Price` เลือกแถว `priceType = Onetime` ต้องได้หนึ่งแถว ถ้าไม่มีหรือมากกว่าหนึ่งแถว ให้แจ้ง Error และเก็บ `price_value` ของแถวนั้น
3. รวมคู่ `Char Name` + `value` จาก `Characteristics for Price` ของ Onetime POP เข้า Char List ของ Variant
4. ค้น `PRODUCT_MST` ด้วย `Product Variants.sku = MAT_CODE` ต้องพบหนึ่งแถว หากไม่มีหรือมากกว่าหนึ่งแถวให้แจ้ง Error กฎข้อนี้ไม่ใช้การเลือกแถวล่าสุดแบบข้อ 13
5. เทียบ Char กับคอลัมน์ต่อไปนี้:

| PRODUCT_MST | Char |
|---|---|
| MAIN_MODEL | main_model / mainModel |
| BRAND | brand |
| COMPANY | company |
| COLOR | color |
| CAPACITY | capacity |
| PRODUCT_TYPE | productType / product_type |
| PRODUCT_SUBTYPE | productSubType / product_sub_type / product_subtype |
| MAT_TYPE | matType / mat_type |
| MODEL | model |
| UNIT_NAME | unitName / unit_name |

ชื่อ Char ตัด suffix `-mh_mg...` แล้วไม่แยกตัวพิมพ์ใหญ่เล็กและไม่สนใจ `_` เพื่อรองรับ camelCase และ snake_case ส่วนค่าต้องตรงตัว ไม่ trim
ข้าม Char ที่ value ว่าง ค่า NULL หรือข้อความว่างในฐานข้อมูลหมายถึงต้องไม่มี Char ที่มีค่า หากฐานข้อมูลมีค่าต้องมี Char ค่านั้น และห้ามมีค่าอื่นร่วมด้วย ไม่ใช้ค่าจากระดับใดเขียนทับอีกระดับ
คู่ Char ที่ซ้ำแต่ค่าเดียวกันนับเป็นค่าเดียว ส่วนชื่ออื่นนอกตารางไม่ถูกเทียบกับ PRODUCT_MST

6. ใช้ PRODUCT_ID เชื่อม PRICE_MST และใช้ price_group จาก Char List เทียบ PRICE_GROUP แบบตรงตัว ต้องมี price_group หนึ่งค่า หากไม่พบกลุ่มราคาให้แจ้ง Error ถ้าพบ PRICE_MST มากกว่าหนึ่งแถวให้เป็น Review เพราะยังไม่มีเกณฑ์เลือกแถวราคา
7. เทียบ INC_VAT กับ price_value ด้วย Decimal โดย `100` เท่ากับ `100.00` หากค่าไม่ใช่ตัวเลขหรือราคาไม่ตรงให้แจ้ง Error

ใช้รายการยกเว้น PO/POP ตาม config และ XLSX/CSV fallback เดิม ไฟล์ Product Offer Price ต้องมี price_value โดยรองรับเซลล์ตัวเลขสำหรับคอลัมน์นี้
ใช้ฐานข้อมูลจาก `.env` หรือ `--env` หากเชื่อมต่อหรือ query ไม่สำเร็จ ให้เป็น Review และ complete=false
ผลอยู่ในชีต `Rule 14` พร้อม Variant ID, SKU, POP ID, ชื่อ Char, ค่าที่พบและค่าอ้างอิง เฉพาะเมื่อมีปัญหา

## สรุปความครบถ้วน

ทุก Record ถูกอ่าน ไม่มี Sampling ข้อที่มี Review ยังคงแสดง `complete=false`
รายการ Review ไม่ถูกนับเป็น Error หรือ Pass โดยปริยาย
หนึ่งต้นเหตุอาจผิดหลายข้อ เช่น POP ไม่มี Characteristic และ Variant ไม่มี model ทำให้ข้อ 5 และข้อ 6 ผิด
ห้ามรวมจำนวน Error แล้วตีความเป็นจำนวน PO/POP ที่ไม่ซ้ำ
