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
| 7 | main_model ใน POP, Variant, Char_Value ของ PO แล้วตรวจ PRODUCT_MST ด้วย SKU | ไม่พบ link/Variant หรือ Char_Value หรือ DEVICE ไม่มี main_model และไม่พบ MAT_CODE หรือ MAIN_MODEL มีข้อมูล |
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
| 14 | รวม Char จาก Variant และ Onetime POP เทียบ Product Master และ Price Master | Char ไม่ตรง, Onetime POP ไม่ครบหนึ่งแถว, ไม่พบ PRODUCT_MST ที่ใช้ได้ หรือราคาไม่ตรง |
| 15 | ย้อน MAT_CODE ของสินค้าที่เข้าเงื่อนไขและมีราคาปัจจุบัน ไปตรวจความครบถ้วนใน Product_Variants | ไม่พบ SKU หรือพบ Variant หลายแถวแต่ไม่มี price_group ตรงกลุ่มราคาที่มีผล |

## รายการยกเว้นการตรวจ Exclude list

โปรแกรมมีรายการยกเว้นอยู่ใน [config.json](config.json) โดยอ่านไฟล์นี้เป็นค่าเริ่มต้น หากระบุ `--config` จะใช้รายการจากไฟล์ที่ระบุแทน การแก้รายการในเอกสารนี้อย่างเดียวไม่มีผลต่อโปรแกรม ต้องแก้ใน config ที่ใช้รันด้วย

| ชื่อรายการ | ใช้เทียบกับ | ผลของการยกเว้น |
|---|---|---|
| `exclude_po_ids` | PO ID เช่น `Product Variants.Product Id` และ `Char Value.Product Offer ID` | ข้าม Variant ของ PO เหล่านี้ และข้ามการตรวจ Char_Value ตาม PO ในข้อ 7–10, 12 และการตรวจ Variant ข้อ 14 ตามเงื่อนไขของแต่ละกฎ |
| `exclude_pop_ids` | POP ID เช่น `Product Offer Price ID` และ POP ID ใน link | ข้าม POP ในรายการหลัก, Characteristics for Price และ Meta รวมการตรวจ POP/Channel และการเลือก Onetime POP ตามเงื่อนไขของแต่ละกฎ |

เทียบ ID แบบตรงตัว แยกตัวพิมพ์ใหญ่เล็ก ไม่ trim และไม่ใช้ wildcard รายการเป็นรหัสเต็มเท่านั้น ไม่ใช่ช่วงรหัสหรือ prefix ใช้ config เดียวกันทั้ง Excel, CSV และฐานข้อมูล

รายการยกเว้นไม่ใช่การลบข้อมูลตั้งต้น โปรแกรมยังอ่านไฟล์ ตรวจรูปแบบข้อมูล และเก็บข้อมูลสำหรับตรวจการอ้างอิง การยกเว้น PO ไม่ได้เพิ่ม POP ที่เชื่อมกันเข้า `exclude_pop_ids` อัตโนมัติ และการยกเว้น POP ไม่ได้ยกเว้น PO หรือ Variant ทั้งหมดของ PO นั้น กฎที่ตรวจความถูกต้องของ link/เจ้าของ เช่นข้อ 9.2 อาจยังรายงานปัญหาของ link ที่ไม่ได้ยกเว้นได้

ตรวจรายการที่ใช้จริงของแต่ละรอบได้จาก `config_used.json` ในโฟลเดอร์ผลตรวจ ส่วน `summary.json` มี `exclude_config` แสดงจำนวน ID ไม่ซ้ำที่ตั้งไว้ และ `excluded_source_rows` แสดงจำนวนแถว PO, POP และ Variant ที่เข้ารายการยกเว้น ไม่ใช่จำนวน Error ที่ถูกซ่อน

### รายการจาก config เริ่มต้น ณ วันที่ 9 พฤศจิกายน 2026

`exclude_po_ids`: **1 IDs**

```text
pay_advance_airtime-of_mg50001
```

`exclude_pop_ids`: **382 IDs**

