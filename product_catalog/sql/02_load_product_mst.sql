-- =============================================================================
-- FILE: 02_load_product_mst.sql
-- PURPOSE: รับข้อมูลจาก stg_product_mst → เปรียบเทียบกับ PRODUCT_MST
--          แล้วแบ่งเป็น INSERT / UPDATE / UNCHANGED พร้อม audit trail ครบถ้วน
--
-- FLOW:
--   stg_product_mst → clean → hash → เปรียบ → INSERT/UPDATE/UNCHANGED
--   → ingest_batch + ingest_batch_detail → generate_all() ถ้ามี downstream
--
-- HOW TO USE:
--   -- ระบุชื่อผู้ทำ
--   CALL load_product_mst('SAP export 2025-04-24', 'somchai.k');
--
--   -- ไม่ระบุชื่อ → บันทึกเป็น 'system' อัตโนมัติ
--   CALL load_product_mst('scheduled job 02:00', NULL);
--
-- AUDIT COLUMNS ใน PRODUCT_MST:
--   system_created_by / system_created_at  → กรอกตอน INSERT ครั้งแรก
--   system_updated_by / system_updated_at  → อัปเดตทุกครั้งที่ข้อมูลเปลี่ยน
--   new_hash     → SHA2-256 ของ business columns ใช้ detect การเปลี่ยนแปลง
--   batch_id_insert / batch_id_update      → FK → ingest_batch
--
-- FIX (2026-05-08):
--   - เปลี่ยน JOIN key ทุกจุดจาก MAT_CODE → PRODUCT_ID (ตรงกับ PRIMARY KEY จริง)
--   - เปลี่ยน INDEX ใน tmp_stg_hashed จาก MAT_CODE → PRODUCT_ID
--   - เพิ่ม INSERT IGNORE ใน STEP 4 กัน duplicate กรณี race condition
--   - เพิ่ม guard ใน EXIT HANDLER (IF v_batch_id > 0) กัน UPDATE ไม่เจอ row
--
-- FIX (2026-06-30):
--   - เพิ่ม FUNCTION clean_name_raw() (แก้ bug "DELIMITER;" → "DELIMITER ;" ที่จะทำให้
--     สคริปต์รันไม่ผ่าน, และเพิ่มขั้นตอนลบสระ/วรรณยุกต์นำหน้าข้อความ)
--   - STEP 1: TRIM + UPPER + clean_name_raw() ให้กับ MAIN_MODEL, COMMERCIAL_NAME,
--     SAP_DESCRIPTION, BRAND, COMPANY, GRADE, COLOR, CAPACITY, MODEL, UNIT_NAME
--     ก่อนเก็บลง tmp_stg_hashed และก่อนคำนวณ new_hash (เพื่อให้ hash สะท้อนค่า
--     ที่ clean แล้วจริง ๆ ไม่งั้น UPDATE/UNCHANGED detection จะผิดเพี้ยน)
-- =============================================================================

DELIMITER $$

DROP PROCEDURE IF EXISTS load_product_mst$$

