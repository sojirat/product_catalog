DELIMITER $$

DROP PROCEDURE IF EXISTS generate_promotion$$

CREATE PROCEDURE generate_promotion(
    IN  batch_id      INT,
    IN  p_created_by  VARCHAR(255),
    IN  p_force_rerun TINYINT(1)      -- 0 = ปกติ, 1 = force rerun (update ทุก row)
)

proc_label: BEGIN
    DECLARE v_pr_start   INT          DEFAULT 0;
    DECLARE v_pr_prefix  VARCHAR(50)  DEFAULT '';
    DECLARE v_pr_suffix  VARCHAR(50)  DEFAULT '';
    DECLARE v_pr_pad     INT          DEFAULT 6;

    DECLARE v_pa_start   INT          DEFAULT 0;
    DECLARE v_pa_prefix  VARCHAR(50)  DEFAULT '';
    DECLARE v_pa_suffix  VARCHAR(50)  DEFAULT '';
    DECLARE v_pa_pad     INT          DEFAULT 6;

    DECLARE v_new_count  INT          DEFAULT 0;
    DECLARE v_rn_offset  INT          DEFAULT 0;
    DECLARE v_actor      VARCHAR(255) DEFAULT 'system';

    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        RESIGNAL;
    END;

    SET v_actor = IFNULL(NULLIF(TRIM(p_created_by), ''), 'system');

    -- ============================================================
    -- Step 1: สร้าง tbl_promotion ถ้ายังไม่มี
    -- ============================================================
    CREATE TABLE IF NOT EXISTS tbl_promotion (
        PROMOTION_ID                 TEXT,
        PROMOTION_ACTION_ID          TEXT,
        EXTERNAL_ID                  VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci,
        PROMOTION_NAME               TEXT,
        PROMOTION_TYPE               VARCHAR(50),
        CODE                         TEXT,
        LIFECYCLE_STATUS             VARCHAR(50),
        COUPON                       TEXT,
        PROMOTION_CLASSIFICATION     VARCHAR(50),
        PROMOTION_APPLICATION_LEVEL  VARCHAR(50),
        VALID_FOR_START_DATETIME     DATETIME,
        VALID_FOR_END_DATETIME       DATETIME,
        ACTION_CARDINALITY           INT,
        ACTION_VALUE                 TEXT,
        PRICE_TYPE                   VARCHAR(50),
        PRIORITY                     TEXT,
        ACTION_OBJECT_ID             TEXT,
        PRICE_ID                     TEXT,
        ACTION_TYPE                  VARCHAR(50),
        SKU                          TEXT,
        AWARD_PRODUCT_ID             TEXT,
        VARIANT_ID                   VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci,
        PRODUCT_OFFER_ID             TEXT,
        CHARACTERISTIC_VALUE         TEXT,
        APPLICATION_DURATION         TEXT,
				TRADE_NO                   	 TEXT,
        TRADE_NAME                   TEXT,
				TRADE_DISCOUNT_ID						 VARCHAR(255),
				TRADE_PRODUCT_ID						 VARCHAR(255),
				TRADE_FREE_GOODS_ID					 VARCHAR(255),
        CAMPAIGN                     TEXT,
        PROMOTION_SOURCE             VARCHAR(50),
        rn                           INT,
        batch_id_insert              INT,
        batch_id_update              INT,
        created_by                   VARCHAR(255) DEFAULT 'system',
        created_at                   DATETIME(3)  DEFAULT NOW(3),
        updated_by                   VARCHAR(255) DEFAULT NULL,
        updated_at                   DATETIME(3)  DEFAULT NULL,
        INDEX idx_rn (rn)
    );
		
		-- ============================================================
		-- AUTO ADD MISSING COLUMNS
		-- ============================================================

		-- TRADE_NO
		SET @sql = IF(
				EXISTS (
						SELECT 1
						FROM INFORMATION_SCHEMA.COLUMNS
						WHERE TABLE_SCHEMA = DATABASE()
							AND TABLE_NAME = 'tbl_promotion'
							AND COLUMN_NAME = 'TRADE_NO'
				),
				'SELECT ''TRADE_NO already exists''',
				'ALTER TABLE tbl_promotion ADD COLUMN TRADE_NO TEXT'
		);

		PREPARE stmt FROM @sql;
		EXECUTE stmt;
		DEALLOCATE PREPARE stmt;

		-- TRADE_NAME
		SET @sql = IF(
				EXISTS (
						SELECT 1
						FROM INFORMATION_SCHEMA.COLUMNS
						WHERE TABLE_SCHEMA = DATABASE()
							AND TABLE_NAME = 'tbl_promotion'
							AND COLUMN_NAME = 'TRADE_NAME'
				),
				'SELECT ''TRADE_NAME already exists''',
				'ALTER TABLE tbl_promotion ADD COLUMN TRADE_NAME TEXT'
		);

		PREPARE stmt FROM @sql;
		EXECUTE stmt;
		DEALLOCATE PREPARE stmt;

		-- TRADE_DISCOUNT_ID
		SET @sql = IF(
				EXISTS (
						SELECT 1
						FROM INFORMATION_SCHEMA.COLUMNS
						WHERE TABLE_SCHEMA = DATABASE()
							AND TABLE_NAME = 'tbl_promotion'
							AND COLUMN_NAME = 'TRADE_DISCOUNT_ID'
				),
				'SELECT ''TRADE_DISCOUNT_ID already exists''',
				'ALTER TABLE tbl_promotion ADD COLUMN TRADE_DISCOUNT_ID VARCHAR(255)'
		);

		PREPARE stmt FROM @sql;
		EXECUTE stmt;
		DEALLOCATE PREPARE stmt;

		-- TRADE_PRODUCT_ID
		SET @sql = IF(
				EXISTS (
						SELECT 1
						FROM INFORMATION_SCHEMA.COLUMNS
						WHERE TABLE_SCHEMA = DATABASE()
							AND TABLE_NAME = 'tbl_promotion'
							AND COLUMN_NAME = 'TRADE_PRODUCT_ID'
				),
				'SELECT ''TRADE_PRODUCT_ID already exists''',
				'ALTER TABLE tbl_promotion ADD COLUMN TRADE_PRODUCT_ID VARCHAR(255)'
		);

		PREPARE stmt FROM @sql;
		EXECUTE stmt;
		DEALLOCATE PREPARE stmt;
		
		-- TRADE_FREE_GOODS_ID
		SET @sql = IF(
				EXISTS (
						SELECT 1
						FROM INFORMATION_SCHEMA.COLUMNS
						WHERE TABLE_SCHEMA = DATABASE()
							AND TABLE_NAME = 'tbl_promotion'
							AND COLUMN_NAME = 'TRADE_FREE_GOODS_ID'
				),
				'SELECT ''TRADE_FREE_GOODS_ID already exists''',
				'ALTER TABLE tbl_promotion ADD COLUMN TRADE_FREE_GOODS_ID VARCHAR(255)'
		);

		PREPARE stmt FROM @sql;
		EXECUTE stmt;
		DEALLOCATE PREPARE stmt;

		-- CAMPAIGN
		SET @sql = IF(
				EXISTS (
						SELECT 1
						FROM INFORMATION_SCHEMA.COLUMNS
						WHERE TABLE_SCHEMA = DATABASE()
							AND TABLE_NAME = 'tbl_promotion'
							AND COLUMN_NAME = 'CAMPAIGN'
				),
				'SELECT ''CAMPAIGN already exists''',
				'ALTER TABLE tbl_promotion ADD COLUMN CAMPAIGN TEXT'
		);

		PREPARE stmt FROM @sql;
		EXECUTE stmt;
		DEALLOCATE PREPARE stmt;

    -- Guard: index บน EXTERNAL_ID
    IF NOT EXISTS (
        SELECT 1 FROM INFORMATION_SCHEMA.STATISTICS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME   = 'tbl_promotion'
          AND INDEX_NAME   = 'idx_external_id'
    ) THEN
        ALTER TABLE tbl_promotion
        ADD INDEX idx_external_id (EXTERNAL_ID(255));
    END IF;

    -- Guard: composite index บน EXTERNAL_ID + VARIANT_ID
    IF NOT EXISTS (
        SELECT 1 FROM INFORMATION_SCHEMA.STATISTICS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME   = 'tbl_promotion'
          AND INDEX_NAME   = 'idx_external_variant'
    ) THEN
        ALTER TABLE tbl_promotion
        ADD INDEX idx_external_variant (EXTERNAL_ID(255), VARIANT_ID(255));
    END IF;

    -- ============================================================
    -- Step 2: Build tmp_promotion (3 parts — PART2+3 ยุบรวม)
    -- ============================================================
    DROP TEMPORARY TABLE IF EXISTS tmp_promotion;

    CREATE TEMPORARY TABLE tmp_promotion AS

    -- ─────────────────────────────────────────────────────────────
    -- PART 1: DISCOUNT / REDUCTION
    -- JOIN pov ตั้งแต่นี้ แต่ละ variantId ได้ row ของตัวเอง
    -- ─────────────────────────────────────────────────────────────
		SELECT
				CONVERT(CAST(TM.TD_TRADE_DISCOUNT_ID AS CHAR) USING utf8mb4)
						COLLATE utf8mb4_general_ci AS EXTERNAL_ID,

				CONVERT(
						CONCAT(
								CAST(TM.TD_TRADE_DISCOUNT_ID AS CHAR),
								' ',
								TM.TM_CAMPAIGN,
								' ',
								TM.TM_TRADE_NAME,
								' discount ',
								CAST(
										REPLACE(
												IFNULL(TM.TD_TRADE_PRICE_EXC_VAT, TM.TD_DISCOUNT_EXC),
												'.',
												'_'
										) AS CHAR
								),
								' Baht for ',
								IFNULL(TM.TP_BRAND,''),
								' ',
								IFNULL(TM.TP_MODEL,''),
								' ',
								IFNULL(TM.TP_COLOR,''),
								' ',
								IFNULL(TM.TP_MAT_CODE,''),

								CASE
										WHEN IFNULL(TM.TP_MIN_PRICE_LENGTH,'') = ''
												 AND IFNULL(TM.TP_MAX_PRICE_LENGTH,'') = '' THEN ''
										WHEN IFNULL(TM.TP_MIN_PRICE_LENGTH,'') = ''
												THEN CONCAT(' ', TM.TP_MAX_PRICE_LENGTH)
										WHEN IFNULL(TM.TP_MAX_PRICE_LENGTH,'') = ''
												THEN CONCAT(' ', TM.TP_MIN_PRICE_LENGTH)
										ELSE CONCAT(
												' ',
												TM.TP_MIN_PRICE_LENGTH,
												'-',
												TM.TP_MAX_PRICE_LENGTH
										)
								END
						) USING utf8mb4
				) COLLATE utf8mb4_general_ci AS PROMOTION_NAME,

				CASE
						WHEN TM.TD_TRADE_PRICE_EXC_VAT IS NULL
								THEN 'Discount'
						ELSE 'Reduction'
				END AS PROMOTION_TYPE,

				NULL AS CODE,

				'Launched' AS LIFECYCLE_STATUS,

				NULL AS COUPON,

				'mutuallyExclusive' AS PROMOTION_CLASSIFICATION,

				'Cart' AS PROMOTION_APPLICATION_LEVEL,

				safe_to_datetime(TM.TD_START_DATE) AS VALID_FOR_START_DATETIME,

				safe_to_datetime(TM.TP_END_DATE) AS VALID_FOR_END_DATETIME,

				NULL AS ACTION_CARDINALITY,

				CONVERT(
						CAST(
								IFNULL(
										TM.TD_TRADE_PRICE_EXC_VAT,
										TM.TD_DISCOUNT_EXC
								) AS CHAR
						) USING utf8mb4
				) COLLATE utf8mb4_general_ci AS ACTION_VALUE,

				'Onetime' AS PRICE_TYPE,

				IFNULL(TM.TD_OPTIONS,1) AS PRIORITY,

				NULL AS ACTION_OBJECT_ID,

				NULL AS PRICE_ID,

				CASE
						WHEN TM.TD_DISCOUNT_BY = 'B'
								THEN 'Flat Discount'
						WHEN TM.TD_DISCOUNT_BY = 'P'
								THEN 'Percent Discount'
						WHEN TM.TD_TRADE_PRICE_EXC_VAT IS NOT NULL
								THEN 'Flat Price'
						ELSE NULL
				END AS ACTION_TYPE,

				CONVERT(TM.TP_MAT_CODE USING utf8mb4)
						COLLATE utf8mb4_general_ci AS SKU,

				NULL AS AWARD_PRODUCT_ID,

				CONVERT(POV.variantId USING utf8mb4)
						COLLATE utf8mb4_general_ci AS VARIANT_ID,

				CONVERT(POV.`Product Id` USING utf8mb4)
						COLLATE utf8mb4_general_ci AS PRODUCT_OFFER_ID,

				CONVERT(POV.`value` USING utf8mb4)
						COLLATE utf8mb4_general_ci AS CHARACTERISTIC_VALUE,

				NULL AS APPLICATION_DURATION,

				CONVERT(TM.TM_TRADE_NO USING utf8mb4)
						COLLATE utf8mb4_general_ci AS TRADE_NO,

				CONVERT(TM.TM_TRADE_NAME USING utf8mb4)
						COLLATE utf8mb4_general_ci AS TRADE_NAME,

				CONVERT(
						CAST(TM.TD_TRADE_DISCOUNT_ID AS CHAR)
						USING utf8mb4
				) COLLATE utf8mb4_general_ci AS TRADE_DISCOUNT_ID,

				CONVERT(
						CAST(TM.TP_TRADE_PRODUCT_ID AS CHAR)
						USING utf8mb4
				) COLLATE utf8mb4_general_ci AS TRADE_PRODUCT_ID,

				NULL AS TRADE_FREE_GOODS_ID,

				CONVERT(TM.TM_CAMPAIGN USING utf8mb4)
						COLLATE utf8mb4_general_ci AS CAMPAIGN,

				'PART1_DISCOUNT_REDUCTION' AS PROMOTION_SOURCE

		FROM tbl_product_mst TM

		LEFT JOIN tbl_product_offering_variant POV
				ON POV.SKU = TM.TP_MAT_CODE

		WHERE TM.TD_TRADE_DISCOUNT_ID IS NOT NULL
			AND TM.TM_SALE_TYPE = 'SALE'

			AND NOW() BETWEEN
						safe_to_datetime(TM.TP_START_DATE)
				AND safe_to_datetime(TM.TP_END_DATE)

			AND NOW() BETWEEN
						safe_to_datetime(TM.TD_START_DATE)
				AND safe_to_datetime(TM.TP_END_DATE)

    UNION ALL

    -- ─────────────────────────────────────────────────────────────
    -- PART 2+3: FREE GOODS (ยุบรวม ALL และ CHOICE)
    -- PROMOTION_SOURCE = 'PART2_FG_ALL' / 'PART3_FG_CHOICE' / 'PART2_FG_ALL,PART3_FG_CHOICE'
    -- ─────────────────────────────────────────────────────────────
		SELECT
				CONVERT(CAST(TFG.TRADE_FREE_GOODS_ID AS CHAR) USING utf8mb4)
						COLLATE utf8mb4_general_ci 												AS EXTERNAL_ID,
				CONVERT(
						CONCAT(
								CAST(TFG.TRADE_FREE_GOODS_ID AS CHAR),
								' ',
								TM.TM_CAMPAIGN,
								' ',
								TM.TM_TRADE_NAME,
								' reward ',
								TFG.MAT_CODE,
								' for ',
								IFNULL(TM.TP_BRAND,''),
								' ',
								IFNULL(TM.TP_MODEL,''),
								' ',
								IFNULL(TM.TP_COLOR,''),
								' ',
								IFNULL(TM.TP_MAT_CODE,''),
								CASE
										WHEN fg_grp.fg_type NOT LIKE '%PART2_FG_ALL%' THEN ''
										WHEN IFNULL(TM.TP_MIN_PRICE_LENGTH,'') = ''
												 AND IFNULL(TM.TP_MAX_PRICE_LENGTH,'') = '' THEN ''
										WHEN IFNULL(TM.TP_MIN_PRICE_LENGTH,'') = ''
												THEN CONCAT(' ', TM.TP_MAX_PRICE_LENGTH)
										WHEN IFNULL(TM.TP_MAX_PRICE_LENGTH,'') = ''
												THEN CONCAT(' ', TM.TP_MIN_PRICE_LENGTH)
										ELSE CONCAT(
												' ',
												TM.TP_MIN_PRICE_LENGTH,
												'-',
												TM.TP_MAX_PRICE_LENGTH
										)
								END
						) USING utf8mb4
				) COLLATE utf8mb4_general_ci 													AS PROMOTION_NAME,
				'Award' 																							AS PROMOTION_TYPE,
				NULL 																									AS CODE,
				'Launched' 																						AS LIFECYCLE_STATUS,
				NULL 																									AS COUPON,
				'stackable' 																					AS PROMOTION_CLASSIFICATION,
				'Cart' 																								AS PROMOTION_APPLICATION_LEVEL,
				safe_to_datetime(TFG.START_DATE) 											AS VALID_FOR_START_DATETIME,
				safe_to_datetime(TFG.END_DATE) 												AS VALID_FOR_END_DATETIME,
				1 AS ACTION_CARDINALITY,
				CONVERT(CAST(TFG.QTY AS CHAR) USING utf8mb4)
						COLLATE utf8mb4_general_ci 												AS ACTION_VALUE,
				NULL 																									AS PRICE_TYPE,
				NULL 																									AS PRIORITY,
				NULL 																									AS ACTION_OBJECT_ID,
				NULL 																									AS PRICE_ID,
				'Add Product' 																				AS ACTION_TYPE,
				CONVERT(TFG.MAT_CODE USING utf8mb4)
						COLLATE utf8mb4_general_ci 												AS SKU,
				CONVERT(POV.variantId USING utf8mb4)
						COLLATE utf8mb4_general_ci 												AS AWARD_PRODUCT_ID,
				CONVERT(POV.variantId USING utf8mb4)
						COLLATE utf8mb4_general_ci 												AS VARIANT_ID,
				CONVERT(POV.`Product Id` USING utf8mb4)
						COLLATE utf8mb4_general_ci 												AS PRODUCT_OFFER_ID,
				CONVERT(POV.`value` USING utf8mb4)
						COLLATE utf8mb4_general_ci 												AS CHARACTERISTIC_VALUE,
				NULL AS APPLICATION_DURATION,
				CONVERT(TM.TM_TRADE_NO USING utf8mb4)
						COLLATE utf8mb4_general_ci 												AS TRADE_NO,
				CONVERT(TM.TM_TRADE_NAME USING utf8mb4)
						COLLATE utf8mb4_general_ci 												AS TRADE_NAME,
				NULL AS TRADE_DISCOUNT_ID,
				CONVERT(CAST(TM.TP_TRADE_PRODUCT_ID AS CHAR) USING utf8mb4)
						COLLATE utf8mb4_general_ci 												AS TRADE_PRODUCT_ID,
				TFG.TRADE_FREE_GOODS_ID 															AS TRADE_FREE_GOODS_ID,
				CONVERT(TM.TM_CAMPAIGN USING utf8mb4)
						COLLATE utf8mb4_general_ci 												AS CAMPAIGN,
				fg_grp.fg_type 																				AS PROMOTION_SOURCE
		FROM tbl_product_mst TM
		INNER JOIN TR_FREE_GOODS TFG ON TFG.TRADE_PRODUCT_ID = TM.TP_TRADE_PRODUCT_ID
		LEFT JOIN tbl_product_offering_variant POV ON POV.SKU = TFG.MAT_CODE
		INNER JOIN (
				SELECT
						grp.TRADE_PRODUCT_ID,
						GROUP_CONCAT(
								DISTINCT grp.type_label
								ORDER BY grp.type_label
								SEPARATOR ','
						) AS fg_type
				FROM (
						SELECT
								TM2.TP_TRADE_PRODUCT_ID AS TRADE_PRODUCT_ID,
								CASE
										WHEN TM2.TP_MAX_RECEIVE_FREE_GOODS =
												 COUNT(DISTINCT TFG2.TRADE_FREE_GOODS_ID)
										THEN 'PART2_FG_ALL'
										ELSE 'PART3_FG_CHOICE'
								END AS type_label
						FROM (
								SELECT
										TP_TRADE_PRODUCT_ID,
										MAX(
												CAST(
														COALESCE(
																NULLIF(TP_MAX_RECEIVE_FREE_GOODS,''),
																'0'
														) AS UNSIGNED
												)
										) AS TP_MAX_RECEIVE_FREE_GOODS
								FROM tbl_product_mst
								GROUP BY TP_TRADE_PRODUCT_ID
						) TM2
						INNER JOIN TR_FREE_GOODS TFG2 ON TFG2.TRADE_PRODUCT_ID = TM2.TP_TRADE_PRODUCT_ID
						WHERE NOW() BETWEEN safe_to_datetime(TFG2.START_DATE) AND safe_to_datetime(TFG2.END_DATE)
						GROUP BY TM2.TP_TRADE_PRODUCT_ID, TM2.TP_MAX_RECEIVE_FREE_GOODS
						HAVING TM2.TP_MAX_RECEIVE_FREE_GOODS <= COUNT(DISTINCT TFG2.TRADE_FREE_GOODS_ID)
				) grp
				GROUP BY grp.TRADE_PRODUCT_ID
		) fg_grp
				ON fg_grp.TRADE_PRODUCT_ID = TM.TP_TRADE_PRODUCT_ID
		WHERE NOW() BETWEEN safe_to_datetime(TM.TP_START_DATE) AND safe_to_datetime(TM.TP_END_DATE)
				AND NOW() BETWEEN safe_to_datetime(TFG.START_DATE) AND safe_to_datetime(TFG.END_DATE)

				AND TM.TM_SALE_TYPE = 'SALE'

    UNION ALL

    -- ─────────────────────────────────────────────────────────────
    -- PART 4: FOC (Free of Charge)
    -- ─────────────────────────────────────────────────────────────
		SELECT
				CONVERT(CAST(TM.TP_TRADE_PRODUCT_ID AS CHAR) USING utf8mb4)
						COLLATE utf8mb4_general_ci AS EXTERNAL_ID,

				CONVERT(CONCAT(
						CAST(TM.TP_TRADE_PRODUCT_ID AS CHAR),
						' ',
						TM.TM_CAMPAIGN,
						' ',
						TM.TM_TRADE_NAME,
						' for ',
						IFNULL(TM.TP_BRAND,''),
						' ',
						IFNULL(TM.TP_MODEL,''),
						' ',
						IFNULL(TM.TP_COLOR,''),
						' ',
						IFNULL(TM.TP_MAT_CODE,'')
				) USING utf8mb4)
						COLLATE utf8mb4_general_ci AS PROMOTION_NAME,

				CASE
						WHEN TM.TP_FOC_CODE = 3 THEN 'Reduction'
						WHEN TM.TD_TRADE_PRICE_EXC_VAT IS NULL THEN 'Discount'
						ELSE 'Reduction'
				END AS PROMOTION_TYPE,

				NULL AS CODE,
				'Launched' AS LIFECYCLE_STATUS,
				NULL AS COUPON,
				'mutuallyExclusive' AS PROMOTION_CLASSIFICATION,
				'Cart' AS PROMOTION_APPLICATION_LEVEL,

				safe_to_datetime(TM.TP_START_DATE) AS VALID_FOR_START_DATETIME,
				safe_to_datetime(TM.TP_END_DATE) AS VALID_FOR_END_DATETIME,

				NULL AS ACTION_CARDINALITY,

				CONVERT(CAST(TM.RM_VAT_AMT AS CHAR) USING utf8mb4)
						COLLATE utf8mb4_general_ci AS ACTION_VALUE,

				CASE
						WHEN TM.TP_FOC_CODE = 3 THEN 'AISPayVAT'
						ELSE 'Onetime'
				END AS PRICE_TYPE,

				IFNULL(TM.TD_OPTIONS, 1) AS PRIORITY,

				NULL AS ACTION_OBJECT_ID,
				NULL AS PRICE_ID,

				CASE
						WHEN TM.TD_DISCOUNT_BY = 'B' THEN 'Flat Discount'
						WHEN TM.TD_DISCOUNT_BY = 'P' THEN 'Percent Discount'
						WHEN TM.TP_FOC_CODE = 3 THEN 'Flat Price'
						ELSE NULL
				END AS ACTION_TYPE,

				CONVERT(TM.TP_MAT_CODE USING utf8mb4)
						COLLATE utf8mb4_general_ci AS SKU,

				NULL AS AWARD_PRODUCT_ID,

				CONVERT(POV.variantId USING utf8mb4)
						COLLATE utf8mb4_general_ci AS VARIANT_ID,

				CONVERT(POV.`Product Id` USING utf8mb4)
						COLLATE utf8mb4_general_ci AS PRODUCT_OFFER_ID,

				CONVERT(POV.`value` USING utf8mb4)
						COLLATE utf8mb4_general_ci AS CHARACTERISTIC_VALUE,

				NULL AS APPLICATION_DURATION,

				CONVERT(TM.TM_TRADE_NO USING utf8mb4)
						COLLATE utf8mb4_general_ci AS TRADE_NO,

				CONVERT(TM.TM_TRADE_NAME USING utf8mb4)
						COLLATE utf8mb4_general_ci AS TRADE_NAME,

				CONVERT(CAST(TM.TD_TRADE_DISCOUNT_ID AS CHAR) USING utf8mb4)
						COLLATE utf8mb4_general_ci AS TRADE_DISCOUNT_ID,

				CONVERT(CAST(TM.TP_TRADE_PRODUCT_ID AS CHAR) USING utf8mb4)
						COLLATE utf8mb4_general_ci AS TRADE_PRODUCT_ID,

				NULL AS TRADE_FREE_GOODS_ID,

				CONVERT(TM.TM_CAMPAIGN USING utf8mb4)
						COLLATE utf8mb4_general_ci AS CAMPAIGN,

				'PART4_FOC' AS PROMOTION_SOURCE

		FROM tbl_product_mst TM

		LEFT JOIN tbl_product_offering_variant POV
				ON POV.SKU = TM.TP_MAT_CODE

		WHERE NOW() BETWEEN
						safe_to_datetime(TM.TP_START_DATE)
				AND safe_to_datetime(TM.TP_END_DATE)
				AND TM.TP_FOC_START_DATE IS NOT NULL
				AND TM.TM_SALE_TYPE = 'SALE'

	UNION ALL

		-- ─────────────────────────────────────────────────────────────
		-- PART 5: NO PROMOTION (product ที่ตกทุก PART)
		-- ─────────────────────────────────────────────────────────────
		SELECT
				CONVERT(CAST(TM.TP_TRADE_PRODUCT_ID AS CHAR) USING utf8mb4)
						COLLATE utf8mb4_general_ci AS EXTERNAL_ID,

				CONVERT(CONCAT(
						CAST(TM.TP_TRADE_PRODUCT_ID AS CHAR),
						' ',
						TM.TM_CAMPAIGN,
						' ',
						TM.TM_TRADE_NAME,
						' for ',
						IFNULL(TM.TP_BRAND,''),
						' ',
						IFNULL(TM.TP_MODEL,''),
						' ',
						IFNULL(TM.TP_COLOR,''),
						' ',
						IFNULL(TM.TP_MAT_CODE,'')
				) USING utf8mb4)
						COLLATE utf8mb4_general_ci AS PROMOTION_NAME,

				'Discount'           AS PROMOTION_TYPE,
				NULL                 AS CODE,
				'Launched'           AS LIFECYCLE_STATUS,
				NULL                 AS COUPON,
				'mutuallyExclusive'  AS PROMOTION_CLASSIFICATION,
				'Cart'               AS PROMOTION_APPLICATION_LEVEL,

				safe_to_datetime(TM.TP_START_DATE) AS VALID_FOR_START_DATETIME,
				safe_to_datetime(TM.TP_END_DATE)   AS VALID_FOR_END_DATETIME,

				NULL                 AS ACTION_CARDINALITY,
				'0'                  AS ACTION_VALUE,
				'Onetime'            AS PRICE_TYPE,
				1                    AS PRIORITY,
				NULL                 AS ACTION_OBJECT_ID,
				NULL                 AS PRICE_ID,
				'Flat Discount'      AS ACTION_TYPE,

				CONVERT(TM.TP_MAT_CODE USING utf8mb4)
						COLLATE utf8mb4_general_ci AS SKU,

				NULL                 AS AWARD_PRODUCT_ID,

				CONVERT(POV.variantId USING utf8mb4)
						COLLATE utf8mb4_general_ci AS VARIANT_ID,

				CONVERT(POV.`Product Id` USING utf8mb4)
						COLLATE utf8mb4_general_ci AS PRODUCT_OFFER_ID,

				CONVERT(POV.`value` USING utf8mb4)
						COLLATE utf8mb4_general_ci AS CHARACTERISTIC_VALUE,

				NULL                 AS APPLICATION_DURATION,

				CONVERT(TM.TM_TRADE_NO USING utf8mb4)
						COLLATE utf8mb4_general_ci AS TRADE_NO,

				CONVERT(TM.TM_TRADE_NAME USING utf8mb4)
						COLLATE utf8mb4_general_ci AS TRADE_NAME,

				NULL                 AS TRADE_DISCOUNT_ID,

				CONVERT(CAST(TM.TP_TRADE_PRODUCT_ID AS CHAR) USING utf8mb4)
						COLLATE utf8mb4_general_ci AS TRADE_PRODUCT_ID,

				NULL                 AS TRADE_FREE_GOODS_ID,

				CONVERT(TM.TM_CAMPAIGN USING utf8mb4)
						COLLATE utf8mb4_general_ci AS CAMPAIGN,

				'PART5_NO_PROMOTION' AS PROMOTION_SOURCE

		FROM tbl_product_mst TM

		LEFT JOIN tbl_product_offering_variant POV
				ON POV.SKU = TM.TP_MAT_CODE

		WHERE TM.TM_SALE_TYPE = 'SALE'
			AND NOW() BETWEEN safe_to_datetime(TM.TP_START_DATE)
										AND safe_to_datetime(TM.TP_END_DATE)

			-- ตกจาก PART 1
			AND TM.TD_TRADE_DISCOUNT_ID IS NULL

			-- ตกจาก PART 4
			AND TM.TP_FOC_START_DATE IS NULL

			-- ตกจาก PART 2&3
			AND NOT EXISTS (
					SELECT 1 FROM TR_FREE_GOODS TFG
					WHERE TFG.TRADE_PRODUCT_ID = TM.TP_TRADE_PRODUCT_ID
			);


    -- ============================================================
    -- FIX: ล้าง datetime ที่ invalid หลัง UNION ALL ทั้งหมด
    -- ============================================================
    UPDATE tmp_promotion
    SET
        VALID_FOR_START_DATETIME = CASE
            WHEN CAST(VALID_FOR_START_DATETIME AS CHAR) = '00:00:00.000' THEN NULL
            ELSE VALID_FOR_START_DATETIME
        END,
        VALID_FOR_END_DATETIME = CASE
            WHEN CAST(VALID_FOR_END_DATETIME AS CHAR) = '00:00:00.000' THEN NULL
            ELSE VALID_FOR_END_DATETIME
        END;

    -- Guard: ไม่มีข้อมูล
    IF NOT EXISTS (SELECT 1 FROM tmp_promotion LIMIT 1) THEN
        SELECT 'No active promotions found.' AS message;
        DROP TEMPORARY TABLE IF EXISTS tmp_promotion;
        LEAVE proc_label;
    END IF;

    -- ============================================================
    -- Step 3: นับ EXTERNAL_ID + VARIANT_ID ใหม่ (composite key)
    -- ============================================================
		SELECT COUNT(*) INTO v_new_count
		FROM (
				SELECT DISTINCT EXTERNAL_ID, VARIANT_ID
				FROM tmp_promotion
		) tp
		WHERE NOT EXISTS (
				SELECT 1 FROM tbl_promotion pr
				WHERE pr.EXTERNAL_ID = CAST(tp.EXTERNAL_ID AS CHAR) COLLATE utf8mb4_general_ci
					AND pr.VARIANT_ID  = CAST(IFNULL(tp.VARIANT_ID,'') AS CHAR) COLLATE utf8mb4_general_ci
		);

    SELECT IFNULL(MAX(rn), -1) INTO v_rn_offset FROM tbl_promotion;

    START TRANSACTION;

    -- ============================================================
    -- Step 4: Reserve sequence batch (เฉพาะถ้ามี record ใหม่)
    -- ============================================================
    IF v_new_count > 0 THEN
        CALL get_next_sequence_batch('promotion', NULL, v_new_count,
            v_pr_start, @v_pr_end, @v_pr_prefix, @v_pr_suffix, @v_pr_pad);

        SET v_pr_prefix = IFNULL(@v_pr_prefix, '');
        SET v_pr_suffix = IFNULL(@v_pr_suffix, '');
        SET v_pr_pad    = IFNULL(@v_pr_pad, 6);

        CALL get_next_sequence_batch('promotion_action', NULL, v_new_count,
            v_pa_start, @v_pa_end, @v_pa_prefix, @v_pa_suffix, @v_pa_pad);

        SET v_pa_prefix = IFNULL(@v_pa_prefix, '');
        SET v_pa_suffix = IFNULL(@v_pa_suffix, '');
        SET v_pa_pad    = IFNULL(@v_pa_pad, 6);
    END IF;

    SET @v_rn     = v_rn_offset;
    SET @v_seq    = v_pr_start - 1;
    SET @v_seq_pa = v_pa_start - 1;

    -- ============================================================
    -- Step 5a: INSERT record ใหม่
    -- check ด้วย composite key: EXTERNAL_ID + VARIANT_ID
    -- ============================================================
    IF v_new_count > 0 THEN
        INSERT INTO tbl_promotion (
					PROMOTION_ID,
					PROMOTION_ACTION_ID,
					EXTERNAL_ID,
					PROMOTION_NAME,
					PROMOTION_TYPE,
					CODE,
					LIFECYCLE_STATUS,
					COUPON,
					PROMOTION_CLASSIFICATION,
					PROMOTION_APPLICATION_LEVEL,
					VALID_FOR_START_DATETIME,
					VALID_FOR_END_DATETIME,
					ACTION_CARDINALITY,
					ACTION_VALUE,
					PRICE_TYPE,
					PRIORITY,
					ACTION_OBJECT_ID,
					PRICE_ID,
					ACTION_TYPE,
					SKU,
					AWARD_PRODUCT_ID,
					VARIANT_ID,
					PRODUCT_OFFER_ID,
					CHARACTERISTIC_VALUE,
					APPLICATION_DURATION,
					TRADE_NO,
					TRADE_NAME,
					TRADE_DISCOUNT_ID,
					TRADE_PRODUCT_ID,
					TRADE_FREE_GOODS_ID,
					CAMPAIGN,
					PROMOTION_SOURCE,
					rn,
					batch_id_insert,
					created_by,
					created_at
			)

			SELECT
