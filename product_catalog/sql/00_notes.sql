-- =============================================================================
-- FILE: 00_notes.sql
-- PURPOSE: ขั้นตอนในการใช้งานและการตั้งค่าต่างๆ
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. IMPORT PRODUCT_MST & CLEAN NULL TO STRINGS
--    นำเข้าไฟล์ PRODUCT_MST เป็น TABLE ชื่ออะไรก็ได้
--    ใช้ CALL fix_all_null_strings('TABLE NAME') ในการ CLEAN DATA
-- -----------------------------------------------------------------------------

-- ทำทุก table ใน schema (เหมือนเดิม)
CALL fix_all_null_strings(NULL);
CALL fix_all_null_strings('');

-- ทำเฉพาะ table ที่ระบุ
-- CALL fix_all_null_strings('PRODUCT_MST_01');
-- CALL fix_all_null_strings('PRODUCT_MST_01, PRODUCT_MST_02');
-- CALL fix_all_null_strings('PRODUCT_MST_02_edit, PRODUCT_MST_03_edit');
-- CALL fix_all_null_strings('PRODUCT_MST_01, PRODUCT_MST_02, PRODUCT_MST_03');
-- CALL fix_all_null_strings('PRICE_MST, PRODUCT_MST, TR_DISCOUNT, TR_MST, TR_PRODUCT');
CALL fix_all_null_strings('TR_DISCOUNT, TR_FREE_GOODS, TR_MST, TR_PRODUCT');


-- -----------------------------------------------------------------------------
-- 2. COPY TABLE
--    ถ้ามี TABLE stg_product_mst อยู่ก่อนแล้ว ให้ DROP TABLE IF EXISTS stg_product_mst; ก่อน
--    ใช้คำสั่ง CREATE TABLE stg_product_mst AS SELECT * FROM PRODUCT_MST_01_TEST;
-- -----------------------------------------------------------------------------
DROP TABLE IF EXISTS stg_product_mst;
CREATE TABLE stg_product_mst AS SELECT * FROM PRODUCT_MST_20260508;

-- -----------------------------------------------------------------------------
-- 3. MIGRATE TABLE
--    สร้างและ migrate table ที่ใช้รับข้อมูล + ติดตาม batch การนำเข้า
-- -----------------------------------------------------------------------------
CALL staging_and_batch_tables();

-- -----------------------------------------------------------------------------
-- 4. LOAD TO PRODUCT_MST AND GENERATE PO, POP
--    สร้างและ migrate table ที่ใช้รับข้อมูล + ติดตาม batch การนำเข้า
-- -----------------------------------------------------------------------------
CALL load_product_mst('MIGRATE_DATA_20260508', 'sojirat.s');