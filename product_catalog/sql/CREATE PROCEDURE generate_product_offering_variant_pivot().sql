DELIMITER $$

DROP PROCEDURE IF EXISTS generate_product_offering_variant_pivot$$

CREATE PROCEDURE generate_product_offering_variant_pivot()
BEGIN
    DECLARE v_seq_start INT DEFAULT 0;
    DECLARE v_seq_end   INT DEFAULT 0;
    DECLARE v_padding   INT DEFAULT 6;
    DECLARE v_total     INT DEFAULT 0;

    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        RESIGNAL;
    END;

    SET SESSION group_concat_max_len = 1000000;

    -- Step 1: Build dynamic JSON_ARRAY columns สำหรับ sort value
    SELECT GROUP_CONCAT(
        CONCAT('IFNULL(`', char_id, '`, '''')')
        ORDER BY char_id ASC
        SEPARATOR ', '
    )
    INTO @v_json_cols
    FROM (SELECT DISTINCT char_id FROM char_to_pm_column WHERE is_active = 1) t;

    -- Step 2: สร้าง tbl_variant_wide โดย sort value ก่อน concat
    DROP TABLE IF EXISTS tbl_variant_wide;

    SET @v_sql = CONCAT(
        'CREATE TABLE tbl_variant_wide AS ',
        'SELECT `Product ID`, `SKU`, ',
        '    CONCAT(`Product ID`, ''_'', sorted_vals) AS variant_base ',
        'FROM ( ',
        '    SELECT DISTINCT `Product ID`, `SKU`, ',
        '        (SELECT GROUP_CONCAT(val ORDER BY val ASC SEPARATOR ''_'') ',
        '         FROM JSON_TABLE( ',
        '             JSON_ARRAY(', @v_json_cols, '), ',
        '             ''$[*]'' COLUMNS (val TEXT PATH ''$'') ',
        '         ) jt ',
        '         WHERE val IS NOT NULL AND val != '''' ',
        '        ) AS sorted_vals ',
        '    FROM tbl_product_offering_variant_unpivot ',
        ') t ',
        'ORDER BY `Product ID`, variant_base'
    );

    PREPARE stmt FROM @v_sql;
    EXECUTE stmt;
    DEALLOCATE PREPARE stmt;

    -- Step 3: Build dynamic UNION ALL
    SELECT GROUP_CONCAT(
        CONCAT(
            'SELECT DISTINCT v.`Product ID`, v.`SKU`, w.variant_base, ''', char_id, ''' AS char_id, v.`', char_id, '` AS char_value ',
            'FROM tbl_product_offering_variant_unpivot v ',
            'JOIN tbl_variant_wide w ON w.`Product ID` = v.`Product ID` AND w.`SKU` = v.`SKU` ',
            'WHERE v.`', char_id, '` IS NOT NULL'
        )
        SEPARATOR ' UNION ALL '
    )
    INTO @v_unpivot
    FROM (SELECT DISTINCT char_id FROM char_to_pm_column WHERE is_active = 1) t;

    -- Step 4: นับจำนวน row ที่จะ insert เพื่อ reserve sequence
    SET @v_count_sql = CONCAT(
        'SELECT COUNT(*) INTO @v_total_count ',
        'FROM ( ',
        '    SELECT DISTINCT ',
        '        c.`Product ID`, c.`SKU`, c.variant_base, c.char_id, c.char_value ',
        '    FROM (', @v_unpivot, ') c ',
        '    WHERE c.char_value IS NOT NULL ',
        ') sub'
    );

    PREPARE stmt FROM @v_count_sql;
    EXECUTE stmt;
    DEALLOCATE PREPARE stmt;

    START TRANSACTION;

    -- Step 5: Reserve sequence batch
    CALL get_next_sequence_batch(
        'variant', NULL, @v_total_count,
        v_seq_start, v_seq_end, @v_prefix, @v_suffix, v_padding
    );

    -- Step 6: สร้าง result table
    DROP TABLE IF EXISTS tbl_product_offering_variant;
    CREATE TABLE tbl_product_offering_variant (
        `Product Id`                             VARCHAR(500),
        `variantId`                              VARCHAR(500),
        `isAvailable`                            VARCHAR(10),
        `specCharacteristic.Characteristic Id`   VARCHAR(255),
        `specCharacteristic.Characteristic Name` VARCHAR(255),
        `value`                                  TEXT,
        `SKU`                                    VARCHAR(255),
        `created_by`                             VARCHAR(255) DEFAULT 'system',
        `created_at`                             DATETIME(3)  DEFAULT NOW(3),
        INDEX idx_pid  (`Product Id`(255)),
        INDEX idx_sku  (`SKU`),
        INDEX idx_char (`specCharacteristic.Characteristic Id`)
    );

    -- Step 7: Insert พร้อม running no จาก reserved sequence
    SET @v_rn = v_seq_start - 1;

    SET @v_sql = CONCAT(
        'INSERT INTO tbl_product_offering_variant ',
        '(`Product Id`, `variantId`, `isAvailable`, ',
        '`specCharacteristic.Characteristic Id`, ',
        '`specCharacteristic.Characteristic Name`, ',
        '`value`, `SKU`) ',
        'SELECT ',
        '    `Product ID`, ',
        '    CONCAT(',
        '        LOWER(REGEXP_REPLACE(variant_base, ''[^a-zA-Z0-9_-]'', '''')), ',
        '        ''_'', LPAD(@v_rn := @v_rn + 1, ', v_padding, ', ''0'')',
        '    ), ',
        '    ''TRUE'', ',
        '    char_id, ',
        '    `name`, ',
        '    char_value, ',
        '    `SKU` ',
        'FROM ( ',
        '    SELECT DISTINCT ',
        '        c.`Product ID`, ',
        '        c.`SKU`, ',
        '        c.variant_base, ',
        '        c.char_id, ',
        '        sc.`name`, ',
        '        c.char_value ',
        '    FROM (', @v_unpivot, ') c ',
        '    LEFT JOIN spec_characteristics sc ',
        '        ON sc.`Characteristics ID` = c.char_id ',
        ') sub ',
        'ORDER BY `Product ID`, variant_base, char_id'
    );

    PREPARE stmt FROM @v_sql;
    EXECUTE stmt;
    DEALLOCATE PREPARE stmt;

    COMMIT;

    DROP TABLE IF EXISTS tbl_variant_wide;

    -- Step 8: Create View
		DROP VIEW IF EXISTS v_product_offering_variant;
		CREATE VIEW v_product_offering_variant AS
		SELECT
				CAST(`Product Id` AS CHAR)                               AS `Product Id`,
				CAST(`variantId` AS CHAR)                                AS `variantId`,
				CAST(`isAvailable` AS CHAR)                              AS `isAvailable`,
				CAST(`specCharacteristic.Characteristic Id` AS CHAR)     AS `specCharacteristic.Characteristic Id`,
				CAST(`specCharacteristic.Characteristic Name` AS CHAR)   AS `specCharacteristic.Characteristic Name`,
				CAST(`value` AS CHAR)                                    AS `value`,
				CAST(`SKU` AS CHAR)                                      AS `SKU`
		FROM tbl_product_offering_variant;
				
		-- Step 9: Return result
		SELECT * FROM v_product_offering_variant
		ORDER BY `Product Id`, `variantId`;

END$$

DELIMITER ;