REGEXP_REPLACE(
                        clean_id(CONCAT(
                            v_pr_prefix,
                            clean_id(t.PROMOTION_NAME),
                            v_pr_suffix,
                            LPAD(@v_seq := @v_seq + 1, v_pr_pad, '0')
                        )),
                        '_pm_mg([0-9]+)',
                        '-pm_mg\\1'
                    ) AS PROMOTION_ID,

					clean_id(CONCAT(
							v_pa_prefix,
							LPAD(@v_seq_pa := @v_seq_pa + 1, v_pa_pad, '0'),
							v_pa_suffix
					)) AS PROMOTION_ACTION_ID,

					CAST(t.EXTERNAL_ID AS CHAR),
					t.PROMOTION_NAME,
					t.PROMOTION_TYPE,
					t.`CODE`,
					t.LIFECYCLE_STATUS,
					t.COUPON,
					t.PROMOTION_CLASSIFICATION,
					t.PROMOTION_APPLICATION_LEVEL,
					t.VALID_FOR_START_DATETIME,
					t.VALID_FOR_END_DATETIME,
					t.ACTION_CARDINALITY,
					t.ACTION_VALUE,
					t.PRICE_TYPE,
					t.PRIORITY,
					t.ACTION_OBJECT_ID,
					t.PRICE_ID,
					t.ACTION_TYPE,
					t.SKU,
					t.AWARD_PRODUCT_ID,
					t.VARIANT_ID,
					t.PRODUCT_OFFER_ID,
					t.CHARACTERISTIC_VALUE,
					t.APPLICATION_DURATION,
					t.TRADE_NO,
					t.TRADE_NAME,
					t.TRADE_DISCOUNT_ID,
					t.TRADE_PRODUCT_ID,
					t.TRADE_FREE_GOODS_ID,
					t.CAMPAIGN,
					t.PROMOTION_SOURCE,

					@v_rn := @v_rn + 1 AS rn,

					batch_id,
					v_actor,
					NOW(3)

			FROM (
					SELECT DISTINCT tp.*
					FROM tmp_promotion tp
					WHERE NOT EXISTS (
							SELECT 1
							FROM tbl_promotion pr
							WHERE pr.EXTERNAL_ID COLLATE utf8mb4_general_ci
									= CAST(tp.EXTERNAL_ID AS CHAR) COLLATE utf8mb4_general_ci
								AND pr.VARIANT_ID COLLATE utf8mb4_general_ci
									= CAST(IFNULL(tp.VARIANT_ID, '') AS CHAR) COLLATE utf8mb4_general_ci
					)
			) t
			ORDER BY t.PROMOTION_NAME;
    END IF;

    -- ============================================================
    -- Step 5b: UPDATE record เดิม
    -- match ด้วย composite key: EXTERNAL_ID + VARIANT_ID
    -- ============================================================
		UPDATE tbl_promotion pr
		JOIN (
				SELECT DISTINCT * 
				FROM tmp_promotion
		) t
				ON pr.EXTERNAL_ID COLLATE utf8mb4_general_ci
						= CAST(t.EXTERNAL_ID AS CHAR) COLLATE utf8mb4_general_ci
				AND pr.VARIANT_ID COLLATE utf8mb4_general_ci
						= CAST(IFNULL(t.VARIANT_ID,'') AS CHAR) COLLATE utf8mb4_general_ci
		SET
				pr.PROMOTION_NAME               = t.PROMOTION_NAME,
				pr.PROMOTION_TYPE               = t.PROMOTION_TYPE,
				pr.LIFECYCLE_STATUS             = t.LIFECYCLE_STATUS,
				pr.PROMOTION_CLASSIFICATION     = t.PROMOTION_CLASSIFICATION,
				pr.PROMOTION_APPLICATION_LEVEL  = t.PROMOTION_APPLICATION_LEVEL,
				pr.VALID_FOR_START_DATETIME     = t.VALID_FOR_START_DATETIME,
				pr.VALID_FOR_END_DATETIME       = t.VALID_FOR_END_DATETIME,
				pr.ACTION_CARDINALITY           = t.ACTION_CARDINALITY,
				pr.ACTION_VALUE                 = t.ACTION_VALUE,
				pr.PRICE_TYPE                   = t.PRICE_TYPE,
				pr.PRIORITY                     = t.PRIORITY,
				pr.ACTION_TYPE                  = t.ACTION_TYPE,
				pr.SKU                          = t.SKU,
				pr.AWARD_PRODUCT_ID             = t.AWARD_PRODUCT_ID,
				pr.VARIANT_ID                   = t.VARIANT_ID,
				pr.PRODUCT_OFFER_ID             = t.PRODUCT_OFFER_ID,
				pr.CHARACTERISTIC_VALUE         = t.CHARACTERISTIC_VALUE,

				pr.TRADE_NO                     = t.TRADE_NO,
				pr.TRADE_NAME                   = t.TRADE_NAME,
				pr.TRADE_DISCOUNT_ID            = t.TRADE_DISCOUNT_ID,
				pr.TRADE_PRODUCT_ID             = t.TRADE_PRODUCT_ID,
				pr.TRADE_FREE_GOODS_ID					= t.TRADE_FREE_GOODS_ID,
				pr.CAMPAIGN                     = t.CAMPAIGN,

				pr.PROMOTION_SOURCE             = t.PROMOTION_SOURCE,
				pr.batch_id_update              = batch_id,
				pr.updated_by                   = v_actor,
				pr.updated_at                   = NOW(3)

		WHERE
				p_force_rerun = 1
				OR pr.batch_id_insert <> batch_id
				OR pr.batch_id_insert IS NULL;
				
		-- ============================================================
    -- Step 5c: Soft delete record ที่หายออกจาก source แล้ว  
    -- ต้องอยู่ก่อน COMMIT และก่อน DROP TEMPORARY TABLE
    -- ============================================================
    UPDATE tbl_promotion pr
    SET
        pr.LIFECYCLE_STATUS = 'Retired',
        pr.updated_by       = v_actor,
        pr.updated_at       = NOW(3),
        pr.batch_id_update  = batch_id
    WHERE NOT EXISTS (
        SELECT 1 FROM tmp_promotion tp
        WHERE CAST(tp.EXTERNAL_ID AS CHAR) COLLATE utf8mb4_general_ci
            = pr.EXTERNAL_ID COLLATE utf8mb4_general_ci
          AND CAST(IFNULL(tp.VARIANT_ID, '') AS CHAR) COLLATE utf8mb4_general_ci
            = pr.VARIANT_ID COLLATE utf8mb4_general_ci
    )
    AND pr.LIFECYCLE_STATUS <> 'Retired';

    COMMIT;

    DROP TEMPORARY TABLE IF EXISTS tmp_promotion;

    -- ============================================================
    -- Step 6: Create Views
    -- ============================================================
    DROP VIEW IF EXISTS v_promotion;
    CREATE VIEW v_promotion AS
    SELECT
        CAST(PROMOTION_ID AS CHAR)                AS `promotion_id`,
        CAST(EXTERNAL_ID AS CHAR)                 AS `externalID`,
        CAST(PROMOTION_NAME AS CHAR)              AS `name`,
        CAST(PROMOTION_TYPE AS CHAR)              AS `Promotion Type`,
        CAST(`CODE` AS CHAR)                      AS `code`,
        CAST(LIFECYCLE_STATUS AS CHAR)            AS `lifecycleStatus`,
        CAST(COUPON AS CHAR)                      AS `coupon`,
        CAST(PROMOTION_CLASSIFICATION AS CHAR)    AS `promotionClassification`,
        CAST(PROMOTION_APPLICATION_LEVEL AS CHAR) AS `promoApplicationLevel`,
        CAST(DATE_FORMAT(VALID_FOR_START_DATETIME, '%Y-%m-%dT%H:%i:%s.000Z') AS CHAR) AS `Validity Start Date`,
        CAST(DATE_FORMAT(VALID_FOR_END_DATETIME,   '%Y-%m-%dT%H:%i:%s.000Z') AS CHAR) AS `Validity End Date`
    FROM tbl_promotion
    ORDER BY rn;

    DROP VIEW IF EXISTS v_promotion_action;
    CREATE VIEW v_promotion_action AS
    SELECT
        CAST(PROMOTION_ID AS CHAR)         AS `Promotion ID`,
        CAST(PROMOTION_ACTION_ID AS CHAR)  AS `promotion Action id`,
        CAST(`CODE` AS CHAR)               AS `code`,
        CAST(ACTION_CARDINALITY AS CHAR)   AS `actionCardinality`,
        CAST(ACTION_VALUE AS CHAR)         AS `actionValue`,
        CAST(PRICE_TYPE AS CHAR)           AS `priceType`,
        CAST(PRIORITY AS CHAR)             AS `priority`,
        CAST(ACTION_OBJECT_ID AS CHAR)     AS `actionObjectId`,
        CAST(PRICE_ID AS CHAR)             AS `PriceId`,
        CAST(ACTION_TYPE AS CHAR)          AS `actionType`,
        CAST(AWARD_PRODUCT_ID AS CHAR)     AS `AwardProductId`,
        CAST(VARIANT_ID AS CHAR)           AS `Variant Id`,