```text
op_mg50001
op_mg50002
op_mg50003
op_mg50004
op_mg50005
op_mg50006
op_mg50011
op_mg50012
op_mg50013
op_mg50014
op_mg50015
op_mg50016
op_mg50017
op_mg50018
op_mg50019
op_mg50020
op_mg50021
op_mg50022
op_mg50023
op_mg50024
op_mg50025
op_mg50026
op_mg50027
op_mg50028
op_mg50029
op_mg50030
op_mg50031
op_mg50032
op_mg50033
op_mg50036
op_mg50037
op_mg50038
op_mg50039
op_mg50040
op_mg50041
op_mg50042
op_mg50043
op_mg50044
op_mg50045
op_mg50046
op_mg50047
op_mg50048
op_mg50051
op_mg50052
op_mg50053
op_mg50054
op_mg50055
op_mg50056
op_mg50057
op_mg50058
op_mg50059
op_mg50060
op_mg50062
op_mg50063
op_mg50064
op_mg50065
op_mg50066
op_mg50067
op_mg50068
op_mg50069
op_mg50070
op_mg50071
op_mg50076
op_mg50077
op_mg50078
op_mg50079
op_mg50080
op_mg50081
op_mg50082
op_mg50083
op_mg50084
op_mg50085
op_mg50086
op_mg50087
op_mg50088
op_mg50089
op_mg50090
op_mg50091
op_mg50092
op_mg50093
op_mg50094
op_mg50095
op_mg50096
op_mg50097
op_mg50098
op_mg50099
op_mg50100
op_mg50101
op_mg50102
op_mg50103
op_mg50104
op_mg50105
op_mg50106
op_mg50107
op_mg50108
op_mg50109
op_mg50110
op_mg50111
op_mg50112
op_mg50117
op_mg50118
op_mg50120
op_mg50121
op_mg50122
op_mg50123
op_mg50124
op_mg50125
op_mg50126
op_mg50127
op_mg50128
op_mg50129
op_mg50130
op_mg50131
op_mg50132
op_mg50133
op_mg50134
op_mg50135
op_mg50136
op_mg50137
op_mg50138
op_mg50139
op_mg50140
op_mg50142
op_mg50143
op_mg50144
op_mg50145
op_mg50146
op_mg50147
op_mg50148
op_mg50149
op_mg50150
op_mg50151
op_mg50152
op_mg50154
op_mg50155
op_mg50156
op_mg50157
op_mg50158
op_mg50159
op_mg50160
op_mg50161
op_mg50162
op_mg50163
op_mg50164
op_mg50165
op_mg50166
op_mg50167
op_mg50168
op_mg50169
op_mg50170
op_mg50171
op_mg50172
op_mg50173
op_mg50174
op_mg50175
op_mg50176
op_mg50177
op_mg50178
op_mg50179
op_mg50180
op_mg50181
op_mg50182
op_mg50183
op_mg50184
op_mg50185
op_mg19123
op_mg19124
op_mg18122
op_mg18123
op_mg19045
op_mg19048
op_mg18045
op_mg18048
op_mg19058
op_mg19125
op_mg18058
op_mg18124
op_mg19072
op_mg19126
op_mg18072
op_mg18125
op_mg19012
op_mg19049
op_mg18012
op_mg18049
op_mg19027
op_mg19050
op_mg18027
op_mg18050
op_mg19028
op_mg19054
op_mg18028
op_mg18054
op_mg19055
op_mg19128
op_mg18055
op_mg18127
op_mg19003
op_mg19020
op_mg19032
op_mg19147
op_mg18003
op_mg18020
op_mg18032
op_mg18146
op_mg19090
op_mg19129
op_mg18090
op_mg18128
op_mg19056
op_mg19130
op_mg18056
op_mg18129
op_mg19077
op_mg19131
op_mg18077
op_mg18130
op_mg19091
op_mg19132
op_mg18091
op_mg18131
op_mg19004
op_mg19021
op_mg19033
op_mg19155
op_mg18004
op_mg18021
op_mg18033
op_mg18157
op_mg19092
op_mg19133
op_mg18092
op_mg18132
op_mg19081
op_mg19134
op_mg18081
op_mg18133
op_mg19057
op_mg19135
op_mg18057
op_mg18134
op_mg19093
op_mg19136
op_mg18093
op_mg18135
op_mg19005
op_mg19022
op_mg19034
op_mg19141
op_mg18005
op_mg18022
op_mg18034
op_mg18140
op_mg19094
op_mg18094
op_mg19109
op_mg19078
op_mg18078
op_mg19095
op_mg18095
op_mg19006
op_mg19023
op_mg19035
op_mg18006
op_mg18023
op_mg18035
op_mg19096
op_mg18096
op_mg19097
op_mg18097
op_mg19089
op_mg18089
op_mg19098
op_mg18098
op_mg19007
op_mg19024
op_mg19036
op_mg19145
op_mg18007
op_mg18024
op_mg18036
op_mg18144
op_mg19099
op_mg18099
op_mg19100
op_mg18100
op_mg19079
op_mg18079
op_mg19101
op_mg18101
op_mg19030
op_mg19037
op_mg19146
op_mg18030
op_mg18037
op_mg18145
op_mg19102
op_mg18102
op_mg19103
op_mg18103
op_mg19104
op_mg18104
op_mg19105
op_mg18105
op_mg19008
op_mg19038
op_mg19144
op_mg18008
op_mg18038
op_mg18143
op_mg19106
op_mg18106
op_mg19107
op_mg18107
op_mg19108
op_mg18108
op_mg19009
op_mg19039
op_mg18009
op_mg18039
op_mg19010
op_mg19040
op_mg19142
op_mg18010
op_mg18040
op_mg18141
op_mg19041
op_mg18041
op_mg19011
op_mg19042
op_mg19143
op_mg18011
op_mg18042
op_mg18142
op_mg19111
op_mg18110
op_mg19110
op_mg19112
op_mg18111
op_mg19113
op_mg18112
op_mg19114
op_mg18113
op_mg19017
op_mg19018
op_mg19043
op_mg18017
op_mg18043
op_mg19029
op_mg19115
op_mg18029
op_mg18114
op_mg19026
op_mg19044
op_mg19188
op_mg18026
op_mg18044
op_mg18188
op_mg19116
op_mg18115
op_mg19016
op_mg19052
op_mg19190
op_mg18016
op_mg18052
op_mg18190
op_mg19117
op_mg18116
op_mg19015
op_mg19053
op_mg18015
op_mg18053
op_mg19118
op_mg18117
op_mg19119
op_mg18118
op_mg19120
op_mg18119
op_mg19121
op_mg18120
op_mg19122
op_mg18121
```

