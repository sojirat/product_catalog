DELIMITER $$

DROP PROCEDURE IF EXISTS pivot_product_offering_variant$$

CREATE PROCEDURE pivot_product_offering_variant()
BEGIN
    DECLARE col_list TEXT DEFAULT '';
    DECLARE sql_stmt TEXT;

    SET SESSION group_concat_max_len = 1000000;

    -- ดึง Characteristics ID จาก master_characteristics
    SELECT GROUP_CONCAT(
        CONCAT(
            'TRIM(SUBSTRING_INDEX(SUBSTRING_INDEX(value, '','', FIND_IN_SET(''',
            `Characteristics ID`,
            ''', `specCharacteristic.Characteristic Id`)), '','', -1)) AS `', `Characteristics ID`, '`'
        )
        SEPARATOR ', '
    )
    INTO col_list
    FROM master_characteristics;

    SET sql_stmt = CONCAT(
				'CREATE OR REPLACE VIEW vw_pivot_product_offering_variant AS ',
				'SELECT ',
				'CAST(`Product Id` AS CHAR) AS po_id, ',
				'CAST(SKU AS CHAR) AS SKU, ',
				col_list,
				' FROM tbl_product_offering_variant'
		);

    SET @sql = sql_stmt;
    PREPARE stmt FROM @sql;
    EXECUTE stmt;
    DEALLOCATE PREPARE stmt;

		CREATE OR REPLACE VIEW v_product_offering_material_info AS
		SELECT
				'Product Offer Extension'                            AS `BM Entity Type`,
				CAST(po_id AS CHAR)                                  AS `Product Offer ID`,
				'Material Details'                                   AS `Name`,
				'materialInfo'                                       AS `Extension Type`,
				'Residence'                                          AS `marketSegment`,
				'All'                                                AS `Channels`,
				CAST(NULL AS CHAR)                                   AS `Languages`,
				CAST(company AS CHAR)                                AS `company`,
				CAST(SKU AS CHAR)                                    AS `materialCode`,
				CAST(model AS CHAR)                                  AS `charName`,
				CAST(main_model AS CHAR)                             AS `charValue`
		FROM vw_pivot_product_offering_variant;

    SELECT 'View created successfully' AS result;

END$$

DELIMITER ;