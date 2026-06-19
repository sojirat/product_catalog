-- =============================================================================
-- FILE: 01_staging_and_batch_tables.sql
-- PURPOSE: สร้างและ migrate tables ที่ใช้รับข้อมูล + ติดตาม batch การนำเข้า
--
-- สามารถ run ซ้ำได้ปลอดภัยทุกครั้ง
--
-- TABLE ที่สร้าง:
--   1. PRODUCT_MST          — master table หลักของสินค้า (พร้อม audit columns)
--   2. ingest_batch         — header บันทึกแต่ละรอบที่นำเข้าข้อมูล
--   3. ingest_batch_detail  — รายละเอียดระดับแถวว่าแต่ละ PRODUCT_ID ถูกทำอะไร
--
-- MIGRATION GUARDS (Section 4–5):
--   ถ้า table มีอยู่แล้ว จะเพิ่มเฉพาะ column ที่ยังขาด ไม่ drop ข้อมูลเดิม
-- =============================================================================

DELIMITER $$

DROP PROCEDURE IF EXISTS staging_and_batch_tables$$

CREATE PROCEDURE staging_and_batch_tables()

BEGIN

	-- -----------------------------------------------------------------------------
	-- 1. PRODUCT_MST — master table หลักของสินค้า
	--
	--    แบ่ง columns ออกเป็น 4 กลุ่มตาม downstream ที่ใช้:
	--      • IDENTITY / NAME   → generate_product_offering  (ชื่อ PO)
	--      • VARIANT           → generate_product_offering_variant
	--      • CLASSIFICATION    → product_type_mapping, spec_characteristics
	--      • PRICE             → generate_product_offering_price
	--      • MISC              → columns จาก source system (SAP) เก็บไว้ครบ
	--      • TRACKING          → audit + batch tracking โดยระบบ (ไม่มาจาก source)
	-- -----------------------------------------------------------------------------
	CREATE TABLE IF NOT EXISTS PRODUCT_MST (
			-- KEY ----------------------------------------------------------------
			PK									VARCHAR(255),
			PRODUCT_ID          VARCHAR(255)    NOT NULL,   -- รหัสสินค้าหลัก (unique ต่อ product)
			MAT_CODE            VARCHAR(255)    NOT NULL,   -- material code จาก SAP (unique ต่อ SKU)

			-- IDENTITY / NAME --- ใช้ตั้งชื่อ Product Offering -------------------
			MAIN_MODEL          VARCHAR(500),               -- ชื่อ model หลัก เช่น "Galaxy S25"
			COMMERCIAL_NAME     VARCHAR(500),               -- ชื่อเชิงพาณิชย์ (fallback ถ้าไม่มี MAIN_MODEL)
			SAP_DESCRIPTION     VARCHAR(500),               -- คำอธิบายจาก SAP (fallback ลำดับ 3)
			BRAND               VARCHAR(255),               -- แบรนด์ เช่น Samsung, Apple
			COMPANY             VARCHAR(255),               -- บริษัทผู้นำเข้า/ผู้จัดจำหน่าย
			GRADE               VARCHAR(50),                -- เกรดสินค้า เช่น GD, DEM (ต่อท้ายชื่อ PO)

			-- VARIANT --- กำหนด combination ของ variant -------------------------
			COLOR               VARCHAR(255),               -- สี เช่น Black, White, Titanium
			CAPACITY            VARCHAR(255),               -- ความจุ เช่น 128GB, 256GB

			-- CLASSIFICATION --- ใช้ map กับ product_type_mapping ---------------
			PRODUCT_TYPE        VARCHAR(100),               -- ประเภทสินค้า เช่น DEVICE
			PRODUCT_SUBTYPE     VARCHAR(100),               -- ประเภทย่อย เช่น SMARTPHONE
			CATEGORY            VARCHAR(100),               -- หมวดหมู่ เช่น NORM, DEMO
			VALUATION_CLASS     VARCHAR(100),               -- กลุ่มมูลค่า ใช้สร้าง category_id

			-- PRICE --- กำหนดช่วงเวลาที่ราคามีผล --------------------------------
			EFFECTIVE_DATE      DATE,                       -- วันที่เริ่มใช้ราคา
			EXPIRE_DATE         DATETIME,                   -- วันหมดอายุราคา

			-- MISC --- columns จาก SAP/source system เก็บไว้ครบเพื่อ traceability
			ACT_TYPE            VARCHAR(255),
			ACTIVE_FLAG         VARCHAR(255),               -- สถานะ active ของ record
			MAT_TYPE            VARCHAR(255),               -- ประเภท material ใน SAP
			MODEL               VARCHAR(255),               -- model code จาก SAP
			UNIT_NAME           VARCHAR(255),               -- หน่วยนับ เช่น EA (each)
			CREATED_BY          VARCHAR(255),               -- ผู้สร้างใน source system
			DATE_CREATED        VARCHAR(255),               -- วันสร้างใน source system
			LAST_UPDATED        VARCHAR(255),               -- วันอัปเดตล่าสุดใน source system
			UPDATED_BY          VARCHAR(255),               -- ผู้อัปเดตใน source system
			FEATURE             VARCHAR(255),               -- feature พิเศษของสินค้า
			VENDOR_CODE         VARCHAR(255),               -- รหัส vendor ใน SAP
			DIVISION            VARCHAR(255),               -- division ใน SAP
			VAT_TYPE            VARCHAR(255),               -- ประเภท VAT
			REGION              VARCHAR(255),               -- ภูมิภาค
			SUB_REGION          VARCHAR(255),               -- ภูมิภาคย่อย
			NETWORK             VARCHAR(255),               -- network ที่รองรับ
			FACE_VALUE          VARCHAR(255),               -- มูลค่าหน้าบัตร (สำหรับ SIM/voucher)
			PRODUCT_HIERARCHY   VARCHAR(255),               -- ลำดับชั้น product ใน SAP
			PROCESS_ID          VARCHAR(255),               -- รหัส process ที่สร้าง record
			DATA_FILE_NAME      VARCHAR(255),               -- ชื่อไฟล์ที่นำเข้า
			PROCESS_DATE        VARCHAR(255),               -- วันที่ process
			DATA_VERSION        VARCHAR(255),               -- version ของ data
			FREE_GOODS          VARCHAR(255),               -- ของแถม
			OLD_MAT_NO          VARCHAR(255),               -- material number เดิม (ก่อน migrate)

			-- TRACKING --- กรอกโดยระบบ load_product_mst() ทั้งหมด ไม่มาจาก source
			new_hash            VARCHAR(64),                -- SHA2-256 hash ของ business columns ใช้ detect การเปลี่ยนแปลง
			batch_id_insert     INT,                        -- batch_id ที่ INSERT แถวนี้ครั้งแรก
			batch_id_update     INT,                        -- batch_id ล่าสุดที่ UPDATE แถวนี้
			isGenerate          TINYINT,                    -- 0 = รอ generate downstream, 1 = generate แล้ว
			system_created_by          VARCHAR(255) DEFAULT 'system',  -- ชื่อ user/ระบบที่ INSERT
			system_created_at          DATETIME(3)  DEFAULT NOW(3),    -- เวลาที่ INSERT ครั้งแรก
			system_updated_by          VARCHAR(255) DEFAULT NULL,      -- ชื่อ user/ระบบที่ UPDATE ล่าสุด
			system_updated_at          DATETIME(3)  DEFAULT NULL,      -- เวลาที่ UPDATE ล่าสุด

			PRIMARY KEY (PRODUCT_ID),
			INDEX idx_stg_pid   (PRODUCT_ID)
	) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;


	-- -----------------------------------------------------------------------------
	-- 2. INGEST_BATCH — header บันทึกแต่ละรอบที่นำเข้าข้อมูล
	--
	--    1 row = 1 รอบการ CALL load_product_mst()
	--    ใช้ดูว่ารอบไหนทำเมื่อไหร่ ใครทำ ผลเป็นอย่างไร
	-- -----------------------------------------------------------------------------
	CREATE TABLE IF NOT EXISTS ingest_batch (
			batch_id            INT             AUTO_INCREMENT PRIMARY KEY,
			batch_name          VARCHAR(255),               -- ชื่อรอบที่ระบุตอนเรียก เช่น 'SAP export 2025-04-24'
			created_by          VARCHAR(255)    DEFAULT 'system',   -- ชื่อ user หรือ 'system' ถ้าไม่ระบุ
			created_at          DATETIME(3)     DEFAULT NOW(3),     -- เวลาที่เปิด batch
			started_at          DATETIME(3)     DEFAULT NOW(3),     -- เวลาเริ่ม process
			finished_at         DATETIME(3),                        -- เวลาเสร็จ (NULL ถ้ายัง RUNNING)
			status              ENUM('RUNNING','SUCCESS','ERROR')   DEFAULT 'RUNNING',
			row_total           INT             DEFAULT 0,          -- จำนวน rows ทั้งหมดใน staging
			row_inserted        INT             DEFAULT 0,          -- rows ที่ INSERT ใหม่
			row_updated         INT             DEFAULT 0,          -- rows ที่ UPDATE (hash เปลี่ยน)
			row_unchanged       INT             DEFAULT 0,          -- rows ที่ไม่เปลี่ยน (hash เหมือนเดิม)
			downstream_triggered TINYINT(1)    DEFAULT 0,          -- 1 = มีการ call generate_all()
			error_message       TEXT,                               -- error message ถ้า status = ERROR

			INDEX idx_batch_status  (status),
			INDEX idx_batch_started (started_at),
			INDEX idx_batch_actor   (created_by)
	) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


	-- -----------------------------------------------------------------------------
	-- 3. INGEST_BATCH_DETAIL — รายละเอียดระดับแถวของแต่ละ batch
	--
	--    1 row = 1 PRODUCT_ID ใน 1 batch
	--    ใช้ตอบคำถาม "รอบนี้มีสินค้าอะไรเพิ่ม/เปลี่ยน/ไม่เปลี่ยน"
	--    และ "column ไหนที่เปลี่ยน → downstream ไหนต้อง re-generate"
	-- -----------------------------------------------------------------------------
	CREATE TABLE IF NOT EXISTS ingest_batch_detail (
			id                  BIGINT          AUTO_INCREMENT PRIMARY KEY,
			batch_id            INT             NOT NULL,           -- FK → ingest_batch
			PRODUCT_ID          VARCHAR(255)    NOT NULL,
			MAT_CODE            VARCHAR(255)    NOT NULL,
			action              ENUM('INSERT','UPDATE','UNCHANGED') NOT NULL,
			actioned_at         DATETIME(3)     DEFAULT NOW(3),     -- เวลาที่ดำเนินการ

			-- สำหรับ UPDATE: JSON array ของ column ที่เปลี่ยนจริง
			-- เช่น '["COLOR","CAPACITY","EFFECTIVE_DATE"]'
			changed_columns     JSON,

			-- hash ก่อน/หลัง เพื่อ audit และ verify
			old_row_hash        VARCHAR(64),                        -- hash ก่อน update (NULL สำหรับ INSERT)
			new_row_hash        VARCHAR(64),                        -- hash หลัง update

			-- downstream flags: บอกว่า column ที่เปลี่ยนกระทบ domain ไหน
			-- ใช้โดย generate_all() เพื่อ skip step ที่ไม่จำเป็น
			needs_offering      TINYINT(1)      DEFAULT 0,  -- MAIN_MODEL/COMMERCIAL_NAME/SAP_DESCRIPTION/BRAND เปลี่ยน
			needs_variant       TINYINT(1)      DEFAULT 0,  -- COLOR/CAPACITY เปลี่ยน
			needs_price         TINYINT(1)      DEFAULT 0,  -- EFFECTIVE_DATE/EXPIRE_DATE เปลี่ยน
			needs_promotion			TINYINT(1)      DEFAULT 0,	-- MAIN_MODEL/COMMERCIAL_NAME/SAP_DESCRIPTION/BRAND เปลี่ยน
			needs_contract_master	TINYINT(1)    DEFAULT 0,	-- BRAND/MODEL/MAT_CODE/PRODUCT_TYPE/PRODUCT_SUBTYPE/COLOR/EFFECTIVE_DATE/EXPIRE_DATE เปลี่ยน

			INDEX idx_detail_batch  (batch_id),
			INDEX idx_detail_pid    (PRODUCT_ID),
			INDEX idx_detail_action (batch_id, action),
			FOREIGN KEY (batch_id) REFERENCES ingest_batch(batch_id)
	) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

	-- -----------------------------------------------------------------------------
	-- 4. MIGRATION: เพิ่ม columns ใน stg_product_mst ที่อาจสร้างไว้ก่อน DDL นี้
	--    guard ด้วย INFORMATION_SCHEMA → run ซ้ำได้ปลอดภัย ไม่ error ถ้ามีอยู่แล้ว
	-- -----------------------------------------------------------------------------

	-- stg_loaded_at: เวลาที่ load ข้อมูลเข้า staging (กรอกโดยระบบอัตโนมัติ)
	SET @sql = IF(
			NOT EXISTS (
					SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
					WHERE TABLE_SCHEMA = DATABASE()
						AND TABLE_NAME   = 'stg_product_mst'
						AND COLUMN_NAME  = 'stg_loaded_at'
			),
			'ALTER TABLE stg_product_mst ADD COLUMN stg_loaded_at DATETIME(3) DEFAULT NOW(3)',
			'SELECT ''stg_loaded_at already exists'' AS msg'
	);
	PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

	-- stg_source_note: ระบุที่มาของข้อมูล เช่น 'SAP export 2025-04-24' (optional)
	SET @sql = IF(
			NOT EXISTS (
					SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
					WHERE TABLE_SCHEMA = DATABASE()
						AND TABLE_NAME   = 'stg_product_mst'
						AND COLUMN_NAME  = 'stg_source_note'
			),
			'ALTER TABLE stg_product_mst ADD COLUMN stg_source_note VARCHAR(500)',
			'SELECT ''stg_source_note already exists'' AS msg'
	);
	PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

	-- -----------------------------------------------------------------------------
	-- 5. COLLATION ALIGNMENT: ตรวจสอบ collation ของ PRODUCT_MST
	--    แล้ว align stg_product_mst ให้ตรงกันอัตโนมัติ
	--
	--    ไม่ hardcode ค่า collation — ดึงจากตารางจริงเสมอ
	--    ป้องกัน "Illegal mix of collations" ตอน JOIN ระหว่างสองตาราง
	-- -----------------------------------------------------------------------------

	-- ดึง collation ปัจจุบันของทั้งสองตาราง
	SET @pm_collation = (
			SELECT TABLE_COLLATION
			FROM INFORMATION_SCHEMA.TABLES
			WHERE TABLE_SCHEMA = DATABASE()
				AND TABLE_NAME   = 'PRODUCT_MST'
	);

	SET @stg_collation = (
			SELECT TABLE_COLLATION
			FROM INFORMATION_SCHEMA.TABLES
			WHERE TABLE_SCHEMA = DATABASE()
				AND TABLE_NAME   = 'stg_product_mst'
	);

	-- ถ้า collation ต่างกัน → แปลง stg ให้ตรงกับ PRODUCT_MST
	-- ถ้าเหมือนกันแล้ว → ข้ามไป
	SET @sql = IF(
			@stg_collation <> @pm_collation,
			CONCAT('ALTER TABLE stg_product_mst CONVERT TO CHARACTER SET utf8mb4 COLLATE ', @pm_collation),
			'SELECT ''stg_product_mst collation already matches PRODUCT_MST'' AS msg'
	);
	PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

END$$

DELIMITER ;