หากแก้รายการใน config ภายหลัง ให้ปรับรายการในหัวข้อนี้ตามด้วย โดยยึด `config_used.json` ของรอบตรวจเป็นหลักเมื่อตรวจสอบผลย้อนหลัง

## กฎกลางสำหรับใช้ CSV แทนฐานข้อมูล

กฎนี้ใช้ร่วมกันทุกข้อที่อ่าน table หรือ view จากฐานข้อมูล รวมการอ่าน mapping และข้อมูลอ้างอิงข้อ 12–14:

1. หากเปิดการเชื่อมต่อฐานข้อมูลไม่ได้ รวมกรณีไม่มีไฟล์ `.env` ให้เปลี่ยนมาอ่าน CSV ในโฟลเดอร์ `Database` ที่ root ของโปรเจกต์ และใช้ CSV สำหรับการเรียกฐานข้อมูลที่เหลือของรอบนั้น โดยไม่ลองเชื่อมต่อซ้ำ
2. หากระบุ `--csv` ให้ใช้ CSV โดยไม่เชื่อมต่อฐานข้อมูล รองรับทั้งตรวจรวมทุกกฎและเลือกข้อด้วย `--rules` หากไม่ระบุไฟล์ export โปรแกรมจะอ่านข้อมูลหลักจาก CSV ด้วย หากระบุโฟลเดอร์ export จะใช้ข้อมูลหลักจาก export และใช้ CSV แทนเฉพาะส่วนที่ต้องเรียกฐานข้อมูล
3. ใช้ชื่อ table หรือ view จับคู่กับชื่อไฟล์ รองรับ `<table>.csv`, `<table>_<YYYYMMDDHHMM>.csv` และ `<table>_<YYYYMMDDHHMMSS>.csv` เช่น `Database/PRODUCT_MST_202611091058.csv` ไม่เติม schema เทียบชื่อโดยไม่แยกตัวพิมพ์ใหญ่เล็ก เลือกชื่อที่ไม่มี timestamp ก่อน หากไม่มีจึงเลือก timestamp ล่าสุดจากชื่อไฟล์ ไม่ใช้เวลาแก้ไขไฟล์ หากเวลาเท่ากันเลือกชื่อที่ระบุวินาที timestamp ต้องเป็นวันเวลาที่ถูกต้อง หากยังพบหลายไฟล์ที่ตรงกันให้หยุด ไม่ค้นโฟลเดอร์ย่อยหรือรวมไฟล์หลายรอบ กฎนี้รวมไฟล์ mapping และทุก table/view
4. โหมดอ่านข้อมูลหลักจากฐานข้อมูลหรือ CSV ใช้ `template_mapping.csv` หรือชื่อจาก `TEMPLATE_MAPPING_TABLE` เพื่อหา `DATABASE NAME` แล้วอ่าน `<DATABASE NAME>.csv` รวมแหล่งข้อมูล `UNOIN` เช่นเดิม หาก fallback ของไฟล์ Excel ต้องค้น `table_mapping` ให้ใช้ `Database/table_mapping.csv` ผ่านกฎกลางนี้ด้วย
5. CSV ใช้ UTF-8 รองรับ BOM แถวแรกเป็นชื่อคอลัมน์ตรงกับ table/view รวมช่องว่างและจุดในชื่อคอลัมน์ อ่านทุกแถว เก็บรหัสและข้อความตามเดิม ไม่ trim ไม่ตัดเลขศูนย์นำหน้า ค่าว่างคือข้อความว่าง ใช้ `\N` แทน SQL NULL โดยเฉพาะ ไม่ใช้คำว่า `NULL` แทนโดยอัตโนมัติ
6. ใช้เงื่อนไข filter, join, การนับแถวซ้ำ และการเลือกแถวตามกฎเดิม ข้อ 13 ต้องมี `system_updated_at`, `system_created_at`, `PRODUCT_ID` เพื่อเลือกแถวล่าสุด เวลาใน CSV ต้องใช้รูปแบบ ISO ที่เรียงเป็นเวลาได้และ timezone เดียวกัน ค่า NULL ในเวลาให้ใช้ `\N` และ `PRODUCT_ID` ใช้รหัสตัวเลขเช่นเดียวกับฐานข้อมูล ข้อ 14 ยังคงตรวจจำนวนแถว PRODUCT_MST และ PRICE_MST ตามเดิม
7. หาก CSV หาย หัวคอลัมน์ซ้ำ คอลัมน์ที่ query ต้องใช้ไม่ครบ หรือจำนวนช่องในแถวไม่ถูกต้อง ห้ามถือว่าไม่พบข้อมูลหรือผ่านกฎ หากเป็นข้อมูลอ้างอิงข้อ 12–14 ให้เป็น Review และ `complete=false` หากเป็นข้อมูลหลักที่อ่านไม่ได้ให้หยุดรอบตรวจพร้อม `FAILED.json` ส่วนข้อผิดพลาดของ query บนฐานข้อมูลที่เชื่อมต่อได้ยังคงรายงานตามเดิม ไม่สลับมา CSV เพื่อซ่อนข้อผิดพลาด
8. บันทึก path ของ CSV ที่อ่านใน `run.log` และ SHA-256 ใน `summary.json` โดยตรวจว่าไฟล์ไม่เปลี่ยนระหว่างรัน ใช้ `--database-dir` เพื่อเปลี่ยนโฟลเดอร์จากค่าเริ่มต้น `Database` ได้

