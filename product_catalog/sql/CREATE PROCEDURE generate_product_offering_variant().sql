SET NAMES utf8mb4 COLLATE utf8mb4_general_ci;
SET collation_connection = 'utf8mb4_general_ci';

DELIMITER $$

DROP PROCEDURE IF EXISTS generate_product_offering_variant$$

CREATE PROCEDURE generate_product_offering_variant(
    IN  batch_id   				INT,
    IN  p_created_by    	VARCHAR(255)
)
BEGIN
		DECLARE v_actor      	VARCHAR(255) DEFAULT 'system';

    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        RESIGNAL;
    END;

    SET SESSION group_concat_max_len = 1000000;
		SET v_actor = IFNULL(NULLIF(TRIM(p_created_by), ''), 'system');

    -- Step 1: Build dynamic JSON_ARRAY columns สำหรับ sort value
    SELECT GROUP_CONCAT(
        CONCAT('IFNULL(`', char_id, '`, '''')')
        ORDER BY char_id ASC
        SEPARATOR ', '
    )
    INTO @v_json_cols
    FROM (SELECT DISTINCT char_id FROM char_to_pm_column WHERE is_active = 1) t;

    -- Step 2: สร้าง tbl_variant_wide โดย sort value ก่อน concat (เพิ่ม rn)
    DROP TABLE IF EXISTS tbl_variant_wide;

    SET @v_sql = CONCAT(
        'CREATE TABLE tbl_variant_wide AS ',
        'SELECT `rn`, `Product ID`, `SKU`, ',
        '    CONCAT(`Product ID`, ''_'', clean_id(sorted_vals)) AS variant_base ',
        'FROM ( ',
        '    SELECT DISTINCT `rn`, `Product ID`, `SKU`, ',
        '        (SELECT GROUP_CONCAT(val ORDER BY val ASC SEPARATOR ''_'') ',
        '         FROM JSON_TABLE( ',
        '             JSON_ARRAY(', @v_json_cols, '), ',
        '             ''$[*]'' COLUMNS (val TEXT PATH ''$'') ',
        '         ) jt ',
        '         WHERE val IS NOT NULL AND val != '''' ',
        '        ) AS sorted_vals ',
        '    FROM tbl_product_offering_variant_unpivot ',
        ') t ',
        'ORDER BY `rn`, `Product ID`, variant_base'
    );

    PREPARE stmt FROM @v_sql;
    EXECUTE stmt;
    DEALLOCATE PREPARE stmt;

    -- Step 3: Build dynamic UNION ALL (เพิ่ม rn)
    SELECT GROUP_CONCAT(
        CONCAT(
            'SELECT DISTINCT v.`rn`, v.`Product ID`, v.`SKU`, w.variant_base, ''', char_id, ''' AS char_id, v.`', char_id, '` AS char_value ',
            'FROM tbl_product_offering_variant_unpivot v ',
            'JOIN tbl_variant_wide w ON w.`Product ID` = v.`Product ID` AND w.`SKU` = v.`SKU` ',
            'WHERE v.`', char_id, '` IS NOT NULL'
        )
        SEPARATOR ' UNION ALL '
    )
    INTO @v_unpivot
    FROM (SELECT DISTINCT char_id FROM char_to_pm_column WHERE is_active = 1) t;

    START TRANSACTION;

    -- Step 4: สร้าง tbl_product_offering_variant ถ้ายังไม่มี
    CREATE TABLE IF NOT EXISTS tbl_product_offering_variant (
        `rn`                                     INT,
        `Product Id`                             VARCHAR(500),
        `variantId`                              VARCHAR(500),
        `isAvailable`                            VARCHAR(10),
        `specCharacteristic.Characteristic Id`   TEXT,
        `specCharacteristic.Characteristic Name` TEXT,
        `value`                                  TEXT,
        `SKU`                                    VARCHAR(255),
        `batch_id_insert`                        INT,
        `batch_id_update`                        INT,
        `created_by`                             VARCHAR(255) DEFAULT 'system',
        `created_at`                             DATETIME(3)  DEFAULT NOW(3),
        `updated_by`                             VARCHAR(255) DEFAULT NULL,
        `updated_at`                             DATETIME(3)  DEFAULT NULL,
        INDEX idx_rn   (`rn`),
        INDEX idx_pid  (`Product Id`(255)),
        INDEX idx_sku  (`SKU`)
    );

    -- Step 5a: Check if price_group_is_default column exists
		SELECT COUNT(*) INTO @v_has_price_group
		FROM information_schema.COLUMNS
		WHERE TABLE_SCHEMA = DATABASE()
			AND TABLE_NAME   = 'tbl_product_offering_variant_unpivot'
			AND COLUMN_NAME  = 'price_group_is_default';

		-- Step 5a: Build new rows เข้า temp ก่อน
		DROP TEMPORARY TABLE IF EXISTS tmp_variant_new;

		SET @v_price_group_col = IF(@v_has_price_group > 0, 
				'u.price_group_is_default', 
				'0'
		);

		SET @v_sql = CONCAT(
				'CREATE TEMPORARY TABLE tmp_variant_new AS ',
				'SELECT ',
				'    `rn`, ',
				'    `Product ID`    AS `Product Id`, ',
				'    variant_base    AS `variantId`, ',
				'    CASE WHEN MAX(price_group_is_default) = 1 THEN ''FALSE'' ELSE ''TRUE'' END AS `isAvailable`, ',
				'    GROUP_CONCAT(DISTINCT char_id    ORDER BY char_id ASC SEPARATOR '','') AS `specCharacteristic.Characteristic Id`, ',
				'    GROUP_CONCAT(DISTINCT `name`     ORDER BY `name`  ASC SEPARATOR '','') AS `specCharacteristic.Characteristic Name`, ',
				'    GROUP_CONCAT(DISTINCT char_value ORDER BY char_id ASC SEPARATOR '','') AS `value`, ',
				'    `SKU` ',
				'FROM ( ',
				'    SELECT DISTINCT ',
				'        c.`rn`, ',
				'        c.`Product ID`, ',
				'        c.`SKU`, ',
				'        REGEXP_REPLACE(clean_id(c.variant_base), ''_of_mg([0-9]+)'', ''-of_mg$1'') AS variant_base, ',
				'        c.char_id, ',
				'        sc.`name`, ',
				'        c.char_value, ',
				'        ', @v_price_group_col, ' AS price_group_is_default ',   -- <- dynamic fallback
				'    FROM (', @v_unpivot, ') c ',
				'    JOIN tbl_product_offering_variant_unpivot u ',
				'        ON u.`Product ID` = c.`Product ID` ',
				'        AND u.`SKU` = c.`SKU` ',
				'    LEFT JOIN spec_characteristics sc ',
				'        ON sc.`Characteristics ID` = c.char_id ',
				') sub ',
				'GROUP BY `rn`, `Product ID`, `SKU`, variant_base ',
				'ORDER BY `rn`, `Product ID`, variant_base'
		);

		PREPARE stmt FROM @v_sql;
		EXECUTE stmt;
		DEALLOCATE PREPARE stmt;

    -- Step 5b: Update rows ที่มีอยู่แล้ว
    UPDATE tbl_product_offering_variant e
    JOIN tmp_variant_new s
        ON  e.`Product Id` = s.`Product Id`
        AND e.`SKU`        = s.`SKU`
        AND e.`variantId`  = s.`variantId`
    SET
        e.`rn`                                     = s.`rn`,
        e.`isAvailable`                            = s.`isAvailable`,
        e.`specCharacteristic.Characteristic Id`   = s.`specCharacteristic.Characteristic Id`,
        e.`specCharacteristic.Characteristic Name` = s.`specCharacteristic.Characteristic Name`,
        e.`value`                                  = s.`value`,
        e.`batch_id_update`                        = batch_id,
        e.`updated_by`                             = v_actor,
        e.`updated_at`                             = NOW(3);

    -- Step 5c: Insert rows ใหม่ที่ยังไม่มี
    INSERT INTO tbl_product_offering_variant (
        `rn`,
        `Product Id`,
        `variantId`,
        `isAvailable`,
        `specCharacteristic.Characteristic Id`,
        `specCharacteristic.Characteristic Name`,
        `value`,
        `SKU`,
        `batch_id_insert`,
        `created_by`,
        `created_at`
    )
    SELECT
        s.`rn`,
        s.`Product Id`,
        s.`variantId`,
        s.`isAvailable`,
        s.`specCharacteristic.Characteristic Id`,
        s.`specCharacteristic.Characteristic Name`,
        s.`value`,
        s.`SKU`,
        batch_id,
        v_actor,
        NOW(3)
    FROM tmp_variant_new s
    WHERE NOT EXISTS (
        SELECT 1
        FROM tbl_product_offering_variant e
        WHERE e.`Product Id` = s.`Product Id`
          AND e.`SKU`        = s.`SKU`
          AND e.`variantId`  = s.`variantId`
    );

    DROP TEMPORARY TABLE IF EXISTS tmp_variant_new;

    COMMIT;

    DROP TABLE IF EXISTS tbl_variant_wide;

		-- Step 6: Create View
  DROP VIEW IF EXISTS v_product_offering_variant;
	CREATE VIEW v_product_offering_variant AS
	SELECT
			CAST(`Product Id` AS CHAR)                                   AS `Product Variants.Product Id`,
			CAST(`variantId` AS CHAR)                                    AS `Product Variants.variantId`,
			CAST(`isAvailable` AS CHAR)                                  AS `Product Variants.isAvailable`,
			CAST(`specCharacteristic.Characteristic Id` AS CHAR)         AS `Product Variants.specCharacteristics`,
			CAST(`value` AS CHAR)                                        AS `Product Variants.value`,
			CAST(`SKU` AS CHAR)                                          AS `Product Variants.sku`
	FROM tbl_product_offering_variant
	ORDER BY `rn`, `Product Id`, `variantId`;

    -- Step 7: Return result
    SELECT * FROM v_product_offering_variant;

END$$

DELIMITER;