--         CAST(PRODUCT_OFFER_ID AS CHAR)     AS `ProductOffer ID`,
--         CAST(CHARACTERISTIC_VALUE AS CHAR) AS `characteristicValue`,
        CAST(APPLICATION_DURATION AS CHAR) AS `applicationDuration`
    FROM tbl_promotion
    ORDER BY rn;

    DROP VIEW IF EXISTS v_promotion_link_campaign_master;
    CREATE VIEW v_promotion_link_campaign_master AS
    SELECT
        'Master Extension'           AS `BM Entity Type`,
        CAST(PROMOTION_ID AS CHAR)   AS `Promotion ID`,
        CONCAT(
            CAST(CAMPAIGN AS CHAR), ' ', CAST(TRADE_NAME AS CHAR)
        )                            AS `Name`,
        'campaignMaster'             AS `Extension Type`,
        'Residence'                  AS `marketSegment`,
        'All'                        AS `Channels`,
        NULL                         AS `Languages`,
        CAST(CAMPAIGN AS CHAR)       AS `campaignGroupName`,
        CAST(TRADE_NAME AS CHAR)     AS `campaignName`
    FROM tbl_promotion
    ORDER BY rn;
		
		DROP VIEW IF EXISTS v_promotion_meta_ext_value_extra_document;
		CREATE VIEW v_promotion_meta_ext_value_extra_document AS
		SELECT DISTINCT
			'Promotion Extension' 				AS `BM Entity Type`,
			pmt.PROMOTION_ID 							AS `Promotion ID`,
			'Extra Document' 							AS `Name`,
			'extraDocument' 							AS `Extension Type`,
			'Residence'		 								AS `marketSegment`,
			'All' 												AS `Channels`,
			'' 														AS `Languages`,
			tc.CRITERIA_VALUE 						AS `documentName`
		FROM TR_PRODUCT tp
			LEFT JOIN tr_mst tm ON tm.TRADE_NO = tp.TRADE_NO
			LEFT JOIN TR_CRITERIA tc ON tc.TRADE_NO = tp.TRADE_NO
			INNER JOIN tbl_promotion pmt ON pmt.TRADE_NO = tp.TRADE_NO
			AND pmt.TRADE_PRODUCT_ID = tp.TRADE_PRODUCT_ID
		WHERE
			tc.CRITERIA_TYPE = 'extraDoc';
		
		DROP VIEW IF EXISTS v_promotion_meta_ext_value_allowed_airtime_installment;
		CREATE VIEW v_promotion_meta_ext_value_allowed_airtime_installment AS	
		SELECT DISTINCT
				CONVERT('Promotion Extension' USING utf8mb4) COLLATE utf8mb4_general_ci 				AS `BM Entity Type`,
				pmt.PROMOTION_ID 																																AS `Promotion ID`,
				CONVERT('Allowed Airtime Installment' USING utf8mb4) COLLATE utf8mb4_general_ci AS `Name`,
				CONVERT('allowedAirtimeInstallment' USING utf8mb4) COLLATE utf8mb4_general_ci 	AS `Extension Type`,
				CONVERT('Residence' USING utf8mb4) COLLATE utf8mb4_general_ci 									AS `marketSegment`,
				CONVERT('All' USING utf8mb4) COLLATE utf8mb4_general_ci 												AS `Channels`,
				CONVERT('' USING utf8mb4) COLLATE utf8mb4_general_ci 														AS `Languages`,
				CONVERT(
						CASE
								WHEN tp.ASP_FLG = 'Y' THEN 'TRUE'
								ELSE 'FALSE'
						END
				USING utf8mb4) COLLATE utf8mb4_general_ci 																			AS `isAllowedAirtimeInstallment`
		FROM TR_PRODUCT tp
		INNER JOIN tbl_promotion pmt
				ON pmt.TRADE_PRODUCT_ID = tp.TRADE_PRODUCT_ID
		WHERE CURRENT_DATE BETWEEN tp.START_DATE AND tp.END_DATE;

		DROP VIEW IF EXISTS v_promotion_meta_ext_value_free_goods_detail;
		CREATE VIEW v_promotion_meta_ext_value_free_goods_detail AS	
		SELECT
				`BM Entity Type`, `Promotion ID`, `Name`, `Extension Type`,
				`marketSegment`, `Channels`, `Languages`, `isWaitingList`
		FROM (
				SELECT DISTINCT
						CAST('Promotion Extension'                                                      AS CHAR)  AS `BM Entity Type`,
						CAST(promo.promotion_id                                                         AS CHAR)  AS `Promotion ID`,
						CAST('Free Goods Detail'                                                        AS CHAR)  AS `Name`,
						CAST('freeGoodsDetail'                                                          AS CHAR)  AS `Extension Type`,
						CAST('Residence'                                                                AS CHAR)  AS `marketSegment`,
						CAST('All'                                                                      AS CHAR)  AS `Channels`,
						CAST(NULL                                                                       AS CHAR)  AS `Languages`,
						CAST(CASE WHEN ctm.free_goods_waiting_flag = 'Y' THEN 'TRUE' ELSE 'FALSE' END  AS CHAR)  AS `isWaitingList`,
						promo.rn
				FROM (
						SELECT DISTINCT trade_no, trade_product_id
						FROM TR_FREE_GOODS
				) ctfg
				STRAIGHT_JOIN TR_PRODUCT ctp    ON ctp.TRADE_NO         = ctfg.trade_no
																				AND ctp.TRADE_PRODUCT_ID = ctfg.trade_product_id
				STRAIGHT_JOIN TR_MST ctm        ON ctm.trade_no          = ctfg.trade_no
				STRAIGHT_JOIN (
						SELECT TRADE_NO, promotion_id, MIN(rn) AS rn
						FROM tbl_promotion
						GROUP BY TRADE_NO, promotion_id
				) promo                         ON promo.TRADE_NO         = ctfg.trade_no
		) t
		ORDER BY rn ASC;
		
		DROP VIEW IF EXISTS v_promotion_meta_ext_value_specific_location;
		CREATE VIEW v_promotion_meta_ext_value_specific_location AS	
		SELECT
				CAST('Promotion Extension'	AS CHAR)  AS `BM Entity Type`,
				CAST(promo.promotion_id			AS CHAR)  AS `Promotion ID`,
				CAST('Specific Location'    AS CHAR)  AS `Name`,
				CAST('specificLocation'     AS CHAR)  AS `Extension Type`,
				CAST(NULL                   AS CHAR)  AS `marketSegment`,
				CAST(NULL                   AS CHAR)  AS `Channels`,
				CAST(NULL                   AS CHAR)  AS `Languages`,
				CAST('Include'              AS CHAR)  AS `filterType`,
				CAST(CONCAT(base.LOCATION_CODE, '|', clm.LOCATION_NAME) AS CHAR)  	AS `locationCode`
		FROM (
				SELECT DISTINCT TRADE_NO, LOCATION_CODE
				FROM TR_CN
				WHERE LOCATION_CODE IS NOT NULL
		) base
		STRAIGHT_JOIN (
				SELECT DISTINCT TRADE_NO, promotion_id, MIN(rn) AS rn
				FROM tbl_promotion
				GROUP BY TRADE_NO, promotion_id
		) promo ON promo.TRADE_NO = base.TRADE_NO
		STRAIGHT_JOIN LOCATION_MST clm ON clm.LOCATION_CODE = base.LOCATION_CODE
		ORDER BY promo.rn ASC;
		
		DROP VIEW IF EXISTS v_promotion_meta_ext_value_ussd;
		CREATE VIEW v_promotion_meta_ext_value_ussd AS	
		SELECT
				`BM Entity Type`, `Promotion ID`, `Name`, `Extension Type`,
				`marketSegment`, `Channels`, `Languages`, `campaignValidationPattern`
		FROM (
				SELECT DISTINCT
						CAST('Promotion Extension'      AS CHAR)  AS `BM Entity Type`,
						CAST(promo.promotion_id         AS CHAR)  AS `Promotion ID`,
						CAST('USSD Validation'          AS CHAR)  AS `Name`,
						CAST('ussdValidation'           AS CHAR)  AS `Extension Type`,
						CAST('Residence'                AS CHAR)  AS `marketSegment`,
						CAST('All'                      AS CHAR)  AS `Channels`,
						CAST(NULL                       AS CHAR)  AS `Languages`,
						CAST(NULL   					          AS CHAR)  AS `campaignValidationPattern`,
						promo.rn
				FROM TR_PRIVILEGE cdtp
				JOIN (
						SELECT TRADE_NO, trade_product_id, promotion_id, MIN(rn) AS rn
						FROM tbl_promotion
						GROUP BY TRADE_NO, trade_product_id, promotion_id
				) promo ON promo.trade_product_id = cdtp.`TRADE_PRODUCT_ID`
		) t
		ORDER BY rn ASC;
		
		DROP VIEW IF EXISTS v_promotion_meta_ext_value_channel_hierarchy;
		CREATE VIEW v_promotion_meta_ext_value_channel_hierarchy AS	
		SELECT
				`BM Entity Type`, `Promotion ID`, `Name`, `Extension Type`,
				`marketSegment`, `Channels`, `Languages`,
				`channelL1`, `channelL2`, `channelL3`, `channelL4`
		FROM (
				SELECT DISTINCT
						CAST('Promotion Extension' AS CHAR) AS `BM Entity Type`,
						CAST(promo.promotion_id AS CHAR) AS `Promotion ID`,
						CAST('Channel Hierarchy' AS CHAR) AS `Name`,
						CAST('channelHierarchy' AS CHAR) AS `Extension Type`,
						CAST(NULL AS CHAR) AS `marketSegment`,
						CAST(NULL AS CHAR) AS `Channels`,
						CAST(NULL AS CHAR) AS `Languages`,
						CAST(ctc.`SALE_CHANNEL` AS CHAR) AS `channelL1`,
						CAST(
								CASE
										WHEN ctc.`PUBLIC_NAME` IN ('ALL','NULL') OR ctc.`PUBLIC_NAME` IS NULL
										THEN NULL
										ELSE ctc.`PUBLIC_NAME`
								END AS CHAR
						) AS `channelL2`,
						CAST(
								CASE
										WHEN ctc.`PUBLIC_NAME` IN ('ALL','NULL') OR ctc.`PUBLIC_NAME` IS NULL THEN NULL
										WHEN ctc.`SHOP_TYPE_GROUP` IN ('ALL','NULL') OR ctc.`SHOP_TYPE_GROUP` IS NULL THEN NULL
										ELSE ctc.`SHOP_TYPE_GROUP`
								END AS CHAR
						) AS `channelL3`,
						CAST(
								CASE
										WHEN ctc.`PUBLIC_NAME` IN ('ALL','NULL') OR ctc.`PUBLIC_NAME` IS NULL THEN NULL
										WHEN ctc.`SHOP_TYPE_GROUP` IN ('ALL','NULL') OR ctc.`SHOP_TYPE_GROUP` IS NULL THEN NULL
										WHEN ctc.`SHOP_TYPE` IN ('ALL','NULL') OR ctc.`SHOP_TYPE` IS NULL THEN NULL
										ELSE ctc.`SHOP_TYPE`
								END AS CHAR
						) AS `channelL4`,
						promo.rn
				FROM TR_CN ctc
				INNER JOIN tbl_promotion promo
						ON promo.trade_no = ctc.`TRADE_NO`
				WHERE ctc.`SALE_CHANNEL` IS NOT NULL
					AND ctc.`SALE_CHANNEL` <> 'NULL'
		) t
		ORDER BY rn;