`--check-connection` ทดสอบฐานข้อมูลจริงเท่านั้น ไม่ใช้ CSV fallback และใช้ร่วมกับ `--csv` ไม่ได้
ข้อความในข้อ 12–14 ที่ระบุกรณีเชื่อมต่อไม่สำเร็จ ให้ลอง CSV ตามกฎกลางก่อน หากยังอ่านไม่ได้จึงรายงาน Review ตามเดิม

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
6. หาก PO นั้นมี `product_type-mh_mg00162 = DEVICE` ให้ตรวจ `main_model-mh_mg00554` ที่มี value อย่างน้อยหนึ่งแถวใน Char_Value ของ PO เดียวกัน ตรวจแต่ละ PO แยกกันเมื่อพบหลาย PO หากยังไม่มี ให้ตรวจ PRODUCT_MST ต่อไปนี้:
   - นำ `Product Variants.sku` ของทุกแถว Variant ที่เกี่ยวข้องกับ PO และ POP ที่ตรวจแล้วว่าไม่มี main_model ทั้งใน POP, Variant และ PO ไป query `PRODUCT_MST` ด้วย `MAT_CODE = sku` แบบตรงตัว ผ่าน SQL parameter หนึ่งครั้งต่อ SKU ไม่ซ้ำ
   - ต้องพบ PRODUCT_MST หนึ่งแถว หาก `MAIN_MODEL` เป็น SQL NULL หรือข้อความว่าง `''` ให้ถือว่าไม่มีข้อมูลและผ่าน ทั้งโหมดฐานข้อมูลและ CSV แล้วเก็บแถว Variant ในรายงานแยก `Result_Rule7_NoMainModel_<วันเวลา>.xlsx` ชีต `Rule 7` พร้อม Variant ID, SKU, PO ID, POP ID และไฟล์/แถวต้นทาง รายงานระบุค่าจริงว่าเป็น NULL หรือ `''` และไม่ถูกนับเป็น Error หรือ Review
   - หาก `MAIN_MODEL` มีข้อมูล ให้แจ้ง Error `DEVICE_MAIN_MISSING` ข้อความที่มีเฉพาะช่องว่างยังถือว่ามีค่าตามกฎไม่ trim หาก SKU ว่างหรือไม่พบ MAT_CODE ให้แจ้ง Error เช่นกัน โดยระบุ Variant ID และ SKU ที่ตรวจ
   - หากพบหลายแถวต่อ MAT_CODE ให้เป็น Review เพราะยังไม่มีเกณฑ์เลือกแถวสำหรับข้อ 7 หาก query ไม่สำเร็จให้เป็น Review และ `complete=false` ไม่สรุปว่าไม่มี main_model
   - ใช้ฐานข้อมูลหรือ CSV จากโฟลเดอร์ `Database` ตามกฎกลาง รวมการเลือกไฟล์ชื่อมี timestamp ค่า NULL ใน CSV ต้องเขียน `\N` ข้อ 7 ไม่ใช้ PRICE_MST และไม่ใช้เกณฑ์เลือกแถวล่าสุดของข้อ 13

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
4. ค้น `PRODUCT_MST` ด้วย `Product Variants.sku = MAT_CODE` หากพบหนึ่งแถวให้นำแถวนั้นไปใช้ต่อ หากพบมากกว่าหนึ่งแถว ให้เทียบค่า company ใน Char List ที่รวมจาก Variant และ Onetime POP กับ `PRODUCT_MST.COMPANY` แบบตรงตัว ไม่ trim และแยกตัวพิมพ์ใหญ่เล็ก นำทุกแถวที่ COMPANY ตรงกันไปใช้ต่อ แม้เหลือมากกว่าหนึ่งแถว หากไม่พบ MAT_CODE หรือไม่มี COMPANY ตรงกัน ให้แจ้ง Error `VARIANT_PRODUCT_MASTER_COUNT` ไม่เลือกแถวแรกหรือแถวล่าสุดแบบข้อ 13 ขั้นตอน 5 เทียบ Char กับทุกแถวที่เลือก พร้อมระบุ PRODUCT_ID ในรายละเอียด และขั้นตอน 6 ใช้ PRODUCT_ID ที่เลือกทั้งหมดโดยไม่ซ้ำ ไม่รวมราคาของบริษัทอื่น
5. เทียบ Char กับคอลัมน์ต่อไปนี้:

