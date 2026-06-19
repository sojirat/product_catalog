DELIMITER $$

DROP PROCEDURE IF EXISTS generate_product_offering_variant_unpivot$$
CREATE PROCEDURE generate_product_offering_variant_unpivot()
BEGIN
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        RESIGNAL;
    END;
    SET SESSION group_concat_max_len = 1000000;

    -- Step 1: Normalize MAT_CODE → tmp_po_matcode
    DROP TEMPORARY TABLE IF EXISTS tmp_po_matcode;
    CREATE TEMPORARY TABLE tmp_po_matcode (
        PO_ID    VARCHAR(500) NOT NULL,
        MAT_CODE VARCHAR(255) NOT NULL,
        PRIMARY KEY (PO_ID, MAT_CODE),
        INDEX idx_mat (MAT_CODE)
    );
    INSERT IGNORE INTO tmp_po_matcode (PO_ID, MAT_CODE)
    SELECT po.PO_ID,
           TRIM(j.value) AS MAT_CODE
    FROM tbl_product_offering po
    JOIN JSON_TABLE(
        CONCAT('["', REPLACE(TRIM(po.MAT_CODE), ',', '","'), '"]'),
        '$[*]' COLUMNS (value VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci PATH '$')
    ) j
    WHERE TRIM(j.value) <> '';

    -- Step 1.5: Split PRODUCT_LINE_TYPE_PAIR → tmp_po_product_line
    DROP TEMPORARY TABLE IF EXISTS tmp_po_product_line;
    CREATE TEMPORARY TABLE tmp_po_product_line (
        PO_ID            VARCHAR(500) NOT NULL,
        PO_PRODUCT_LINE  VARCHAR(255) NOT NULL,
        PO_PRODUCT_TYPE  VARCHAR(255) NOT NULL,
        INDEX idx_po_id (PO_ID)
    );
    INSERT INTO tmp_po_product_line (PO_ID, PO_PRODUCT_LINE, PO_PRODUCT_TYPE)
    WITH RECURSIVE num AS (
        SELECT 1 AS n
        UNION ALL
        SELECT n + 1
        FROM num
        WHERE n < (
            SELECT MAX(LENGTH(PRODUCT_LINE_TYPE_PAIR) - LENGTH(REPLACE(PRODUCT_LINE_TYPE_PAIR, ',', '')) + 1)
            FROM tbl_product_offering
        )
    )
    SELECT
        po.PO_ID,
        TRIM(SUBSTRING_INDEX(SUBSTRING_INDEX(po.PRODUCT_LINE_TYPE_PAIR, ',', n.n), '|', 1))  AS PO_PRODUCT_LINE,
        TRIM(SUBSTRING_INDEX(SUBSTRING_INDEX(po.PRODUCT_LINE_TYPE_PAIR, ',', n.n), '|', -1)) AS PO_PRODUCT_TYPE
    FROM tbl_product_offering po
    JOIN num n ON n.n <= (LENGTH(po.PRODUCT_LINE_TYPE_PAIR) - LENGTH(REPLACE(po.PRODUCT_LINE_TYPE_PAIR, ',', '')) + 1);

    -- Step 2: Pre-join PRODUCT_MST → tmp_po_pm
    DROP TEMPORARY TABLE IF EXISTS tmp_po_pm;
    CREATE TEMPORARY TABLE tmp_po_pm AS
    SELECT 
        po.rn,
        mc.PO_ID,
        pm.MAT_CODE,
        pm.PRODUCT_ID,
        pl.PO_PRODUCT_LINE,
        pl.PO_PRODUCT_TYPE
    FROM tmp_po_matcode mc
    JOIN tbl_product_offering po
        ON po.PO_ID = mc.PO_ID
    JOIN product_catalog.PRODUCT_MST pm 
        ON pm.MAT_CODE COLLATE utf8mb4_general_ci = mc.MAT_CODE COLLATE utf8mb4_general_ci
    JOIN tmp_po_product_line pl
        ON pl.PO_ID = mc.PO_ID;

    -- Step 3: Build dynamic SELECT columns
    SELECT GROUP_CONCAT(
				CASE 
						WHEN char_id = 'price_group' THEN
								CONCAT(
										'COALESCE(MIN(`src_', char_id, '`.`', pm_column, '`), ',
										CASE WHEN default_value IS NOT NULL THEN CONCAT('''', default_value, '''') ELSE '''EUP''' END,
										') AS `', char_id, '`, ',
										'CASE WHEN MIN(`src_', char_id, '`.`', pm_column, '`) IS NULL THEN 1 ELSE 0 END AS `', char_id, '_is_default`'
								)
						WHEN default_value IS NOT NULL THEN
								CONCAT('COALESCE(MIN(`src_', char_id, '`.`', pm_column, '`), ''', default_value, ''') AS `', char_id, '`')
						ELSE
								CONCAT('MIN(`src_', char_id, '`.`', pm_column, '`) AS `', char_id, '`')
				END
				ORDER BY char_id
				SEPARATOR ', '
		)
		INTO @v_cols
		FROM char_to_pm_column
		WHERE is_active = 1;

    -- Step 4: Build dynamic LEFT JOINs
    SELECT GROUP_CONCAT(
				CASE
						WHEN source_table = 'product_catalog.PRICE_MST' THEN
								CONCAT(
										' LEFT JOIN product_catalog.PRICE_MST `src_', char_id, '`',
										' ON `src_', char_id, '`.PRODUCT_ID COLLATE utf8mb4_general_ci = base.PRODUCT_ID COLLATE utf8mb4_general_ci',
										CASE
												WHEN where_condition IS NOT NULL AND where_condition != ''
												THEN CONCAT(' AND ', where_condition)
												ELSE ''
										END
								)
						ELSE
								CONCAT(
										' LEFT JOIN product_catalog.PRODUCT_MST `src_', char_id, '`',
										' ON `src_', char_id, '`.MAT_CODE COLLATE utf8mb4_general_ci = base.MAT_CODE COLLATE utf8mb4_general_ci',
										CASE 
												WHEN main_model_col IS NOT NULL AND main_model_col != '' 
												THEN CONCAT(' AND `src_', char_id, '`.`', main_model_col, '` IS NOT NULL')
												ELSE ''
										END,
										CASE
												WHEN where_condition IS NOT NULL AND where_condition != ''
												THEN CONCAT(' AND ', where_condition)
												ELSE ''
										END
								)
				END
				SEPARATOR ' '
		)
		INTO @v_joins
		FROM char_to_pm_column
		WHERE is_active = 1;

    -- Step 5: Create output table
    DROP TABLE IF EXISTS tbl_product_offering_variant_unpivot;
    SET @v_sql = CONCAT(
        'CREATE TABLE tbl_product_offering_variant_unpivot AS ',
        'SELECT ',
        '    base.rn              AS `rn`, ',
        '    base.PO_ID           AS `Product ID`, ',
        '    base.MAT_CODE        AS `SKU`, ',
        '    base.PO_PRODUCT_LINE AS `po_product_line`, ',
        '    base.PO_PRODUCT_TYPE AS `po_product_type`, ',
        @v_cols,
        ' FROM tmp_po_pm base ',
        @v_joins,
        ' GROUP BY base.rn, base.PO_ID, base.MAT_CODE, base.PO_PRODUCT_LINE, base.PO_PRODUCT_TYPE',
        ' ORDER BY base.rn, base.MAT_CODE, base.PO_PRODUCT_LINE'
    );
    PREPARE stmt FROM @v_sql;
    EXECUTE stmt;
    DEALLOCATE PREPARE stmt;

    -- Step 6: Add index
    ALTER TABLE tbl_product_offering_variant_unpivot
        ADD INDEX idx_rn           (`rn`),
        ADD INDEX idx_product_id   (`Product ID`),
        ADD INDEX idx_sku          (`SKU`),
        ADD INDEX idx_product_line (`po_product_line`);

    DROP TEMPORARY TABLE IF EXISTS tmp_po_matcode;
    DROP TEMPORARY TABLE IF EXISTS tmp_po_pm;
    DROP TEMPORARY TABLE IF EXISTS tmp_po_product_line;

    SELECT * FROM tbl_product_offering_variant_unpivot
    ORDER BY `rn`, `SKU`, `po_product_line`;
END$$
DELIMITER ;