END proc_label$$
$$
$$
$$

DELIMITER;

/*

-- 1
SELECT
CONVERT(CAST(TDC.TRADE_DISCOUNT_ID AS CHAR) USING utf8mb4)
COLLATE utf8mb4_general_ci                  AS EXTERNAL_ID,
CONVERT(CONCAT(
CAST(TDC.TRADE_DISCOUNT_ID AS CHAR),
' ', TM.CAMPAIGN, ' ', TM.TRADE_NAME,
' discount ',
CAST(REPLACE(IFNULL(TDC.TRADE_PRICE_EXC_VAT, TDC.DISCOUNT_EXC), '.', '_') AS CHAR),
' Baht for ',
IFNULL(TPD.BRAND, ''), ' ', IFNULL(TPD.MODEL, ''),
' ', IFNULL(TPD.COLOR, ''), ' ', IFNULL(TPD.MAT_CODE, ''),
CASE
WHEN IFNULL(TPD.MIN_PRICE_LENGTH, '') = ''
AND IFNULL(TPD.MAX_PRICE_LENGTH, '') = '' THEN ''
WHEN IFNULL(TPD.MIN_PRICE_LENGTH, '') = ''
THEN CONCAT(' ', TPD.MAX_PRICE_LENGTH)
WHEN IFNULL(TPD.MAX_PRICE_LENGTH, '') = ''
THEN CONCAT(' ', TPD.MIN_PRICE_LENGTH)
ELSE CONCAT(' ', TPD.MIN_PRICE_LENGTH, '-', TPD.MAX_PRICE_LENGTH)
END
) USING utf8mb4) COLLATE utf8mb4_general_ci    AS PROMOTION_NAME,
CASE
WHEN TDC.TRADE_PRICE_EXC_VAT IS NULL THEN 'Discount'
ELSE 'Reduction'
END                                             AS PROMOTION_TYPE,
NULL                                            AS CODE,
'Launched'                                      AS LIFECYCLE_STATUS,
NULL                                            AS COUPON,
'mutuallyExclusive'                             AS PROMOTION_CLASSIFICATION,
'Cart'                                          AS PROMOTION_APPLICATION_LEVEL,
safe_to_datetime(TDC.START_DATE)                AS VALID_FOR_START_DATETIME,
safe_to_datetime(TDC.END_DATE)                  AS VALID_FOR_END_DATETIME,
NULL                                            AS ACTION_CARDINALITY,
CONVERT(CAST(IFNULL(TDC.TRADE_PRICE_EXC_VAT, TDC.DISCOUNT_EXC) AS CHAR)
USING utf8mb4) COLLATE utf8mb4_general_ci  AS ACTION_VALUE,
'Onetime'                                       AS PRICE_TYPE,
IFNULL(TDC.OPTIONS, 1)                          AS PRIORITY,
NULL                                            AS ACTION_OBJECT_ID,
NULL                                            AS PRICE_ID,
CASE
WHEN TDC.DISCOUNT_BY = 'B'               THEN 'Flat Discount'
WHEN TDC.DISCOUNT_BY = 'P'               THEN 'Percent Discount'
WHEN TDC.TRADE_PRICE_EXC_VAT IS NOT NULL THEN 'Flat Price'
ELSE NULL
END                                             AS ACTION_TYPE,
CONVERT(TPD.MAT_CODE USING utf8mb4)
COLLATE utf8mb4_general_ci                  AS SKU,
NULL                                            AS AWARD_PRODUCT_ID,
CONVERT(POV.variantId USING utf8mb4)
COLLATE utf8mb4_general_ci                  AS VARIANT_ID,
CONVERT(POV.`Product Id` USING utf8mb4)
COLLATE utf8mb4_general_ci                  AS PRODUCT_OFFER_ID,
CONVERT(POV.`value` USING utf8mb4)
COLLATE utf8mb4_general_ci                  AS CHARACTERISTIC_VALUE,
NULL                                            AS APPLICATION_DURATION,
CONVERT(TM.TRADE_NO USING utf8mb4)
COLLATE utf8mb4_general_ci                  AS TRADE_NO,
CONVERT(TM.TRADE_NAME USING utf8mb4)
COLLATE utf8mb4_general_ci                  AS TRADE_NAME,
CONVERT(TDC.TRADE_DISCOUNT_ID USING utf8mb4)
COLLATE utf8mb4_general_ci                  AS TRADE_DISCOUNT_ID,
CONVERT(TPD.TRADE_PRODUCT_ID USING utf8mb4)
COLLATE utf8mb4_general_ci                  AS TRADE_PRODUCT_ID,
NULL																						AS TRADE_FREE_GOODS_ID,
CONVERT(TM.CAMPAIGN USING utf8mb4)
COLLATE utf8mb4_general_ci                  AS CAMPAIGN,
'PART1_DISCOUNT_REDUCTION'                      AS PROMOTION_SOURCE
FROM TR_PRODUCT TPD
LEFT JOIN TR_MST      TM  ON TM.TRADE_NO          = TPD.TRADE_NO
LEFT JOIN TR_DISCOUNT TDC ON TDC.TRADE_PRODUCT_ID = TPD.TRADE_PRODUCT_ID
LEFT JOIN tbl_product_offering_variant POV ON POV.SKU = TPD.MAT_CODE
WHERE NOW() BETWEEN
safe_to_datetime(TPD.START_DATE)
AND safe_to_datetime(TPD.END_DATE)
AND TDC.TRADE_DISCOUNT_ID IS NOT NULL
AND NOW() BETWEEN
safe_to_datetime(TDC.START_DATE)
AND safe_to_datetime(TDC.END_DATE)
AND TM.SALE_TYPE = 'SALE';

-- 2&3
SELECT
CONVERT(CAST(TFG.TRADE_FREE_GOODS_ID AS CHAR) USING utf8mb4)
COLLATE utf8mb4_general_ci                  AS EXTERNAL_ID,
CONVERT(CONCAT(
CAST(TFG.TRADE_FREE_GOODS_ID AS CHAR),
' ', TM.CAMPAIGN, ' ', TM.TRADE_NAME,
' reward ', TFG.MAT_CODE, ' for ',
IFNULL(TPD.BRAND, ''), ' ', IFNULL(TPD.MODEL, ''),
' ', IFNULL(TPD.COLOR, ''), ' ', IFNULL(TPD.MAT_CODE, ''),
-- แสดง price length range เฉพาะกรณี ALL
CASE
WHEN fg_grp.fg_type NOT LIKE '%PART2_FG_ALL%' THEN ''
WHEN IFNULL(TPD.MIN_PRICE_LENGTH, '') = ''
AND IFNULL(TPD.MAX_PRICE_LENGTH, '') = '' THEN ''
WHEN IFNULL(TPD.MIN_PRICE_LENGTH, '') = ''
THEN CONCAT(' ', TPD.MAX_PRICE_LENGTH)
WHEN IFNULL(TPD.MAX_PRICE_LENGTH, '') = ''
THEN CONCAT(' ', TPD.MIN_PRICE_LENGTH)
ELSE CONCAT(' ', TPD.MIN_PRICE_LENGTH, '-', TPD.MAX_PRICE_LENGTH)
END
) USING utf8mb4) COLLATE utf8mb4_general_ci    AS PROMOTION_NAME,
'Award'                                         AS PROMOTION_TYPE,
NULL                                            AS CODE,
'Launched'                                      AS LIFECYCLE_STATUS,
NULL                                            AS COUPON,
'stackable'                                     AS PROMOTION_CLASSIFICATION,
'Cart'                                          AS PROMOTION_APPLICATION_LEVEL,
safe_to_datetime(TFG.START_DATE)                AS VALID_FOR_START_DATETIME,
safe_to_datetime(TFG.END_DATE)                  AS VALID_FOR_END_DATETIME,
1                                               AS ACTION_CARDINALITY,
CONVERT(CAST(TFG.QTY AS CHAR) USING utf8mb4)
COLLATE utf8mb4_general_ci                  AS ACTION_VALUE,
NULL                                            AS PRICE_TYPE,
NULL                                            AS PRIORITY,
NULL                                            AS ACTION_OBJECT_ID,
NULL                                            AS PRICE_ID,
'Add Product'                                   AS ACTION_TYPE,
CONVERT(TFG.MAT_CODE USING utf8mb4)
COLLATE utf8mb4_general_ci                  AS SKU,
CONVERT(POV.variantId USING utf8mb4)
COLLATE utf8mb4_general_ci                  AS AWARD_PRODUCT_ID,
CONVERT(POV.variantId USING utf8mb4)
COLLATE utf8mb4_general_ci                  AS VARIANT_ID,
CONVERT(POV.`Product Id` USING utf8mb4)
COLLATE utf8mb4_general_ci                  AS PRODUCT_OFFER_ID,
CONVERT(POV.`value` USING utf8mb4)
COLLATE utf8mb4_general_ci                  AS CHARACTERISTIC_VALUE,
NULL                                            AS APPLICATION_DURATION,
CONVERT(TM.TRADE_NO USING utf8mb4)
COLLATE utf8mb4_general_ci                  AS TRADE_NO,
CONVERT(TM.TRADE_NAME USING utf8mb4)
COLLATE utf8mb4_general_ci                  AS TRADE_NAME,
NULL 																						AS TRADE_DISCOUNT_ID,
CONVERT(TPD.TRADE_PRODUCT_ID USING utf8mb4)
COLLATE utf8mb4_general_ci                  AS TRADE_PRODUCT_ID,
TFG.TRADE_FREE_GOODS_ID													AS TRADE_FREE_GOODS_ID,
CONVERT(TM.CAMPAIGN USING utf8mb4)
COLLATE utf8mb4_general_ci                  AS CAMPAIGN,
fg_grp.fg_type                                  AS PROMOTION_SOURCE
FROM TR_PRODUCT TPD
LEFT JOIN TR_MST        TM  ON TM.TRADE_NO          = TPD.TRADE_NO
LEFT JOIN TR_FREE_GOODS TFG ON TFG.TRADE_PRODUCT_ID = TPD.TRADE_PRODUCT_ID
LEFT JOIN tbl_product_offering_variant POV ON POV.SKU = TFG.MAT_CODE
-- subquery classify ALL / CHOICE / ทั้งคู่ ต่อ TRADE_PRODUCT_ID
JOIN (
SELECT
grp.TRADE_PRODUCT_ID,
GROUP_CONCAT(
DISTINCT grp.type_label
ORDER BY grp.type_label
SEPARATOR ','
) AS fg_type
FROM (
SELECT
TPD3.TRADE_PRODUCT_ID,
CASE
WHEN TPD3.MAX_RECEIVE_FREE_GOODS = COUNT(*) THEN 'PART2_FG_ALL'
ELSE 'PART3_FG_CHOICE'
END AS type_label
FROM TR_PRODUCT   TPD3
INNER JOIN TR_FREE_GOODS TFG3
ON TFG3.TRADE_PRODUCT_ID = TPD3.TRADE_PRODUCT_ID
WHERE NOW() BETWEEN
safe_to_datetime(TFG3.START_DATE)
AND safe_to_datetime(TFG3.END_DATE)
GROUP BY
TPD3.TRADE_PRODUCT_ID,
TPD3.MAX_RECEIVE_FREE_GOODS
HAVING TPD3.MAX_RECEIVE_FREE_GOODS <= COUNT(*)
) grp
GROUP BY grp.TRADE_PRODUCT_ID
) AS fg_grp ON fg_grp.TRADE_PRODUCT_ID = TPD.TRADE_PRODUCT_ID
WHERE NOW() BETWEEN
safe_to_datetime(TPD.START_DATE)
AND safe_to_datetime(TPD.END_DATE)
AND NOW() BETWEEN
safe_to_datetime(TFG.START_DATE)
AND safe_to_datetime(TFG.END_DATE)
AND TM.SALE_TYPE = 'SALE';

*/