| PRODUCT_MST | Char |
|---|---|
| MAIN_MODEL | main_model / mainModel |
| BRAND | brand |
| COMPANY | company |
| COLOR | color |
| CAPACITY | storage_capacity / storageCapacity |
| PRODUCT_TYPE | productType / product_type |
| PRODUCT_SUBTYPE | productSubType / product_sub_type / product_subtype |
| MAT_TYPE | matType / mat_type |
| MODEL | ใช้ value ของ model เป็นชื่อ Char ปลายทาง แล้วนำ value ของ Char ปลายทางมาเทียบ |
| UNIT_NAME | unitName / unit_name |

ชื่อ Char ตัด suffix `-mh_mg...` แล้วไม่แยกตัวพิมพ์ใหญ่เล็กและไม่สนใจ `_` เพื่อรองรับ camelCase และ snake_case ส่วนค่าต้องตรงตัว ไม่ trim
ข้าม Char ที่ value ว่าง ค่า NULL หรือข้อความว่างในฐานข้อมูลหมายถึงต้องไม่มี Char ที่มีค่า หากฐานข้อมูลมีค่าต้องมี Char ค่านั้น และห้ามมีค่าอื่นร่วมด้วย ไม่ใช้ค่าจากระดับใดเขียนทับอีกระดับ
คู่ Char ที่ซ้ำแต่ค่าเดียวกันนับเป็นค่าเดียว ส่วนชื่ออื่นนอกตารางไม่ถูกเทียบกับ PRODUCT_MST

