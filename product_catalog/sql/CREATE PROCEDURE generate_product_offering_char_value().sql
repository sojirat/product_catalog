DELIMITER $$

DROP PROCEDURE IF EXISTS generate_product_offering_char_value$$

CREATE PROCEDURE generate_product_offering_char_value(
    IN  batch_id   				INT,
    IN  p_created_by    	VARCHAR(255)
)
BEGIN
    DECLARE v_union         TEXT DEFAULT '';
    DECLARE v_char_id       VARCHAR(255);
    DECLARE v_pm_col        VARCHAR(255);
    DECLARE v_src_table     VARCHAR(255);
    DECLARE v_src_cond      TEXT;
    DECLARE v_mm_col        VARCHAR(255);
    DECLARE v_default       VARCHAR(255);
    DECLARE v_done          INT  DEFAULT 0;
    DECLARE v_first         INT  DEFAULT 1;
		DECLARE v_actor      		VARCHAR(255) DEFAULT 'system';

    DECLARE cur_map CURSOR FOR
        SELECT char_id, pm_column, source_table, source_condition, main_model_col, default_value
        FROM char_to_pm_column
        ORDER BY char_id;

    DECLARE CONTINUE HANDLER FOR NOT FOUND SET v_done = 1;

    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        RESIGNAL;
    END;

		SET v_actor = IFNULL(NULLIF(TRIM(p_created_by), ''), 'system');
		
    -- Step 1: Build UNION ALL (ใช้ MAT_CODE เป็น key)
    OPEN cur_map;
    read_map: LOOP
        FETCH cur_map INTO v_char_id, v_pm_col, v_src_table, v_src_cond, v_mm_col, v_default;
        IF v_done THEN LEAVE read_map; END IF;

        IF v_first THEN
            SET v_first = 0;
        ELSE
            SET v_union = CONCAT(v_union, ' UNION ALL ');
        END IF;

        IF v_src_cond IS NULL THEN
            SET v_union = CONCAT(v_union,
                ' SELECT DISTINCT',
                '   src.MAT_CODE,',
                '   ''', v_char_id, ''' AS char_id,',
                IF(v_default IS NOT NULL,
                    CONCAT('   COALESCE(src.`', v_pm_col, '`, ''', v_default, ''') AS char_value'),
                    CONCAT('   src.`', v_pm_col, '` AS char_value')
                ),
                ' FROM ', v_src_table, ' src',
                ' WHERE src.MAT_CODE IS NOT NULL',
                IF(v_default IS NULL, CONCAT(' AND src.`', v_pm_col, '` IS NOT NULL'), '')
            );

        ELSEIF v_mm_col IS NOT NULL THEN
            SET v_union = CONCAT(v_union,
                ' SELECT DISTINCT',
                '   src.MAT_CODE,',
                '   ''', v_char_id, ''' AS char_id,',
                IF(v_default IS NOT NULL,
                    CONCAT('   COALESCE(src.`', v_pm_col, '`, ''', v_default, ''') AS char_value'),
                    CONCAT('   src.`', v_pm_col, '` AS char_value')
                ),
                ' FROM ', v_src_table, ' src',
                ' WHERE src.MAT_CODE IS NOT NULL',
                IF(v_default IS NULL, CONCAT(' AND src.`', v_pm_col, '` IS NOT NULL'), '')
            );

        ELSE
            SET v_union = CONCAT(v_union,
                ' SELECT DISTINCT',
                '   pm_base.MAT_CODE,',
                '   ''', v_char_id, ''' AS char_id,',
                IF(v_default IS NOT NULL,
                    CONCAT('   COALESCE(src.`', v_pm_col, '`, ''', v_default, ''') AS char_value'),
                    CONCAT('   src.`', v_pm_col, '` AS char_value')
                ),
                ' FROM product_catalog.PRODUCT_MST pm_base',
                ' JOIN ', v_src_table, ' src ON ', v_src_cond,
                ' WHERE pm_base.MAT_CODE IS NOT NULL',
                IF(v_default IS NULL, CONCAT(' AND src.`', v_pm_col, '` IS NOT NULL'), '')
            );

        END IF;

    END LOOP;
    CLOSE cur_map;

    -- Step 2: Insert into tmp_pm_vals
    DROP TEMPORARY TABLE IF EXISTS tmp_pm_vals;
    CREATE TEMPORARY TABLE tmp_pm_vals (
        MAT_CODE    VARCHAR(255),
        char_id     VARCHAR(255),
        char_value  TEXT,
        INDEX idx_mc_char (MAT_CODE, char_id)
    );

    SET @v_insert = CONCAT(
        'INSERT INTO tmp_pm_vals (MAT_CODE, char_id, char_value) ',
        v_union
    );
    PREPARE stmt FROM @v_insert;
    EXECUTE stmt;
    DEALLOCATE PREPARE stmt;

    -- Step 3: Normalize MAT_CODE → tmp_po_matcode
    DROP TEMPORARY TABLE IF EXISTS tmp_po_matcode;
    CREATE TEMPORARY TABLE tmp_po_matcode (
        PO_ID       VARCHAR(500),
        MAT_CODE    VARCHAR(255),
        INDEX idx_po_mat (MAT_CODE, PO_ID)
    );

    INSERT INTO tmp_po_matcode (PO_ID, MAT_CODE)
    SELECT
        po.PO_ID,
        TRIM(j.value) AS MAT_CODE
    FROM tbl_product_offering po
    JOIN JSON_TABLE(
        CONCAT('["', REPLACE(REPLACE(po.MAT_CODE, ' ', ''), ',', '","'), '"]'),
        '$[*]' COLUMNS (value VARCHAR(255) PATH '$')
    ) j;

    -- Step 3.5: Split PRODUCT_LINE_TYPE_PAIR → tmp_po_product_line
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

    START TRANSACTION;

    -- Step 4: SELECT
    SELECT DISTINCT
        po.rn                       AS `rn`,
        po.PO_ID                    AS `Char Value.Product Offer ID`,
        pl.PO_PRODUCT_LINE          AS `Char Value.Product Line`,
        pl.PO_PRODUCT_TYPE          AS `Char Value.Product Type`,
        sc.`Spec ID`                AS `Char Value.Product Spec ID`,
        sc.`Characteristics ID`     AS `Char Value.Product Offer Characteristics ID`,
        sc.`name`                   AS `Char Value.Product Offer Characteristics Name`,
        'List'                      AS `Char Value.valueType`,
        clean_name(COALESCE(pmv.char_value, cmap.default_value)) AS `Char Value.value`,
        NULL                        AS `Char Value.Default`
    FROM tbl_product_offering po
    JOIN tmp_po_product_line pl
        ON pl.PO_ID = po.PO_ID
    JOIN product_type_mapping ptm
        ON  ptm.PRODUCT_TYPE     = pl.PO_PRODUCT_LINE
        AND ptm.PRODUCT_SUB_TYPE = pl.PO_PRODUCT_TYPE
    JOIN (
        SELECT ptm2.PRODUCT_TYPE, ptm2.PRODUCT_SUB_TYPE,
               sc2.`Spec ID`, sc2.`Characteristics ID`, sc2.`name`
        FROM product_type_mapping ptm2
        JOIN spec_characteristics sc2
            ON sc2.`Spec ID` = ptm2.PRODUCT_SPECIFICATION
        UNION ALL
        SELECT ptm2.PRODUCT_TYPE, ptm2.PRODUCT_SUB_TYPE,
               sc2.`Spec ID`, sc2.`Characteristics ID`, sc2.`name`
        FROM product_type_mapping ptm2
        JOIN spec_characteristics sc2
            ON sc2.`Spec ID` = ptm2.RESOURCE_SPECIFICATION
        WHERE ptm2.RESOURCE_SPECIFICATION IS NOT NULL
    ) sc
        ON  sc.PRODUCT_TYPE     = pl.PO_PRODUCT_LINE
        AND sc.PRODUCT_SUB_TYPE = pl.PO_PRODUCT_TYPE
    JOIN char_to_pm_column cmap
        ON  cmap.char_id = sc.`Characteristics ID`
    JOIN tmp_po_matcode pm_map
        ON  pm_map.PO_ID = po.PO_ID
    LEFT JOIN tmp_pm_vals pmv 
        ON  pmv.MAT_CODE = pm_map.MAT_CODE
        AND pmv.char_id  = sc.`Characteristics ID`
    WHERE clean_name(COALESCE(pmv.char_value, cmap.default_value)) IS NOT NULL
    ORDER BY
        po.rn,
        pl.PO_PRODUCT_LINE,
        sc.`Characteristics ID`,
        clean_name(COALESCE(pmv.char_value, cmap.default_value));

    -- Step 5a: Sync ค่าใหม่เข้า characteristics_value
    IF NOT EXISTS (
        SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
        WHERE  TABLE_SCHEMA = DATABASE()
          AND  TABLE_NAME   = 'characteristics_value'
          AND  COLUMN_NAME  = 'batch_id_insert'
    ) THEN
        ALTER TABLE characteristics_value ADD COLUMN batch_id_insert INT DEFAULT NULL;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
        WHERE  TABLE_SCHEMA = DATABASE()
          AND  TABLE_NAME   = 'characteristics_value'
          AND  COLUMN_NAME  = 'batch_id_update'
    ) THEN
        ALTER TABLE characteristics_value ADD COLUMN batch_id_update INT DEFAULT NULL;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
        WHERE  TABLE_SCHEMA = DATABASE()
          AND  TABLE_NAME   = 'characteristics_value'
          AND  COLUMN_NAME  = 'created_by'
    ) THEN
        ALTER TABLE characteristics_value ADD COLUMN created_by VARCHAR(255) DEFAULT NULL;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
        WHERE  TABLE_SCHEMA = DATABASE()
          AND  TABLE_NAME   = 'characteristics_value'
          AND  COLUMN_NAME  = 'created_at'
    ) THEN
        ALTER TABLE characteristics_value ADD COLUMN created_at DATETIME(3) DEFAULT NULL;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
        WHERE  TABLE_SCHEMA = DATABASE()
          AND  TABLE_NAME   = 'characteristics_value'
          AND  COLUMN_NAME  = 'updated_by'
    ) THEN
        ALTER TABLE characteristics_value ADD COLUMN updated_by VARCHAR(255) DEFAULT NULL;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
        WHERE  TABLE_SCHEMA = DATABASE()
          AND  TABLE_NAME   = 'characteristics_value'
          AND  COLUMN_NAME  = 'updated_at'
    ) THEN
        ALTER TABLE characteristics_value ADD COLUMN updated_at DATETIME(3) DEFAULT NULL;
    END IF;
		
    INSERT INTO characteristics_value (
        `Spec ID`,
        `Characteristics ID`,
        `Resource Spec Charactristics Name`,
        `valueType`,
        `value`,
        `isDefault`,
				`batch_id_insert`,
				`created_by`,
				`created_at`
    )
    SELECT DISTINCT
        sc.`Spec ID`,
        sc.`Characteristics ID`,
        sc.`name`,
        'List',
        clean_name(COALESCE(pmv.char_value, cmap.default_value)),
        NULL,
				batch_id,
				v_actor,
				NOW(3)
    FROM tbl_product_offering po
    JOIN tmp_po_product_line pl
        ON pl.PO_ID = po.PO_ID
    JOIN product_type_mapping ptm
        ON  ptm.PRODUCT_TYPE     = pl.PO_PRODUCT_LINE
        AND ptm.PRODUCT_SUB_TYPE = pl.PO_PRODUCT_TYPE
    JOIN (
        SELECT ptm2.PRODUCT_TYPE, ptm2.PRODUCT_SUB_TYPE,
               sc2.`Spec ID`, sc2.`Characteristics ID`, sc2.`name`
        FROM product_type_mapping ptm2
        JOIN spec_characteristics sc2
            ON sc2.`Spec ID` = ptm2.PRODUCT_SPECIFICATION
        UNION ALL
        SELECT ptm2.PRODUCT_TYPE, ptm2.PRODUCT_SUB_TYPE,
               sc2.`Spec ID`, sc2.`Characteristics ID`, sc2.`name`
        FROM product_type_mapping ptm2
        JOIN spec_characteristics sc2
            ON sc2.`Spec ID` = ptm2.RESOURCE_SPECIFICATION
        WHERE ptm2.RESOURCE_SPECIFICATION IS NOT NULL
    ) sc
        ON  sc.PRODUCT_TYPE     = pl.PO_PRODUCT_LINE
        AND sc.PRODUCT_SUB_TYPE = pl.PO_PRODUCT_TYPE
    JOIN char_to_pm_column cmap
        ON  cmap.char_id = sc.`Characteristics ID`
    JOIN tmp_po_matcode pm_map
        ON  pm_map.PO_ID = po.PO_ID
    LEFT JOIN tmp_pm_vals pmv
        ON  pmv.MAT_CODE = pm_map.MAT_CODE
        AND pmv.char_id  = sc.`Characteristics ID`
    WHERE COALESCE(pmv.char_value, cmap.default_value) IS NOT NULL
      AND NOT EXISTS (
          SELECT 1
          FROM characteristics_value cv
          WHERE cv.`Characteristics ID` = sc.`Characteristics ID`
            AND cv.`value`              = clean_name(COALESCE(pmv.char_value, cmap.default_value))
      );

		-- Step 5b: Sync ค่าใหม่เข้า char_value
		IF NOT EXISTS (
				SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
				WHERE  TABLE_SCHEMA = DATABASE()
					AND  TABLE_NAME   = 'char_value'
					AND  COLUMN_NAME  = 'batch_id_insert'
		) THEN
				ALTER TABLE char_value ADD COLUMN batch_id_insert INT DEFAULT NULL;
		END IF;

		IF NOT EXISTS (
				SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
				WHERE  TABLE_SCHEMA = DATABASE()
					AND  TABLE_NAME   = 'char_value'
					AND  COLUMN_NAME  = 'batch_id_update'
		) THEN
				ALTER TABLE char_value ADD COLUMN batch_id_update INT DEFAULT NULL;
		END IF;

		IF NOT EXISTS (
				SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
				WHERE  TABLE_SCHEMA = DATABASE()
					AND  TABLE_NAME   = 'char_value'
					AND  COLUMN_NAME  = 'created_by'
		) THEN
				ALTER TABLE char_value ADD COLUMN created_by VARCHAR(255) DEFAULT NULL;
		END IF;

		IF NOT EXISTS (
				SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
				WHERE  TABLE_SCHEMA = DATABASE()
					AND  TABLE_NAME   = 'char_value'
					AND  COLUMN_NAME  = 'created_at'
		) THEN
				ALTER TABLE char_value ADD COLUMN created_at DATETIME(3) DEFAULT NULL;
		END IF;

		IF NOT EXISTS (
				SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
				WHERE  TABLE_SCHEMA = DATABASE()
					AND  TABLE_NAME   = 'char_value'
					AND  COLUMN_NAME  = 'updated_by'
		) THEN
				ALTER TABLE char_value ADD COLUMN updated_by VARCHAR(255) DEFAULT NULL;
		END IF;

		IF NOT EXISTS (
				SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
				WHERE  TABLE_SCHEMA = DATABASE()
					AND  TABLE_NAME   = 'char_value'
					AND  COLUMN_NAME  = 'updated_at'
		) THEN
				ALTER TABLE char_value ADD COLUMN updated_at DATETIME(3) DEFAULT NULL;
		END IF;
		
		INSERT INTO char_value (
				`OLD_PS_ID`,
				`Spec ID`,
				`Characteristics ID`,
				`Product Spec Charactristics Name`,
				`valueType`,
				`value`,
				`isDefault`,
				`batch_id_insert`,
				`created_by`,
				`created_at`
		)
		SELECT DISTINCT
				ps.OLD_ID           AS OLD_PS_ID,
				sc.`Spec ID`,
				sc.`Characteristics ID`,
				sc.`name`,
				'List',
				clean_name(COALESCE(pmv.char_value, cmap.default_value)),
				NULL,
				batch_id,
				v_actor,
				NOW(3)
		FROM tbl_product_offering po
		JOIN tmp_po_product_line pl
				ON pl.PO_ID = po.PO_ID
		JOIN product_type_mapping ptm
				ON  ptm.PRODUCT_TYPE     = pl.PO_PRODUCT_LINE
				AND ptm.PRODUCT_SUB_TYPE = pl.PO_PRODUCT_TYPE
		JOIN (
				SELECT ptm2.PRODUCT_TYPE, ptm2.PRODUCT_SUB_TYPE,
							 sc2.`Spec ID`, sc2.`Characteristics ID`, sc2.`name`
				FROM product_type_mapping ptm2
				JOIN spec_characteristics sc2
						ON sc2.`Spec ID` = ptm2.PRODUCT_SPECIFICATION
				UNION ALL
				SELECT ptm2.PRODUCT_TYPE, ptm2.PRODUCT_SUB_TYPE,
							 sc2.`Spec ID`, sc2.`Characteristics ID`, sc2.`name`
				FROM product_type_mapping ptm2
				JOIN spec_characteristics sc2
						ON sc2.`Spec ID` = ptm2.RESOURCE_SPECIFICATION
				WHERE ptm2.RESOURCE_SPECIFICATION IS NOT NULL
		) sc
				ON  sc.PRODUCT_TYPE     = pl.PO_PRODUCT_LINE
				AND sc.PRODUCT_SUB_TYPE = pl.PO_PRODUCT_TYPE
		JOIN product_specification ps
				ON  ps.`Spec ID` = sc.`Spec ID`
		JOIN char_to_pm_column cmap
				ON  cmap.char_id = sc.`Characteristics ID`
		JOIN tmp_po_matcode pm_map
				ON  pm_map.PO_ID = po.PO_ID
		LEFT JOIN tmp_pm_vals pmv
				ON  pmv.MAT_CODE = pm_map.MAT_CODE
				AND pmv.char_id  = sc.`Characteristics ID`
		WHERE COALESCE(pmv.char_value, cmap.default_value) IS NOT NULL
			AND NOT EXISTS (
					SELECT 1
					FROM char_value cv
					WHERE cv.`Characteristics ID` = sc.`Characteristics ID`
						AND cv.`value`              = clean_name(COALESCE(pmv.char_value, cmap.default_value))
			);

    -- Step 6: Save snapshot (upsert แทน drop+create)
    CREATE TABLE IF NOT EXISTS tbl_product_offering_char_value (
        `rn`                                            INT,
        `Char Value.Product Offer ID`                   VARCHAR(500),
        `Char Value.Product Line`                       VARCHAR(255),
        `Char Value.Product Type`                       VARCHAR(255),
        `Char Value.Product Spec ID`                    VARCHAR(255),
        `Char Value.Product Offer Characteristics ID`   VARCHAR(255),
        `Char Value.Product Offer Characteristics Name` VARCHAR(255),
        `Char Value.valueType`                          VARCHAR(50),
        `Char Value.value`                              TEXT,
        `Char Value.Default`                            TEXT,
				`batch_id_insert`     													INT,
				`batch_id_update`     													INT,
        `created_by`                                    VARCHAR(255) DEFAULT 'system',
        `created_at`                                    DATETIME(3)  DEFAULT NOW(3),
        `updated_by`                                    VARCHAR(255) DEFAULT NULL,
        `updated_at`                                    DATETIME(3)  DEFAULT NULL,
        INDEX idx_snap_po   (`Char Value.Product Offer ID`(255)),
        INDEX idx_snap_char (`Char Value.Product Offer Characteristics ID`(255))
    );

    -- Step 6a: Update rows ที่มีอยู่แล้ว
    UPDATE tbl_product_offering_char_value t
    JOIN (
        SELECT DISTINCT
            po.rn,
            po.PO_ID,
            pl.PO_PRODUCT_LINE,
            pl.PO_PRODUCT_TYPE,
            sc.`Spec ID`,
            sc.`Characteristics ID`,
            sc.`name`,
            clean_name(COALESCE(pmv.char_value, cmap.default_value)) AS char_value,
            cv.isDefault
        FROM tbl_product_offering po
        JOIN tmp_po_product_line pl
            ON pl.PO_ID = po.PO_ID
        JOIN product_type_mapping ptm
            ON  ptm.PRODUCT_TYPE     = pl.PO_PRODUCT_LINE
            AND ptm.PRODUCT_SUB_TYPE = pl.PO_PRODUCT_TYPE
        JOIN (
            SELECT ptm2.PRODUCT_TYPE, ptm2.PRODUCT_SUB_TYPE,
                   sc2.`Spec ID`, sc2.`Characteristics ID`, sc2.`name`
            FROM product_type_mapping ptm2
            JOIN spec_characteristics sc2
                ON sc2.`Spec ID` = ptm2.PRODUCT_SPECIFICATION
            UNION ALL
            SELECT ptm2.PRODUCT_TYPE, ptm2.PRODUCT_SUB_TYPE,
                   sc2.`Spec ID`, sc2.`Characteristics ID`, sc2.`name`
            FROM product_type_mapping ptm2
            JOIN spec_characteristics sc2
                ON sc2.`Spec ID` = ptm2.RESOURCE_SPECIFICATION
            WHERE ptm2.RESOURCE_SPECIFICATION IS NOT NULL
        ) sc
            ON  sc.PRODUCT_TYPE     = pl.PO_PRODUCT_LINE
            AND sc.PRODUCT_SUB_TYPE = pl.PO_PRODUCT_TYPE
        JOIN char_to_pm_column cmap
            ON  cmap.char_id = sc.`Characteristics ID`
        JOIN tmp_po_matcode pm_map
            ON  pm_map.PO_ID = po.PO_ID
        LEFT JOIN tmp_pm_vals pmv
            ON  pmv.MAT_CODE = pm_map.MAT_CODE
            AND pmv.char_id  = sc.`Characteristics ID`
        LEFT JOIN characteristics_value cv
            ON  cv.`Spec ID`            = sc.`Spec ID`
            AND cv.`Characteristics ID` = sc.`Characteristics ID`
            AND cv.`value`              = clean_name(COALESCE(pmv.char_value, cmap.default_value))
        WHERE clean_name(COALESCE(pmv.char_value, cmap.default_value)) IS NOT NULL
    ) src
        ON  t.`Char Value.Product Offer ID`                 = src.PO_ID
        AND t.`Char Value.Product Offer Characteristics ID` = src.`Characteristics ID`
        AND t.`Char Value.Product Spec ID`                  = src.`Spec ID`
    SET
        t.`rn`                                            = src.rn,
        t.`Char Value.Product Line`                       = src.PO_PRODUCT_LINE,
        t.`Char Value.Product Type`                       = src.PO_PRODUCT_TYPE,
        t.`Char Value.Product Offer Characteristics Name` = src.`name`,
        t.`Char Value.valueType`                          = 'List',
        t.`Char Value.value`                              = src.char_value,
        t.`Char Value.Default`                            = src.isDefault,
				t.`batch_id_update`                               = batch_id,
        t.`updated_by`                                    = v_actor,
        t.`updated_at`                                    = NOW(3);

    -- Step 6b: Insert rows ใหม่ที่ยังไม่มี
    INSERT INTO tbl_product_offering_char_value (
        `rn`,
        `Char Value.Product Offer ID`,
        `Char Value.Product Line`,
        `Char Value.Product Type`,
        `Char Value.Product Spec ID`,
        `Char Value.Product Offer Characteristics ID`,
        `Char Value.Product Offer Characteristics Name`,
        `Char Value.valueType`,
        `Char Value.value`,
        `Char Value.Default`,
				`batch_id_insert`,
        `created_by`,
        `created_at`
    )
    SELECT DISTINCT
        po.rn,
        po.PO_ID,
        pl.PO_PRODUCT_LINE,
        pl.PO_PRODUCT_TYPE,
        sc.`Spec ID`,
        sc.`Characteristics ID`,
        sc.`name`,
        'List',
        clean_name(COALESCE(pmv.char_value, cmap.default_value)),
        cv.isDefault,
				batch_id,
        v_actor,
        NOW(3)
    FROM tbl_product_offering po
    JOIN tmp_po_product_line pl
        ON pl.PO_ID = po.PO_ID
    JOIN product_type_mapping ptm
        ON  ptm.PRODUCT_TYPE     = pl.PO_PRODUCT_LINE
        AND ptm.PRODUCT_SUB_TYPE = pl.PO_PRODUCT_TYPE
    JOIN (
        SELECT ptm2.PRODUCT_TYPE, ptm2.PRODUCT_SUB_TYPE,
               sc2.`Spec ID`, sc2.`Characteristics ID`, sc2.`name`
        FROM product_type_mapping ptm2
        JOIN spec_characteristics sc2
            ON sc2.`Spec ID` = ptm2.PRODUCT_SPECIFICATION
        UNION ALL
        SELECT ptm2.PRODUCT_TYPE, ptm2.PRODUCT_SUB_TYPE,
               sc2.`Spec ID`, sc2.`Characteristics ID`, sc2.`name`
        FROM product_type_mapping ptm2
        JOIN spec_characteristics sc2
            ON sc2.`Spec ID` = ptm2.RESOURCE_SPECIFICATION
        WHERE ptm2.RESOURCE_SPECIFICATION IS NOT NULL
    ) sc
        ON  sc.PRODUCT_TYPE     = pl.PO_PRODUCT_LINE
        AND sc.PRODUCT_SUB_TYPE = pl.PO_PRODUCT_TYPE
    JOIN char_to_pm_column cmap
        ON  cmap.char_id = sc.`Characteristics ID`
    JOIN tmp_po_matcode pm_map
        ON  pm_map.PO_ID = po.PO_ID
    LEFT JOIN tmp_pm_vals pmv
        ON  pmv.MAT_CODE = pm_map.MAT_CODE
        AND pmv.char_id  = sc.`Characteristics ID`
    LEFT JOIN characteristics_value cv
        ON  cv.`Spec ID`            = sc.`Spec ID`
        AND cv.`Characteristics ID` = sc.`Characteristics ID`
        AND cv.`value`              = clean_name(COALESCE(pmv.char_value, cmap.default_value))
    WHERE clean_name(COALESCE(pmv.char_value, cmap.default_value)) IS NOT NULL
      AND NOT EXISTS (
          SELECT 1
          FROM tbl_product_offering_char_value e
          WHERE e.`Char Value.Product Offer ID`                 = po.PO_ID
            AND e.`Char Value.Product Offer Characteristics ID` = sc.`Characteristics ID`
            AND e.`Char Value.Product Spec ID`                  = sc.`Spec ID`
      )
    ORDER BY
        po.rn,
        pl.PO_PRODUCT_LINE,
        sc.`Characteristics ID`;

   CREATE OR REPLACE VIEW v_product_offering_char_value AS
		SELECT
				CAST(pocv.`Char Value.Product Offer ID` AS CHAR)                         AS `Char Value.Product Offer ID`,
				CAST(pocv.`Char Value.Product Spec ID` AS CHAR)                          AS `Char Value.Product Spec ID`,
				CAST(ps.`name` AS CHAR)                        													 AS `Char Value.Product Spec Name`,
				CAST(pocv.`Char Value.Product Offer Characteristics ID` AS CHAR)         AS `Char Value.Product Offer Characteristics ID`,
				CAST(pocv.`Char Value.Product Offer Characteristics Name` AS CHAR)       AS `Char Value.Product Offer Characteristics Name`,
				CAST(pocv.`Char Value.valueType` AS CHAR)                                AS `Char Value.valueType`,
				CAST(pocv.`Char Value.value` AS CHAR)                                    AS `Char Value.value`,
				CAST(pocv.`Char Value.Default` AS CHAR)                                  AS `Char Value.isDefault`
		FROM tbl_product_offering_char_value pocv
		JOIN product_specification ps ON ps.`Spec ID` = pocv.`Char Value.Product Spec ID`
		ORDER BY pocv.`rn`;
		
		CREATE OR REPLACE VIEW v_product_offering_meta_extension_material_info AS
		SELECT
				'Product Offer Extension'                                              AS `BM Entity Type`,
				CAST(t.`Char Value.Product Offer ID` AS CHAR)                          AS `Product Offer ID`,
				'Material Details'                                                     AS `Name`,
				'materialInfo'                                                         AS `Extension Type`,
				'Residence'                                                            AS `marketSegment`,
				'All'                                                                  AS `Channels`,
				CAST(NULL AS CHAR)                                                     AS `Languages`,
				CAST(c.company AS CHAR)                                                AS `company`,
				CAST(m.mat_code AS CHAR)                                               AS `materialCode`,
				CAST(t.`Char Value.Product Offer Characteristics ID` AS CHAR)          AS `charName`,
				CAST(t.`Char Value.value` AS CHAR)                                     AS `charValue`
		FROM tbl_product_offering_char_value t
		LEFT JOIN (
				SELECT
						`Char Value.Product Offer ID`,
						`Char Value.value` AS company
				FROM tbl_product_offering_char_value
				WHERE `Char Value.Product Offer Characteristics ID` = 'company-mh_mg00551'
		) c
				ON t.`Char Value.Product Offer ID` = c.`Char Value.Product Offer ID`
		LEFT JOIN (
				SELECT
						`Char Value.Product Offer ID`,
						`Char Value.value` AS mat_code
				FROM tbl_product_offering_char_value
				WHERE `Char Value.Product Offer Characteristics ID` = 'mat_code-mh_mg00120'
		) m
				ON t.`Char Value.Product Offer ID` = m.`Char Value.Product Offer ID`
		WHERE t.`Char Value.Product Offer Characteristics ID`
				NOT IN ('company-mh_mg00551', 'mat_code-mh_mg00120')
		ORDER BY t.rn;

    COMMIT;

    DROP TEMPORARY TABLE IF EXISTS tmp_pm_vals;
    DROP TEMPORARY TABLE IF EXISTS tmp_po_matcode;
    DROP TEMPORARY TABLE IF EXISTS tmp_po_product_line;

END$$

DELIMITER;