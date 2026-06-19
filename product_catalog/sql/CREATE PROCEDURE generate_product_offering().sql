DELIMITER $$

DROP PROCEDURE IF EXISTS generate_product_offering$$

CREATE PROCEDURE generate_product_offering(
    IN  batch_id   				INT,
    IN  p_created_by    	VARCHAR(255)
)

proc_label: BEGIN
    DECLARE v_of_start   INT          DEFAULT 0;
    DECLARE v_of_prefix  VARCHAR(50)  DEFAULT '';
    DECLARE v_of_suffix  VARCHAR(50)  DEFAULT '';
    DECLARE v_of_pad     INT          DEFAULT 6;
    DECLARE v_cat_start  INT          DEFAULT 0;
    DECLARE v_cat_prefix VARCHAR(50)  DEFAULT '';
    DECLARE v_cat_suffix VARCHAR(50)  DEFAULT '';
    DECLARE v_cat_pad    INT          DEFAULT 6;
    DECLARE v_cat_count  INT          DEFAULT 0;
    DECLARE v_new_count  INT          DEFAULT 0;
    DECLARE v_rn_offset  INT          DEFAULT 0;
		DECLARE v_actor      VARCHAR(255) DEFAULT 'system';

    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        RESIGNAL;
    END;

		SET v_actor = IFNULL(NULLIF(TRIM(p_created_by), ''), 'system');
		
    -- Guard: เพิ่ม column isGenerate ถ้ายังไม่มี
    IF NOT EXISTS (
        SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
        WHERE  TABLE_SCHEMA = DATABASE()
          AND  TABLE_NAME   = 'PRODUCT_MST'
          AND  COLUMN_NAME  = 'isGenerate'
    ) THEN
        ALTER TABLE PRODUCT_MST ADD COLUMN isGenerate TINYINT(1) DEFAULT NULL;
    END IF;

    -- Guard: ไม่มีแถวใหม่ให้ generate
    IF NOT EXISTS (
        SELECT 1 FROM PRODUCT_MST
        WHERE IFNULL(isGenerate, 0) = 0
        AND PRODUCT_TYPE NOT IN ('SERVICE')
        LIMIT 1
    ) THEN
        SELECT 'No new records to generate — all rows already generated.' AS message;
        LEAVE proc_label;
    END IF;

    UPDATE PRODUCT_MST SET isGenerate = 0
    WHERE IFNULL(isGenerate, 0) = 0
    AND PRODUCT_TYPE NOT IN ('SERVICE');

    -- Step 1: สร้าง tbl_product_offering ถ้ายังไม่มี
    CREATE TABLE IF NOT EXISTS tbl_product_offering (
        PO_ID                    TEXT,
        PO_NAME                  TEXT,
        V_ID                     TEXT,
        SKU                      TEXT,
        PRODUCT_LINE             TEXT,
        PRODUCT_TYPE             TEXT,
        PRODUCT_LINE_TYPE_PAIR   TEXT,
				PRODUCT_LINE_GROUP_CONCAT TEXT,
				PRODUCT_TYPE_GROUP_CONCAT TEXT,
        VALID_FOR_START_DATETIME DATETIME,
        VALID_FOR_END_DATETIME   DATETIME,
        VALUATION_CLASS          TEXT,
        rn                       INT,
        MAIN_MODEL               TEXT,
        BRAND                    TEXT,
        COMMERCIAL_NAME          TEXT,
        SAP_DESCRIPTION          TEXT,
        COMPANY                  TEXT,
        MAT_CODE                 TEXT,
        PRODUCT_ID               TEXT,
        GRADE                    VARCHAR(50),
				batch_id_insert     			INT,
				batch_id_update     			INT,
        created_by               VARCHAR(255) DEFAULT 'system',
        created_at               DATETIME(3)  DEFAULT NOW(3),
        updated_by               VARCHAR(255) DEFAULT NULL,
        updated_at               DATETIME(3)  DEFAULT NULL,
        INDEX idx_rn (rn)
    );

    -- เพิ่ม UNIQUE index บน PO_NAME ถ้ายังไม่มี
    IF NOT EXISTS (
				SELECT 1 FROM INFORMATION_SCHEMA.STATISTICS
				WHERE TABLE_SCHEMA = DATABASE()
					AND TABLE_NAME   = 'tbl_product_offering'
					AND INDEX_NAME   = 'idx_po_name_type'
		) THEN
				ALTER TABLE tbl_product_offering
				ADD UNIQUE INDEX idx_po_name_type (PO_NAME(255), PRODUCT_LINE(100), PRODUCT_TYPE(100));
		END IF;

    -- เพิ่ม column PRODUCT_LINE_TYPE_PAIR ถ้ายังไม่มี
    IF NOT EXISTS (
        SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME   = 'tbl_product_offering'
          AND COLUMN_NAME  = 'PRODUCT_LINE_TYPE_PAIR'
    ) THEN
        ALTER TABLE tbl_product_offering
        ADD COLUMN PRODUCT_LINE_TYPE_PAIR TEXT AFTER PRODUCT_TYPE;
    END IF;
		
		IF NOT EXISTS (
				SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
				WHERE TABLE_SCHEMA = DATABASE()
					AND TABLE_NAME   = 'tbl_product_offering'
					AND COLUMN_NAME  = 'PRODUCT_LINE_GROUP_CONCAT'
		) THEN
				ALTER TABLE tbl_product_offering
				ADD COLUMN PRODUCT_LINE_GROUP_CONCAT TEXT AFTER PRODUCT_LINE_TYPE_PAIR;
		END IF;

		IF NOT EXISTS (
				SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
				WHERE TABLE_SCHEMA = DATABASE()
					AND TABLE_NAME   = 'tbl_product_offering'
					AND COLUMN_NAME  = 'PRODUCT_TYPE_GROUP_CONCAT'
		) THEN
				ALTER TABLE tbl_product_offering
				ADD COLUMN PRODUCT_TYPE_GROUP_CONCAT TEXT AFTER PRODUCT_LINE_GROUP_CONCAT;
		END IF;

    SELECT COUNT(*) INTO v_rn_offset FROM tbl_product_offering;

    SET SESSION group_concat_max_len = 1000000;

    -- Step 2: Group ข้อมูลใหม่ลง tmp table
		DROP TEMPORARY TABLE IF EXISTS tmp_grouped;
		CREATE TEMPORARY TABLE tmp_grouped AS
		SELECT
				clean_name(
						CONCAT(
								IFNULL(
										CASE WHEN MAX(pm.MAIN_MODEL) IS NOT NULL
												THEN CONCAT_WS(' ', NULLIF(TRIM(MAX(pm.BRAND)), ''), MAX(pm.MAIN_MODEL))
										END,
										IFNULL(MAX(pm.COMMERCIAL_NAME),
												IFNULL(MAX(pm.SAP_DESCRIPTION),
														CONCAT(MAX(pm.COMPANY), '_', MAX(pm.MAT_CODE))
												)
										)
								),
								CASE WHEN IFNULL(MAX(pm.GRADE), '') IN ('GD', 'DEM') THEN ' GD' ELSE '' END
						)
				) AS PO_NAME,
				GROUP_CONCAT(DISTINCT pm.MAT_CODE
						ORDER BY pm.MAT_CODE SEPARATOR ', ')                                AS SKU,
				clean_name(GROUP_CONCAT(DISTINCT CONCAT_WS('_', IFNULL(pm.CAPACITY, 'n_a'), IFNULL(pm.COLOR, 'n_a'))
						ORDER BY pm.CAPACITY, pm.COLOR SEPARATOR ', '))                      AS V_ID,
				pm.PRODUCT_TYPE                                                         AS PRODUCT_LINE,
				pm.PRODUCT_SUBTYPE                                                      AS PRODUCT_TYPE,
				CONCAT(pm.PRODUCT_TYPE, '|', IFNULL(pm.PRODUCT_SUBTYPE, ''))           	AS PRODUCT_LINE_TYPE_PAIR,
				pm.PRODUCT_TYPE                                                         AS PRODUCT_LINE_GROUP_CONCAT,
				IFNULL(pm.PRODUCT_SUBTYPE, '')                                          AS PRODUCT_TYPE_GROUP_CONCAT,
				GROUP_CONCAT(DISTINCT pm.VALUATION_CLASS
						ORDER BY pm.VALUATION_CLASS SEPARATOR ', ')                         AS VALUATION_CLASS,
				MIN(pm.EFFECTIVE_DATE)                                                  AS MIN_EFFECTIVE_DATE,
				MAX(pm.EXPIRE_DATE)                                                     AS MAX_EXPIRE_DATE,
				clean_name(MAX(pm.MAIN_MODEL))                                          AS MAIN_MODEL,
				clean_name(MAX(pm.BRAND))                                               AS BRAND,
				clean_name(MAX(pm.COMMERCIAL_NAME))                                     AS COMMERCIAL_NAME,
				clean_name(MAX(pm.SAP_DESCRIPTION))                                     AS SAP_DESCRIPTION,
				clean_name(MAX(pm.COMPANY))                                             AS COMPANY,
				GROUP_CONCAT(DISTINCT pm.MAT_CODE
						ORDER BY pm.MAT_CODE SEPARATOR ', ')                                AS MAT_CODE,
				GROUP_CONCAT(DISTINCT pm.PRODUCT_ID
						ORDER BY pm.PRODUCT_ID SEPARATOR ', ')                              AS PRODUCT_ID,
				MAX(pm.GRADE)                                                           AS GRADE
		FROM PRODUCT_MST pm
		WHERE IFNULL(pm.isGenerate, 0) = 0
		AND pm.PRODUCT_TYPE NOT IN ('SERVICE')
		GROUP BY
				CASE WHEN pm.MAIN_MODEL IS NOT NULL
						THEN CONCAT_WS(' ', NULLIF(TRIM(pm.BRAND), ''), pm.MAIN_MODEL)
						ELSE IFNULL(pm.COMMERCIAL_NAME,
										IFNULL(pm.SAP_DESCRIPTION, CONCAT(pm.COMPANY, '_', pm.MAT_CODE)))
				END,
				CASE WHEN IFNULL(pm.GRADE, '') IN ('GD', 'DEM') THEN 'GD' ELSE '' END,
				pm.PRODUCT_TYPE,
				pm.PRODUCT_SUBTYPE;

    -- นับเฉพาะ PO ใหม่ที่ยังไม่มีใน tbl_product_offering
    SELECT COUNT(*) INTO v_new_count
    FROM tmp_grouped tg
    WHERE NOT EXISTS (
        SELECT 1 FROM tbl_product_offering po
        WHERE po.PO_NAME = tg.PO_NAME
    );

    START TRANSACTION;

    -- Step 3: Reserve sequence batch ผ่าน get_next_sequence_batch
    CALL get_next_sequence_batch('product_offering', NULL, v_new_count,
        v_of_start, @v_of_end, @v_of_prefix, @v_of_suffix, v_of_pad);

    SET v_of_prefix = IFNULL(@v_of_prefix, '');
    SET v_of_suffix = IFNULL(@v_of_suffix, '');

    -- Step 4: Upsert product offering
    INSERT INTO tbl_product_offering
        (PO_ID, PO_NAME, V_ID, SKU, PRODUCT_LINE, PRODUCT_TYPE, PRODUCT_LINE_TYPE_PAIR, PRODUCT_LINE_GROUP_CONCAT, PRODUCT_TYPE_GROUP_CONCAT,
         VALID_FOR_START_DATETIME, VALID_FOR_END_DATETIME, VALUATION_CLASS, rn,
         MAIN_MODEL, BRAND, COMMERCIAL_NAME, SAP_DESCRIPTION, COMPANY, MAT_CODE, PRODUCT_ID, GRADE,
         batch_id_insert, created_by, created_at)
    SELECT
        CONCAT(
            v_of_prefix,
            t.PO_ID,
            v_of_suffix,
            LPAD(v_of_start + t.rn, v_of_pad, '0')
        ),
        t.PO_NAME, t.V_ID, t.SKU, t.PRODUCT_LINE, t.PRODUCT_TYPE, t.PRODUCT_LINE_TYPE_PAIR, t.PRODUCT_LINE_GROUP_CONCAT, t.PRODUCT_TYPE_GROUP_CONCAT,
        t.MIN_EFFECTIVE_DATE, t.MAX_EXPIRE_DATE, t.VALUATION_CLASS, t.rn,
        t.MAIN_MODEL, t.BRAND, t.COMMERCIAL_NAME, t.SAP_DESCRIPTION, t.COMPANY, t.MAT_CODE, t.PRODUCT_ID, t.GRADE,
        batch_id, v_actor, NOW(3)
    FROM (
        SELECT
								clean_id (tg.PO_NAME) AS PO_ID,
								clean_name (tg.PO_NAME) AS PO_NAME,
								tg.V_ID,
								tg.SKU,
								tg.PRODUCT_LINE,
								tg.PRODUCT_TYPE,
								tg.PRODUCT_LINE_TYPE_PAIR,
								tg.PRODUCT_LINE_GROUP_CONCAT,
								tg.PRODUCT_TYPE_GROUP_CONCAT,
								tg.MIN_EFFECTIVE_DATE,
								tg.MAX_EXPIRE_DATE,
								tg.VALUATION_CLASS,
								clean_name(tg.MAIN_MODEL)       AS MAIN_MODEL,
								clean_name(tg.BRAND)            AS BRAND,
								clean_name(tg.COMMERCIAL_NAME)  AS COMMERCIAL_NAME,
								clean_name(tg.SAP_DESCRIPTION)  AS SAP_DESCRIPTION,
								clean_name(tg.COMPANY)          AS COMPANY,
								tg.MAT_CODE,
								tg.PRODUCT_ID,
								tg.GRADE,
								CASE
									WHEN po_exist.PO_NAME IS NULL THEN
										v_rn_offset + ROW_NUMBER() OVER (PARTITION BY CASE WHEN po_exist.PO_NAME IS NULL THEN 1 ELSE 0 END ORDER BY tg.PO_NAME) - 1
									ELSE
										NULL
								END AS rn
        FROM tmp_grouped tg
        LEFT JOIN tbl_product_offering po_exist
						ON  clean_name(po_exist.PO_NAME)  = clean_name(tg.PO_NAME)
						AND po_exist.PRODUCT_LINE         = tg.PRODUCT_LINE
						AND IFNULL(po_exist.PRODUCT_TYPE, '') = IFNULL(tg.PRODUCT_TYPE, '')
    ) t
    ON DUPLICATE KEY UPDATE
        V_ID                     = VALUES(V_ID),
        SKU                      = VALUES(SKU),
        PRODUCT_LINE             = VALUES(PRODUCT_LINE),
        PRODUCT_TYPE             = VALUES(PRODUCT_TYPE),
        PRODUCT_LINE_TYPE_PAIR   = VALUES(PRODUCT_LINE_TYPE_PAIR),
				PRODUCT_LINE_GROUP_CONCAT 	= VALUES(PRODUCT_LINE_GROUP_CONCAT),
				PRODUCT_TYPE_GROUP_CONCAT		= VALUES(PRODUCT_TYPE_GROUP_CONCAT),
        VALID_FOR_START_DATETIME = VALUES(VALID_FOR_START_DATETIME),
        VALID_FOR_END_DATETIME   = VALUES(VALID_FOR_END_DATETIME),
        VALUATION_CLASS          = VALUES(VALUATION_CLASS),
        MAIN_MODEL               = VALUES(MAIN_MODEL),
        BRAND                    = VALUES(BRAND),
        COMMERCIAL_NAME          = VALUES(COMMERCIAL_NAME),
        SAP_DESCRIPTION          = VALUES(SAP_DESCRIPTION),
        COMPANY                  = VALUES(COMPANY),
        MAT_CODE                 = CONCAT(tbl_product_offering.MAT_CODE, ', ', VALUES(MAT_CODE)),
        PRODUCT_ID               = CONCAT(tbl_product_offering.PRODUCT_ID, ', ', VALUES(PRODUCT_ID)),
        GRADE                    = VALUES(GRADE),
				batch_id_update					 = batch_id,
        updated_by               = v_actor,
        updated_at               = NOW(3);

    UPDATE PRODUCT_MST SET isGenerate = 1
    WHERE isGenerate = 0
    AND PRODUCT_TYPE NOT IN ('SERVICE');

    COMMIT;

    DROP TEMPORARY TABLE IF EXISTS tmp_grouped;

    -- Step 5: Recreate views
    DROP VIEW IF EXISTS v_product_offering;
		CREATE VIEW v_product_offering AS
		SELECT
				CAST(t.PO_ID AS CHAR)                                                            AS `Product Id`,
				CAST(NULL AS CHAR)                                                               AS `External ID`,
				CAST(ptm.PRODUCT_SPECIFICATION AS CHAR)                                          AS `productSpecification_id`,
				CAST(t.PO_NAME AS CHAR)                                                          AS `Product Name`,
				'Residence'                                                                      AS `Market Segment`,
				'All'                                                                            AS `Channel`,
				CAST(NULL AS CHAR)                                                               AS `Offer Label`,
				CAST(NULL AS CHAR)                                                               AS `Offer Term`,
				'All'                                                                            AS `Place`,
				CAST(NULL AS CHAR)                                                               AS `offerGroupId`,
				CAST(NULL AS CHAR)                                                               AS `isLocationDependent`,

				CAST(
						CASE
								WHEN t.GRADE IN ('GD', 'DEM') THEN 'FALSE'
								ELSE 'TRUE'
						END AS CHAR
				)                                                                                AS `isSellable`,

				'FALSE'                                                                          AS `isBundle`,
				CAST(NULL AS CHAR)                                                               AS `bundlePriceOption`,
				'TRUE'                                                                           AS `isAssetable`,
				'TRUE'                                                                           AS `hasVariants`,
				CAST(t.PRODUCT_LINE AS CHAR)                                                     AS `productType`,
				CAST(NULL AS CHAR)                                                               AS `sku`,

				CAST(
						DATE_FORMAT(
								t.VALID_FOR_START_DATETIME,
								'%Y-%m-%dT%H:%i:%s.000Z'
						) AS CHAR
				)                                                                                AS `validFor_startDateTime`,

				CAST(
						DATE_FORMAT(
								COALESCE(t.VALID_FOR_END_DATETIME, '2999-12-31 23:59:00'),
								'%Y-%m-%dT%H:%i:%s.000Z'
						) AS CHAR
				)                                                                                AS `validFor_endDateTime`,

				CAST(NULL AS CHAR)                                                               AS `description`,
				'Device'                                                                         AS `productLine`,
				CAST(NULL AS CHAR)                                                               AS `offerClassification`,
				CAST(NULL AS CHAR)                                                               AS `offerLabels_name`,
				CAST(NULL AS CHAR)                                                               AS `offerLabels_channel`,
				CAST(NULL AS CHAR)                                                               AS `offerLabels_description`

		FROM tbl_product_offering t
		LEFT JOIN product_type_mapping ptm
				ON  ptm.PRODUCT_TYPE     = t.PRODUCT_LINE
				AND ptm.PRODUCT_SUB_TYPE = t.PRODUCT_TYPE;

    DROP VIEW IF EXISTS v_product_offering_spec_characteristic;
		CREATE VIEW v_product_offering_spec_characteristic AS
		WITH base AS (
				SELECT
						po.PO_ID,
						po.rn,
						ptm.PRODUCT_SPECIFICATION,
						ptm.RESOURCE_SPECIFICATION
				FROM tbl_product_offering po
				LEFT JOIN product_type_mapping ptm
						ON  ptm.PRODUCT_TYPE     = po.PRODUCT_LINE
						AND ptm.PRODUCT_SUB_TYPE = po.PRODUCT_TYPE
		),
		unpivot AS (
				SELECT
						PO_ID,
						rn,
						PRODUCT_SPECIFICATION AS spec_id
				FROM base

				UNION ALL

				SELECT
						PO_ID,
						rn,
						RESOURCE_SPECIFICATION AS spec_id
				FROM base
		)
		SELECT
				CAST(u.PO_ID AS CHAR)                       AS `SpecCharacteristic.Product Offer ID`,
				CAST(u.spec_id AS CHAR)                    AS `SpecCharacteristic.Product Spec ID`,
				CAST(sc.`Characteristics ID` AS CHAR)      AS `SpecCharacteristic.Characteristics ID`,
				CAST(sc.`name` AS CHAR)                    AS `SpecCharacteristic.Charactristics Name`,
				CAST(sc.`valueType` AS CHAR)               AS `SpecCharacteristic.Charactristics valueType`
		FROM unpivot u
		LEFT JOIN spec_characteristics sc
				ON sc.`Spec ID` = u.spec_id
		WHERE u.spec_id IS NOT NULL
		ORDER BY
				u.rn,
				u.spec_id,
				sc.`Characteristics ID`;

    CREATE TABLE IF NOT EXISTS tbl_product_offering_category (
        PO_ID           VARCHAR(255),
        OLD_ID          VARCHAR(255),
        category_id     VARCHAR(255),
        parent_category VARCHAR(255),
        valuation_class VARCHAR(255),
        category_name   VARCHAR(255),
        description     TEXT,
				level           VARCHAR(5)
    );

    INSERT INTO tbl_product_offering_category (
        PO_ID, OLD_ID, category_id, parent_category, valuation_class, category_name, description, level
    )
    SELECT
				CAST(t.PO_ID AS CHAR) AS PO_ID,
				CAST(t.code AS CHAR) AS OLD_ID,
				CAST(t.`Category ID` AS CHAR) AS category_id,
				CAST(t.`Parent Category` AS CHAR) AS parent_category,
				CAST(t.VALUATION_CLASS AS CHAR) AS valuation_class,
				CAST(t.`Category Name` AS CHAR) AS category_name,
				CAST(t.Description AS CHAR) AS description,
				CAST(t.level AS CHAR) AS level
		FROM (
				SELECT
						po.PO_ID,
						po.VALUATION_CLASS,

						c.OLD_ID AS code,
						c.`Category ID`,
						c.`Parent Category`,
						c.`Category Name`,
						c.Description,

						CASE
								WHEN CHAR_LENGTH(c.OLD_ID) < 2 THEN 0
								WHEN CHAR_LENGTH(c.OLD_ID) = 2 THEN 1
								WHEN CHAR_LENGTH(c.OLD_ID) = 5 THEN 2
								WHEN CHAR_LENGTH(c.OLD_ID) = 9 THEN 3
								WHEN CHAR_LENGTH(c.OLD_ID) > 9 THEN 4
								ELSE 0
						END AS level

				FROM tbl_product_offering po

				JOIN (
						WITH RECURSIVE nums AS (
								SELECT 1 AS n
								UNION ALL
								SELECT n + 1
								FROM nums
								WHERE n < (
										SELECT MAX(
												CHAR_LENGTH(VALUATION_CLASS)
												- CHAR_LENGTH(REPLACE(VALUATION_CLASS, ',', '')) + 1
										)
										FROM tbl_product_offering
								)
						)
						SELECT n
						FROM nums
				) nums
						ON CHAR_LENGTH(po.VALUATION_CLASS)
						- CHAR_LENGTH(REPLACE(po.VALUATION_CLASS, ',', '')) >= nums.n - 1

				LEFT JOIN category c
						ON c.OLD_ID = TRIM(
								SUBSTRING_INDEX(
										SUBSTRING_INDEX(po.VALUATION_CLASS, ',', nums.n),
										',',
										-1
								)
						)

				WHERE NOT EXISTS (
						SELECT 1
						FROM tbl_product_offering_category poc
						WHERE poc.PO_ID = po.PO_ID
								AND poc.OLD_ID = COALESCE(c.OLD_ID, po.VALUATION_CLASS)
				)

		) t;

    DROP VIEW IF EXISTS v_product_offering_category_all;
		CREATE VIEW v_product_offering_category_all AS
		SELECT
				CAST(PO_ID AS CHAR)                                                        AS `PO_ID`,
				CAST(OLD_ID AS CHAR)                                                       AS `OLD_ID`,
				CAST(category_id AS CHAR)                                                  AS `Category ID`,
				CAST(parent_category AS CHAR)                                              AS `Parent Category`,
				CAST(category_name AS CHAR)                                                AS `Category Name`,
				CAST(description AS CHAR)                                                  AS `Description`,
				'FALSE'                                                                    AS `isOfferContainer`,
				'Product Offering'                                                         AS `visibility_section`,
				'FALSE'                                                                    AS `isRoot`,
				'TRUE'                                                                     AS `isAnchor`,
				'FALSE'                                                                    AS `mutuallyExclusive`,
				'0-99'                                                                     AS `nodeCardinality`,
				'FALSE'                                                                    AS `visibility`,
				CAST(
						DATE_FORMAT(
								'2026-01-01 00:00:00',
								'%Y-%m-%dT%H:%i:%s.000Z'
						) AS CHAR
				)                                                                          AS `validFor_startDateTime`,
				CAST(
						DATE_FORMAT(
								'9999-12-31 23:59:00',
								'%Y-%m-%dT%H:%i:%s.000Z'
						) AS CHAR
				)                                                                          AS `validFor_endDateTime`
		FROM tbl_product_offering_category;
		
		DROP VIEW IF EXISTS v_product_offering_category;
		CREATE VIEW v_product_offering_category AS
		SELECT
				CAST(PO_ID AS CHAR)             AS `PO_ID`,
				CAST(`Category ID` AS CHAR)     AS `category_id`
		FROM v_product_offering_category_all;


		DROP VIEW IF EXISTS v_product_offering_place;
		CREATE VIEW v_product_offering_place AS
		SELECT
				CAST(`Product Id` AS CHAR)      AS `PO_ID`,
				CAST(`Place` AS CHAR)           AS `ProductOffer.Place`
		FROM v_product_offering;


		DROP VIEW IF EXISTS v_product_offering_channel;
		CREATE VIEW v_product_offering_channel AS
		SELECT
				CAST(`Product Id` AS CHAR)      AS `PO_ID`,
				CAST(`Channel` AS CHAR)         AS `ProductOffer.Channel`
		FROM v_product_offering;


		DROP VIEW IF EXISTS v_product_offering_market_segment;
		CREATE VIEW v_product_offering_market_segment AS
		SELECT
				CAST(`Product Id` AS CHAR)          AS `PO_ID`,
				CAST(`Market Segment` AS CHAR)      AS `ProductOffer.MarketSegment`
		FROM v_product_offering;

    -- Step 6: Return result
    SELECT * FROM v_product_offering
    ORDER BY `Product Id`;

    SELECT * FROM v_product_offering_spec_characteristic
    ORDER BY `SpecCharacteristic.Product Offer ID`,
             `SpecCharacteristic.Characteristics ID`;

END proc_label$$

DELIMITER ;