สำหรับ MODEL เช่น `model = appleIpadAir11SeriesHandset` และ `apple_ipad_air11_series_handset = AIR11M3WF_128GB` จะนำ `AIR11M3WF_128GB` เทียบกับ `PRODUCT_MST.MODEL` โดยชื่อ Char ปลายทางรองรับ camelCase/snake_case ผ่านกฎแปลงชื่อเดียวกัน ค่าที่นำมาเทียบยังเป็นแบบตรงตัว
หากไม่พบ Char ปลายทางหลังเทียบชื่อแบบ camelCase/snake_case หรือ Char ปลายทางไม่มีค่า ให้ถือว่าไม่มีค่า MODEL กรณีนี้ PRODUCT_MST.MODEL ต้องเป็น NULL หรือข้อความว่างจึงผ่าน หากฐานข้อมูลมีค่าให้แจ้ง Error พร้อมข้อความว่าต้องไม่มีค่า MODEL
หาก model ชี้หลายชื่อ หรือชี้กลับมาที่ model เอง ให้แจ้ง Error ไม่ใช้ชื่อที่ model ชี้ไปเทียบกับฐานข้อมูลโดยตรง รายละเอียด Error ระบุเส้นทาง `model -> ชื่อ Char ปลายทาง` พร้อมค่าที่เทียบ
CAPACITY ใช้ storage_capacity/storageCapacity เท่านั้น ไม่ใช้ Char ชื่อ capacity แทน

6. ใช้ PRODUCT_ID ทั้งหมดจากขั้นตอน 4 เชื่อม PRICE_MST แล้วใช้ price_group จาก Char List เทียบ PRICE_GROUP แบบตรงตัว โดย Char List ต้องมี price_group หนึ่งค่า หากไม่พบแถวราคาที่ตรงกลุ่มให้แจ้ง Error หากพบแถวราคามากกว่าหนึ่งแถวใน PRODUCT_ID ที่เลือกทั้งหมด ให้เลือกแถวที่ `EFFECTIVE_DATE` ล่าสุดเพียงแถวเดียวก่อนเทียบ INC_VAT ในขั้นตอน 7 ไม่เลือกจากราคาที่เท่ากับ POP และไม่แยกเลือกราคาล่าสุดทีละ PRODUCT_ID หาก EFFECTIVE_DATE ล่าสุดเท่ากันหลายแถว ให้เป็น Review และ `complete=false` เพราะยังไม่มีเกณฑ์ตัดสิน หากวันที่บางแถวเป็น NULL หรือข้อความว่าง ให้เลือกจากแถวที่มีวันที่ แต่หากไม่มีวันที่ที่ใช้ได้เลยหรือมีวันที่ผิดรูปแบบให้เป็น Review เมื่อมีแถวราคาเดียวใช้แถวนั้นได้โดยไม่ต้องจัดอันดับวันที่ CSV ต้องมีคอลัมน์ `EFFECTIVE_DATE` และใช้วันเวลารูปแบบ ISO เช่น `2026-11-09 10:58:00` ใน timezone เดียวกัน รายละเอียดราคาที่ไม่ตรงระบุ PRODUCT_ID และ EFFECTIVE_DATE ของแถวที่เลือก
7. เทียบ INC_VAT กับ price_value ด้วย Decimal โดย `100` เท่ากับ `100.00` หากค่าไม่ใช่ตัวเลขหรือราคาไม่ตรงให้แจ้ง Error

ใช้รายการยกเว้น PO/POP ตาม config และ XLSX/CSV fallback เดิม ไฟล์ Product Offer Price ต้องมี price_value โดยรองรับเซลล์ตัวเลขสำหรับคอลัมน์นี้
ใช้ฐานข้อมูลจาก `.env` หรือ `--env` หากเชื่อมต่อหรือ query ไม่สำเร็จ ให้เป็น Review และ complete=false
ผลอยู่ในชีต `Rule 14` พร้อม Variant ID, SKU, POP ID, ชื่อ Char, ค่าที่พบและค่าอ้างอิง เฉพาะเมื่อมีปัญหา

## ข้อ 15 ตรวจความครบถ้วนของ MAT_CODE ใน Product Offer

ตรวจย้อนจาก PRODUCT_MST ทุกแถว ไม่มี sampling ไปยังไฟล์ Product Offer ชีต `Product_Variants` โดยใช้กฎกลางฐานข้อมูล/CSV เหมือนข้ออื่น เลือกตรวจเฉพาะข้อได้ด้วย `--rules 15` และรวมข้อ 15 อัตโนมัติเมื่อไม่ระบุ `--rules`

### เลือกสินค้าและราคาที่ใช้ตรวจ

ยึดวันที่เริ่มรันตามเวลาไทย Asia/Bangkok เป็นวันเดียวกันตลอดรอบ โดยไม่เปลี่ยนวันกลางทาง:

1. `PRODUCT_MST.PRODUCT_TYPE` ต้องไม่เท่ากับ `SERVICE`
2. `PRODUCT_MST.CATEGORY` ต้องไม่เป็น `SAMM`, SQL NULL หรือข้อความว่าง `''`
3. `PRODUCT_MST.EXPIRE_DATE` ต้องไม่มีค่า คือ NULL หรือข้อความว่าง หรือเป็นวันที่ `1900-01-01` ซึ่งเป็นค่า default ที่ใช้แทนการยังไม่กำหนดวันหมดอายุ หรือมีวันที่ตั้งแต่วันนี้เป็นต้นไป จึงถือว่ายังไม่หมดอายุ รวมสินค้าที่หมดอายุวันนี้ด้วย
4. เชื่อม PRICE_MST ด้วย `PRODUCT_ID` ต้องมีอย่างน้อยหนึ่งแถวที่ `PRICE_ID` มีค่า, `EFFECTIVE_DATE` ไม่เกินวันนี้ และ `EXPIRE_DATE` ไม่มีค่า, เป็นวันที่ `1900-01-01` หรือไม่น้อยกว่าวันนี้ นำเฉพาะราคาที่เข้าเงื่อนไขนี้ไปใช้ สินค้าที่ไม่มีราคาที่มีผลอยู่ไม่อยู่ในขอบเขตตรวจข้อ 15

การใช้ `1900-01-01` แทน NULL ใช้เฉพาะ EXPIRE_DATE ของสินค้าและราคาในข้อ 15 ทั้งฐานข้อมูลและ CSV รวมรูปแบบที่มีเวลา เช่น `1900-01-01 00:00:00.000` ไม่แปลง EFFECTIVE_DATE วันที่นี้เป็น NULL และไม่เปลี่ยนค่าต้นทางหรือเงื่อนไขของกฎอื่น

เทียบ PRODUCT_TYPE, CATEGORY, MAT_CODE และ PRICE_GROUP แบบตรงตัว ไม่ trim และแยกตัวพิมพ์ใหญ่เล็ก ข้อความที่มีแต่ช่องว่างยังถือว่ามีค่า วันที่เปรียบเทียบระดับวัน ไม่ใช่เวลาระหว่างวัน วันที่ไม่มี timezone ใช้วันตามข้อมูล ส่วนวันที่มี timezone แปลงเป็นเวลาไทยก่อน CSV ใช้รูปแบบ ISO เช่น `2026-11-11` หรือ `2026-11-11 10:58:00` และใช้ `\N` แทน NULL

หากวันหมดอายุสินค้าหรือวันที่ราคามีรูปแบบไม่ถูกต้อง หรือราคาไม่มี EFFECTIVE_DATE จนเลือกข้อมูลไม่ได้ ให้เป็น Review `MAT_CODE_DATE_INVALID` และ `complete=false` ไม่สรุปว่า MAT_CODE ผ่านหรือไม่มีราคา

### ตรวจย้อนกลับไปที่ Variant

1. ตรวจทีละแถว PRODUCT_MST ที่เข้าเงื่อนไข นำ `MAT_CODE` เทียบกับ `Product Variants.sku` โดยไม่ตัดเลขศูนย์นำหน้า หาก MAT_CODE ว่างให้เป็น Error `MAT_CODE_EMPTY`
2. หากไม่พบ Variant ให้เป็น Error `MAT_CODE_VARIANT_MISSING` พร้อม MAT_CODE, PRODUCT_ID และ PRICE_ID ที่มีผลอยู่
3. หากพบ Variant หนึ่งแถว ถือว่ามี MAT_CODE ใน Product Offer แล้ว โดยไม่เทียบ price_group ในข้อ 15 ตามขอบเขตที่กำหนด กฎข้ออื่นยังคงตรวจตามเดิม
4. หากพบ Variant มากกว่าหนึ่งแถว ให้ split `Product Variants.specCharacteristics` และ `Product Variants.value` ด้วย comma แล้วเลือกค่า price_group จาก index เดียวกัน เช่นเดียวกับข้อ 14 รองรับ suffix `-mh_mg...` และการแปลงชื่อ Char แบบ camelCase/snake_case แต่ค่าต้องตรงตัว
5. ทุก PRICE_GROUP ไม่ซ้ำของราคาที่มีผลอยู่สำหรับ PRODUCT_ID นั้น ต้องพบในอย่างน้อยหนึ่งแถว Variant ของ MAT_CODE เดียวกัน หากไม่พบให้เป็น Error `MAT_CODE_PRICE_GROUP_MISSING` หนึ่งรายการต่อแถวสินค้าและ PRICE_GROUP ไม่จำเป็นต้องจับคู่หนึ่งต่อหนึ่งกับจำนวนแถวราคา และไม่แจ้ง Error เพียงเพราะ Variant ที่ตรงมีหลายแถว
6. หากราคาที่มีผลอยู่มี PRICE_GROUP ว่าง ให้เป็น Error `MAT_CODE_PRICE_GROUP_EMPTY` เมื่อเข้าสู่ขั้นเทียบกลุ่มราคา หากจับคู่ comma ของ Variant ไม่ได้ให้เป็น Error `MAT_CODE_VARIANT_CHAR_INVALID` และหากยังสรุปไม่ได้ว่ามี price_group ที่ต้องการหรือไม่ ให้เป็น Review สำหรับกลุ่มนั้น ไม่ใช้แถวผิดรูปแบบเป็นหลักฐานว่าผ่าน