CREATE PROCEDURE load_product_mst(
    IN  p_batch_name    VARCHAR(255),
    IN  p_created_by    VARCHAR(255)    -- NULL → ใช้ 'system'
)
proc_label: BEGIN

    DECLARE v_batch_id      INT     DEFAULT 0;
    DECLARE v_total         INT     DEFAULT 0;
    DECLARE v_inserted      INT     DEFAULT 0;
    DECLARE v_updated       INT     DEFAULT 0;
    DECLARE v_unchanged     INT     DEFAULT 0;
    DECLARE v_downstream    INT     DEFAULT 0;
    DECLARE v_actor         VARCHAR(255);
    DECLARE v_error         TEXT;

    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        GET DIAGNOSTICS CONDITION 1 v_error = MESSAGE_TEXT;
        ROLLBACK;
        -- FIX: guard กัน v_batch_id = 0 กรณี error ก่อน INSERT batch
        IF v_batch_id > 0 THEN
            UPDATE ingest_batch
            SET status        = 'ERROR',
                finished_at   = NOW(3),
                error_message = v_error
            WHERE batch_id = v_batch_id;
        END IF;
        RESIGNAL;
    END;

    -- ถ้าไม่ส่งชื่อมา → ใช้ 'system'
    SET v_actor = IFNULL(NULLIF(TRIM(p_created_by), ''), 'system');

    -- บังคับ collation ทั้ง session ให้ตรงกับ PRODUCT_MST
    SET NAMES utf8mb4 COLLATE utf8mb4_general_ci;

    -- ================================================================
    -- STEP 0: เปิด batch — บันทึกชื่อคน + เวลาเริ่ม
    -- ================================================================
    INSERT INTO ingest_batch (batch_name, started_at, status, created_by, created_at)
    VALUES (p_batch_name, NOW(3), 'RUNNING', v_actor, NOW(3));
    SET v_batch_id = LAST_INSERT_ID();

    -- ================================================================
    -- STEP 1: คำนวณ hash ใน staging
    --         CONVERT ทุก string column ให้ตรง collation กับ PRODUCT_MST
    --         เพื่อหลีกเลี่ยง "Illegal mix of collations"
    --         + clean_name_raw()/TRIM/UPPER กับคอลัมน์ที่กำหนด ก่อนเก็บและก่อน hash
    -- ================================================================
    DROP TEMPORARY TABLE IF EXISTS tmp_stg_hashed;
    CREATE TEMPORARY TABLE tmp_stg_hashed (
        PK              VARCHAR(255)    CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci,
        PRODUCT_ID      VARCHAR(255)    CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci,
        MAT_CODE        VARCHAR(255)    CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci,
        MAIN_MODEL      VARCHAR(500)    CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci,
        COMMERCIAL_NAME VARCHAR(500)    CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci,
        SAP_DESCRIPTION VARCHAR(500)    CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci,
        BRAND           VARCHAR(255)    CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci,
        COMPANY         VARCHAR(255)    CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci,
        GRADE           VARCHAR(50)     CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci,
        COLOR           VARCHAR(255)    CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci,
        CAPACITY        VARCHAR(255)    CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci,
        PRODUCT_TYPE    VARCHAR(100)    CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci,
        PRODUCT_SUBTYPE VARCHAR(100)    CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci,
        CATEGORY        VARCHAR(100)    CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci,
        VALUATION_CLASS     VARCHAR(100)    CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci,
        ACT_TYPE            VARCHAR(255)    CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci,
        ACTIVE_FLAG         VARCHAR(255)    CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci,
        MAT_TYPE            VARCHAR(255)    CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci,
        MODEL               VARCHAR(255)    CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci,
        UNIT_NAME           VARCHAR(255)    CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci,
        CREATED_BY          VARCHAR(255)    CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci,
        DATE_CREATED        VARCHAR(255)    CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci,
        LAST_UPDATED        VARCHAR(255)    CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci,
        UPDATED_BY          VARCHAR(255)    CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci,
        FEATURE             VARCHAR(255)    CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci,
        VENDOR_CODE         VARCHAR(255)    CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci,
        DIVISION            VARCHAR(255)    CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci,
        VAT_TYPE            VARCHAR(255)    CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci,
        REGION              VARCHAR(255)    CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci,
        SUB_REGION          VARCHAR(255)    CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci,
        NETWORK             VARCHAR(255)    CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci,
        FACE_VALUE          VARCHAR(255)    CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci,
        PRODUCT_HIERARCHY   VARCHAR(255)    CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci,
        PROCESS_ID          VARCHAR(255)    CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci,
        DATA_FILE_NAME      VARCHAR(255)    CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci,
        PROCESS_DATE        VARCHAR(255)    CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci,
        DATA_VERSION        VARCHAR(255)    CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci,
        FREE_GOODS          VARCHAR(255)    CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci,
        OLD_MAT_NO          VARCHAR(255)    CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci,
        EFFECTIVE_DATE      DATE,
        EXPIRE_DATE         DATETIME,
        new_hash            VARCHAR(64)     CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci
    );

    INSERT INTO tmp_stg_hashed
    SELECT
        CONVERT(s.PK              USING utf8mb4) COLLATE utf8mb4_general_ci,
        CONVERT(s.PRODUCT_ID      USING utf8mb4) COLLATE utf8mb4_general_ci,
        CONVERT(s.MAT_CODE        USING utf8mb4) COLLATE utf8mb4_general_ci,
        -- FIX: clean_name_raw + TRIM + UPPER สำหรับคอลัมน์ที่ต้อง clean
        UPPER(TRIM(clean_name_raw(CONVERT(s.MAIN_MODEL      USING utf8mb4)))) COLLATE utf8mb4_general_ci,
        UPPER(TRIM(clean_name_raw(CONVERT(s.COMMERCIAL_NAME USING utf8mb4)))) COLLATE utf8mb4_general_ci,
        UPPER(TRIM(clean_name_raw(CONVERT(s.SAP_DESCRIPTION USING utf8mb4)))) COLLATE utf8mb4_general_ci,
        UPPER(TRIM(clean_name_raw(CONVERT(s.BRAND           USING utf8mb4)))) COLLATE utf8mb4_general_ci,
        UPPER(TRIM(clean_name_raw(CONVERT(s.COMPANY         USING utf8mb4)))) COLLATE utf8mb4_general_ci,
        UPPER(TRIM(clean_name_raw(CONVERT(s.GRADE           USING utf8mb4)))) COLLATE utf8mb4_general_ci,
        UPPER(TRIM(clean_name_raw(CONVERT(s.COLOR           USING utf8mb4)))) COLLATE utf8mb4_general_ci,
        UPPER(TRIM(clean_name_raw(CONVERT(s.CAPACITY        USING utf8mb4)))) COLLATE utf8mb4_general_ci,
        CONVERT(s.PRODUCT_TYPE    USING utf8mb4) COLLATE utf8mb4_general_ci,
        CONVERT(s.PRODUCT_SUBTYPE USING utf8mb4) COLLATE utf8mb4_general_ci,
        CONVERT(s.CATEGORY        USING utf8mb4) COLLATE utf8mb4_general_ci,
        CONVERT(s.VALUATION_CLASS USING utf8mb4) COLLATE utf8mb4_general_ci,
        CONVERT(s.ACT_TYPE        USING utf8mb4) COLLATE utf8mb4_general_ci,
        CONVERT(s.ACTIVE_FLAG     USING utf8mb4) COLLATE utf8mb4_general_ci,
        CONVERT(s.MAT_TYPE        USING utf8mb4) COLLATE utf8mb4_general_ci,
        UPPER(TRIM(clean_name_raw(CONVERT(s.MODEL            USING utf8mb4)))) COLLATE utf8mb4_general_ci,
        UPPER(TRIM(clean_name_raw(CONVERT(s.UNIT_NAME        USING utf8mb4)))) COLLATE utf8mb4_general_ci,
        CONVERT(s.CREATED_BY      USING utf8mb4) COLLATE utf8mb4_general_ci,
        CONVERT(s.DATE_CREATED    USING utf8mb4) COLLATE utf8mb4_general_ci,
        CONVERT(s.LAST_UPDATED    USING utf8mb4) COLLATE utf8mb4_general_ci,
        CONVERT(s.UPDATED_BY      USING utf8mb4) COLLATE utf8mb4_general_ci,
        CONVERT(s.FEATURE         USING utf8mb4) COLLATE utf8mb4_general_ci,
        CONVERT(s.VENDOR_CODE     USING utf8mb4) COLLATE utf8mb4_general_ci,
        CONVERT(s.DIVISION        USING utf8mb4) COLLATE utf8mb4_general_ci,
        CONVERT(s.VAT_TYPE        USING utf8mb4) COLLATE utf8mb4_general_ci,
        CONVERT(s.REGION          USING utf8mb4) COLLATE utf8mb4_general_ci,
        CONVERT(s.SUB_REGION      USING utf8mb4) COLLATE utf8mb4_general_ci,
        CONVERT(s.NETWORK         USING utf8mb4) COLLATE utf8mb4_general_ci,
        CONVERT(s.FACE_VALUE      USING utf8mb4) COLLATE utf8mb4_general_ci,
        CONVERT(s.PRODUCT_HIERARCHY USING utf8mb4) COLLATE utf8mb4_general_ci,
        CONVERT(s.PROCESS_ID      USING utf8mb4) COLLATE utf8mb4_general_ci,
        CONVERT(s.DATA_FILE_NAME  USING utf8mb4) COLLATE utf8mb4_general_ci,
        CONVERT(s.PROCESS_DATE    USING utf8mb4) COLLATE utf8mb4_general_ci,
        CONVERT(s.DATA_VERSION    USING utf8mb4) COLLATE utf8mb4_general_ci,
        CONVERT(s.FREE_GOODS      USING utf8mb4) COLLATE utf8mb4_general_ci,
        CONVERT(s.OLD_MAT_NO      USING utf8mb4) COLLATE utf8mb4_general_ci,
        s.EFFECTIVE_DATE,
        s.EXPIRE_DATE,
        -- FIX: hash ต้องคำนวณจากค่าที่ clean แล้ว (เหมือนค่าที่จะถูกเก็บจริง)
        SHA2(CONCAT_WS('||',
            IFNULL(s.PRODUCT_ID,         ''),
            IFNULL(s.MAT_CODE,           ''),
            IFNULL(UPPER(TRIM(clean_name_raw(s.MAIN_MODEL))),      ''),
            IFNULL(UPPER(TRIM(clean_name_raw(s.COMMERCIAL_NAME))), ''),
            IFNULL(UPPER(TRIM(clean_name_raw(s.SAP_DESCRIPTION))), ''),
            IFNULL(UPPER(TRIM(clean_name_raw(s.BRAND))),           ''),
            IFNULL(UPPER(TRIM(clean_name_raw(s.COMPANY))),         ''),
            IFNULL(UPPER(TRIM(clean_name_raw(s.GRADE))),           ''),
            IFNULL(UPPER(TRIM(clean_name_raw(s.COLOR))),           ''),
            IFNULL(UPPER(TRIM(clean_name_raw(s.CAPACITY))),        ''),
            IFNULL(s.PRODUCT_TYPE,       ''),
            IFNULL(s.PRODUCT_SUBTYPE,    ''),
            IFNULL(s.CATEGORY,           ''),
            IFNULL(s.VALUATION_CLASS,    ''),
            IFNULL(CAST(s.EFFECTIVE_DATE AS CHAR), ''),
            IFNULL(CAST(s.EXPIRE_DATE    AS CHAR), '')
        ), 256)
    FROM stg_product_mst s;

    -- FIX: เปลี่ยน index จาก MAT_CODE → PRODUCT_ID ให้ตรงกับ PK จริง
    ALTER TABLE tmp_stg_hashed ADD INDEX idx_tmp_pid (PRODUCT_ID);
    SELECT COUNT(*) INTO v_total FROM tmp_stg_hashed;

    -- ================================================================
    -- STEP 2: แยก INSERT / UPDATE / UNCHANGED
    -- FIX: เปลี่ยน JOIN key จาก MAT_CODE → PRODUCT_ID ทุกจุด
    -- ================================================================
    DROP TEMPORARY TABLE IF EXISTS tmp_to_insert;
    CREATE TEMPORARY TABLE tmp_to_insert AS
    SELECT t.*
    FROM tmp_stg_hashed t
    LEFT JOIN PRODUCT_MST pm ON pm.PRODUCT_ID = t.PRODUCT_ID  -- FIX
    WHERE pm.PRODUCT_ID IS NULL;                               -- FIX
    SELECT COUNT(*) INTO v_inserted FROM tmp_to_insert;

    DROP TEMPORARY TABLE IF EXISTS tmp_to_update;
    CREATE TEMPORARY TABLE tmp_to_update AS
    SELECT t.*, pm.new_hash AS old_hash
    FROM tmp_stg_hashed t
    JOIN PRODUCT_MST pm ON pm.PRODUCT_ID = t.PRODUCT_ID       -- FIX
    WHERE pm.new_hash IS NULL
       OR pm.new_hash <> t.new_hash;
    SELECT COUNT(*) INTO v_updated FROM tmp_to_update;

    SET v_unchanged = v_total - v_inserted - v_updated;

    -- ================================================================
    -- STEP 3: START TRANSACTION
    -- ================================================================
    START TRANSACTION;

    -- ================================================================
    -- STEP 4: INSERT rows ใหม่ — บันทึก created_by + created_at
    -- FIX: เพิ่ม INSERT IGNORE กัน duplicate กรณี race condition
    -- ================================================================
    INSERT IGNORE INTO PRODUCT_MST (                           -- FIX: IGNORE
        PK, PRODUCT_ID, MAT_CODE,
        MAIN_MODEL, COMMERCIAL_NAME, SAP_DESCRIPTION, BRAND, COMPANY, GRADE,
        COLOR, CAPACITY,
        PRODUCT_TYPE, PRODUCT_SUBTYPE, CATEGORY, VALUATION_CLASS,
        ACT_TYPE, ACTIVE_FLAG, MAT_TYPE, MODEL, UNIT_NAME,
        CREATED_BY, DATE_CREATED, LAST_UPDATED, UPDATED_BY, FEATURE,
        VENDOR_CODE, DIVISION, VAT_TYPE,
        REGION, SUB_REGION, NETWORK, FACE_VALUE,
        PRODUCT_HIERARCHY, PROCESS_ID, DATA_FILE_NAME,
        PROCESS_DATE, DATA_VERSION, FREE_GOODS, OLD_MAT_NO,
        EFFECTIVE_DATE, EXPIRE_DATE,
        new_hash, batch_id_insert, batch_id_update,
        isGenerate,
        system_created_by, system_created_at,
        system_updated_by, system_updated_at
    )
    SELECT
        PK, PRODUCT_ID, MAT_CODE,
        MAIN_MODEL, COMMERCIAL_NAME, SAP_DESCRIPTION, BRAND, COMPANY, GRADE,
        COLOR, CAPACITY,
        PRODUCT_TYPE, PRODUCT_SUBTYPE, CATEGORY, VALUATION_CLASS,
        ACT_TYPE, ACTIVE_FLAG, MAT_TYPE, MODEL, UNIT_NAME,
        CREATED_BY, DATE_CREATED, LAST_UPDATED, UPDATED_BY, FEATURE,
        VENDOR_CODE, DIVISION, VAT_TYPE,
        REGION, SUB_REGION, NETWORK, FACE_VALUE,
        PRODUCT_HIERARCHY, PROCESS_ID, DATA_FILE_NAME,
        PROCESS_DATE, DATA_VERSION, FREE_GOODS, OLD_MAT_NO,
        EFFECTIVE_DATE, EXPIRE_DATE,
        new_hash, v_batch_id, NULL,
        0,
        v_actor, NOW(3),
        NULL, NULL
    FROM tmp_to_insert;

    -- ================================================================
    -- STEP 5: UPDATE rows — บันทึก updated_by + updated_at
    -- FIX: เปลี่ยน JOIN key จาก MAT_CODE → PRODUCT_ID
    -- ================================================================
    UPDATE PRODUCT_MST pm
    JOIN tmp_to_update t ON pm.PRODUCT_ID = t.PRODUCT_ID      -- FIX
    SET
        pm.PK                  = t.PK,
        pm.MAT_CODE            = t.MAT_CODE,                  -- FIX: อัปเดต MAT_CODE ด้วย (อาจเปลี่ยนได้)
        pm.MAIN_MODEL          = t.MAIN_MODEL,
        pm.COMMERCIAL_NAME     = t.COMMERCIAL_NAME,
        pm.SAP_DESCRIPTION     = t.SAP_DESCRIPTION,
        pm.BRAND               = t.BRAND,
        pm.COMPANY             = t.COMPANY,
        pm.GRADE               = t.GRADE,
        pm.COLOR               = t.COLOR,
        pm.CAPACITY            = t.CAPACITY,
        pm.PRODUCT_TYPE        = t.PRODUCT_TYPE,
        pm.PRODUCT_SUBTYPE     = t.PRODUCT_SUBTYPE,
        pm.CATEGORY            = t.CATEGORY,
        pm.VALUATION_CLASS     = t.VALUATION_CLASS,
        pm.ACT_TYPE            = t.ACT_TYPE,
        pm.ACTIVE_FLAG         = t.ACTIVE_FLAG,
        pm.MAT_TYPE            = t.MAT_TYPE,
        pm.MODEL               = t.MODEL,
        pm.UNIT_NAME           = t.UNIT_NAME,
        pm.CREATED_BY          = t.CREATED_BY,
        pm.DATE_CREATED        = t.DATE_CREATED,
        pm.LAST_UPDATED        = t.LAST_UPDATED,
        pm.UPDATED_BY          = t.UPDATED_BY,
        pm.FEATURE             = t.FEATURE,
        pm.VENDOR_CODE         = t.VENDOR_CODE,
        pm.DIVISION            = t.DIVISION,
        pm.VAT_TYPE            = t.VAT_TYPE,
        pm.REGION              = t.REGION,
        pm.SUB_REGION          = t.SUB_REGION,
        pm.NETWORK             = t.NETWORK,
        pm.FACE_VALUE          = t.FACE_VALUE,
        pm.PRODUCT_HIERARCHY   = t.PRODUCT_HIERARCHY,
        pm.PROCESS_ID          = t.PROCESS_ID,
        pm.DATA_FILE_NAME      = t.DATA_FILE_NAME,
        pm.PROCESS_DATE        = t.PROCESS_DATE,
        pm.DATA_VERSION        = t.DATA_VERSION,
        pm.FREE_GOODS          = t.FREE_GOODS,
        pm.OLD_MAT_NO          = t.OLD_MAT_NO,
        pm.EFFECTIVE_DATE      = t.EFFECTIVE_DATE,
        pm.EXPIRE_DATE         = t.EXPIRE_DATE,
        pm.new_hash            = t.new_hash,
        pm.batch_id_update     = v_batch_id,
        pm.system_updated_by   = v_actor,
        pm.system_updated_at   = NOW(3),
        pm.isGenerate          = CASE
            WHEN IFNULL(pm.MAIN_MODEL,'')      <> IFNULL(t.MAIN_MODEL,'')
              OR IFNULL(pm.COMMERCIAL_NAME,'') <> IFNULL(t.COMMERCIAL_NAME,'')
              OR IFNULL(pm.SAP_DESCRIPTION,'') <> IFNULL(t.SAP_DESCRIPTION,'')
              OR IFNULL(pm.BRAND,'')           <> IFNULL(t.BRAND,'')
              OR IFNULL(pm.COMPANY,'')         <> IFNULL(t.COMPANY,'')
              OR IFNULL(pm.GRADE,'')           <> IFNULL(t.GRADE,'')
            THEN 0
            ELSE pm.isGenerate
        END;

    -- ================================================================
    -- STEP 6: บันทึก ingest_batch_detail พร้อม actioned_at
    -- FIX: เปลี่ยน JOIN key 6B และ 6C จาก MAT_CODE → PRODUCT_ID
    -- ================================================================

    -- 6A: INSERT detail
    INSERT INTO ingest_batch_detail
        (batch_id, PRODUCT_ID, MAT_CODE, action,
         changed_columns, old_row_hash, new_row_hash,
         needs_offering, needs_variant, needs_price, needs_promotion, needs_contract_master,
         actioned_at)
    SELECT
        v_batch_id, PRODUCT_ID, MAT_CODE, 'INSERT',
        NULL, NULL, new_hash,
        1, 1, 1, 1, 1,
        NOW(3)
    FROM tmp_to_insert;

    -- 6B: UPDATE detail
    INSERT INTO ingest_batch_detail
        (batch_id, PRODUCT_ID, MAT_CODE, action,
         changed_columns, old_row_hash, new_row_hash,
         needs_offering, needs_variant, needs_price, needs_promotion, needs_contract_master,
         actioned_at)
    SELECT
        v_batch_id,
        t.PRODUCT_ID,
        t.MAT_CODE,
        'UPDATE',
        JSON_ARRAY(
            CASE WHEN IFNULL(pm.MAIN_MODEL,'')      <> IFNULL(t.MAIN_MODEL,'')      THEN 'MAIN_MODEL'      END,
            CASE WHEN IFNULL(pm.COMMERCIAL_NAME,'') <> IFNULL(t.COMMERCIAL_NAME,'') THEN 'COMMERCIAL_NAME'  END,
            CASE WHEN IFNULL(pm.SAP_DESCRIPTION,'') <> IFNULL(t.SAP_DESCRIPTION,'') THEN 'SAP_DESCRIPTION'  END,
            CASE WHEN IFNULL(pm.BRAND,'')           <> IFNULL(t.BRAND,'')           THEN 'BRAND'            END,
            CASE WHEN IFNULL(pm.COLOR,'')           <> IFNULL(t.COLOR,'')           THEN 'COLOR'            END,
            CASE WHEN IFNULL(pm.CAPACITY,'')        <> IFNULL(t.CAPACITY,'')        THEN 'CAPACITY'         END,
            CASE WHEN IFNULL(CAST(pm.EFFECTIVE_DATE AS CHAR),'') <>
                      IFNULL(CAST(t.EFFECTIVE_DATE  AS CHAR),'') THEN 'EFFECTIVE_DATE'                       END,
            CASE WHEN IFNULL(CAST(pm.EXPIRE_DATE AS CHAR),'') <>
                      IFNULL(CAST(t.EXPIRE_DATE  AS CHAR),'')   THEN 'EXPIRE_DATE'                          END
        ),
        t.old_hash,
        t.new_hash,
        -- needs_offering
        CASE WHEN IFNULL(pm.MAIN_MODEL,'')      <> IFNULL(t.MAIN_MODEL,'')
              OR IFNULL(pm.COMMERCIAL_NAME,'')  <> IFNULL(t.COMMERCIAL_NAME,'')
              OR IFNULL(pm.SAP_DESCRIPTION,'')  <> IFNULL(t.SAP_DESCRIPTION,'')
              OR IFNULL(pm.BRAND,'')            <> IFNULL(t.BRAND,'')
              OR IFNULL(pm.COMPANY,'')          <> IFNULL(t.COMPANY,'')
              OR IFNULL(pm.GRADE,'')            <> IFNULL(t.GRADE,'')
         THEN 1 ELSE 0 END,
        -- needs_variant
        CASE WHEN IFNULL(pm.COLOR,'')   <> IFNULL(t.COLOR,'')
              OR IFNULL(pm.CAPACITY,'') <> IFNULL(t.CAPACITY,'')
         THEN 1 ELSE 0 END,
        -- needs_price
        CASE WHEN IFNULL(CAST(pm.EFFECTIVE_DATE AS CHAR),'') <> IFNULL(CAST(t.EFFECTIVE_DATE AS CHAR),'')
              OR IFNULL(CAST(pm.EXPIRE_DATE    AS CHAR),'')  <> IFNULL(CAST(t.EXPIRE_DATE    AS CHAR),'')
         THEN 1 ELSE 0 END,
        -- needs_promotion
        CASE WHEN IFNULL(pm.MAIN_MODEL,'')      <> IFNULL(t.MAIN_MODEL,'')
              OR IFNULL(pm.COMMERCIAL_NAME,'')  <> IFNULL(t.COMMERCIAL_NAME,'')
              OR IFNULL(pm.SAP_DESCRIPTION,'')  <> IFNULL(t.SAP_DESCRIPTION,'')
              OR IFNULL(pm.BRAND,'')            <> IFNULL(t.BRAND,'')
              OR IFNULL(pm.COMPANY,'')          <> IFNULL(t.COMPANY,'')
              OR IFNULL(pm.GRADE,'')            <> IFNULL(t.GRADE,'')
         THEN 1 ELSE 0 END,
				 -- needs_contract_master
				 CASE WHEN IFNULL(pm.BRAND,'')    <> IFNULL(t.BRAND,'')
              OR IFNULL(pm.MODEL,'')     <> IFNULL(t.MODEL,'')
              OR IFNULL(pm.MAT_CODE,'')  <> IFNULL(t.MAT_CODE,'')
              OR IFNULL(pm.PRODUCT_TYPE,'')    <> IFNULL(t.PRODUCT_TYPE,'')
              OR IFNULL(pm.PRODUCT_SUBTYPE,'') <> IFNULL(t.PRODUCT_SUBTYPE,'')
              OR IFNULL(pm.COLOR,'')     <> IFNULL(t.COLOR,'')
              OR IFNULL(CAST(pm.EFFECTIVE_DATE AS CHAR),'') <> IFNULL(CAST(t.EFFECTIVE_DATE AS CHAR),'')
              OR IFNULL(CAST(pm.EXPIRE_DATE    AS CHAR),'') <> IFNULL(CAST(t.EXPIRE_DATE    AS CHAR),'')
         THEN 1 ELSE 0 END,
        NOW(3)
    FROM tmp_to_update t
    JOIN PRODUCT_MST pm ON pm.PRODUCT_ID = t.PRODUCT_ID;      -- FIX

    -- 6C: UNCHANGED detail
    INSERT INTO ingest_batch_detail
        (batch_id, PRODUCT_ID, MAT_CODE, action,
         changed_columns, old_row_hash, new_row_hash,
         needs_offering, needs_variant, needs_price, needs_promotion, needs_contract_master,
         actioned_at)
    SELECT
        v_batch_id, t.PRODUCT_ID, t.MAT_CODE, 'UNCHANGED',
        NULL, pm.new_hash, t.new_hash,
        0, 0, 0, 0, 0,
        NOW(3)
    FROM tmp_stg_hashed t
    JOIN PRODUCT_MST pm ON pm.PRODUCT_ID = t.PRODUCT_ID       -- FIX
    WHERE pm.new_hash = t.new_hash;

    -- ================================================================
    -- STEP 7: ตรวจ downstream + อัป batch header
    -- ================================================================
    SELECT COUNT(*) INTO v_downstream
    FROM ingest_batch_detail
    WHERE batch_id = v_batch_id
      AND action IN ('INSERT','UPDATE')
      AND (needs_offering = 1 OR needs_variant = 1 OR needs_price = 1 OR needs_promotion = 1 OR needs_contract_master = 1);

    UPDATE ingest_batch
    SET row_total             = v_total,
        row_inserted          = v_inserted,
        row_updated           = v_updated,
        row_unchanged         = v_unchanged,
        downstream_triggered  = IF(v_downstream > 0, 1, 0),
        status                = 'SUCCESS',
        finished_at           = NOW(3)
    WHERE batch_id = v_batch_id;

    COMMIT;

    -- ================================================================
    -- STEP 8: เรียก generate_all ถ้ามี downstream
    -- ================================================================
    IF v_downstream > 0 THEN
        CALL generate_all(v_batch_id, v_actor);
    END IF;

    -- ================================================================
    -- STEP 9: Summary result
    -- ================================================================
    SELECT
        v_batch_id                          AS batch_id,
        p_batch_name                        AS batch_name,
        v_actor                             AS created_by,
        NOW(3)                              AS finished_at,
        v_total                             AS total_rows,
        v_inserted                          AS inserted,
        v_updated                           AS updated,
        v_unchanged                         AS unchanged,
        IF(v_downstream > 0, 'YES', 'NO')   AS downstream_triggered;

    DROP TEMPORARY TABLE IF EXISTS tmp_stg_hashed;
    DROP TEMPORARY TABLE IF EXISTS tmp_to_insert;
    DROP TEMPORARY TABLE IF EXISTS tmp_to_update;

END$$

DELIMITER ;