ข้าม Variant ของ PO ใน `exclude_po_ids` หาก MAT_CODE พบเฉพาะใน PO ที่ยกเว้นทั้งหมด จะข้ามการตรวจสินค้านั้นและนับใน coverage `15_excluded_po_products` หากมีทั้ง PO ที่ยกเว้นและไม่ยกเว้น จะใช้เฉพาะแถวที่ไม่ยกเว้น ข้อ 15 ไม่ใช้ POP และไม่เชื่อม PRICE_MST ผ่าน POP จึงไม่ใช้ `exclude_pop_ids` กรอง Product Master

### แหล่งข้อมูลและรายงาน

- ข้อมูลหลักที่ต้องใช้มีเฉพาะ `Product_Variants` ของ Product Offer ไม่ต้องใช้ Char_Value หรือไฟล์ POP เมื่อเลือกเฉพาะข้อ 15
- PRODUCT_MST ต้องมี `PRODUCT_ID`, `MAT_CODE`, `PRODUCT_TYPE`, `CATEGORY`, `EXPIRE_DATE`
- PRICE_MST ต้องมี `PRODUCT_ID`, `PRICE_ID`, `PRICE_GROUP`, `EFFECTIVE_DATE`, `EXPIRE_DATE`
- เมื่อใช้ `--csv` ให้อ่าน PRODUCT_MST และ PRICE_MST จาก `Database` โดยไม่เชื่อมฐานข้อมูล รองรับชื่อไฟล์มี timestamp ตามกฎกลาง หากเชื่อมฐานข้อมูลไม่ได้ให้ fallback เช่นเดียวกัน
- หากข้อมูลอ้างอิงหาย คอลัมน์ไม่ครบ หรือ query ไม่สำเร็จ ให้เป็น Review `MAT_CODE_LOOKUP_UNAVAILABLE` และ `complete=false` ไม่ถือว่า MAT_CODE ไม่พบใน Variant
- ผลอยู่ในชีต `Rule 15` ของ Error หรือ Review Report ตามระดับปัญหา พร้อม SKU/MAT_CODE และ PRODUCT_ID ใน Related Evidence และแสดงผลใน summary เช่นเดียวกับข้ออื่น รายงาน Error รวมเปลี่ยนชื่อเป็น `Result_check_PO_POP_01-15_ErrorOnly_<วันเวลา>.xlsx`
- `summary.json` แสดงวันที่ที่ใช้ตรวจใน `coverage.15_run_date_bangkok`, จำนวนแถว PRODUCT_MST ทั้งหมด, จำนวนสินค้าที่เข้าเงื่อนไข และจำนวนกลุ่มราคาที่ตรวจ แถวของ Product Master ที่เข้าเงื่อนไขแต่ไม่พบ Variant ยังคงถูกตรวจและรายงาน ไม่ถูกตัดออกด้วยการ join กับ Variant ก่อน

## สรุปความครบถ้วน

ทุก Record ถูกอ่าน ไม่มี Sampling ข้อที่มี Review ยังคงแสดง `complete=false`
รายการ Review ไม่ถูกนับเป็น Error หรือ Pass โดยปริยาย
หนึ่งต้นเหตุอาจผิดหลายข้อ เช่น POP ไม่มี Characteristic และ Variant ไม่มี model ทำให้ข้อ 5 และข้อ 6 ผิด
ห้ามรวมจำนวน Error แล้วตีความเป็นจำนวน PO/POP ที่ไม่ซ้ำ
