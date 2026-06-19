DELIMITER $$

DROP PROCEDURE IF EXISTS fix_all_null_strings$$

CREATE PROCEDURE fix_all_null_strings(
    IN p_tables TEXT      -- ชื่อ table คั่นด้วย comma เช่น 'PRODUCT_MST,stg_product_mst'
                          -- NULL หรือ '' = ทำทุก table ใน schema
)
BEGIN
    DECLARE done    INT  DEFAULT FALSE;
    DECLARE v_sql   TEXT;
    DECLARE v_table VARCHAR(255);
    DECLARE v_col   VARCHAR(255);
    DECLARE v_schema VARCHAR(255);

    DECLARE cur CURSOR FOR
        SELECT TABLE_SCHEMA, TABLE_NAME, COLUMN_NAME
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
          AND IS_NULLABLE  = 'YES'
          AND (
              -- ถ้า p_tables ว่าง/NULL → ทำทุก table
              p_tables IS NULL
              OR TRIM(p_tables) = ''
              -- ถ้าระบุมา → เช็คว่า TABLE_NAME อยู่ใน list
              OR FIND_IN_SET(TABLE_NAME, REPLACE(p_tables, ' ', '')) > 0
          )
        ORDER BY TABLE_NAME, COLUMN_NAME;

    DECLARE CONTINUE HANDLER FOR NOT FOUND SET done = TRUE;

    OPEN cur;

    read_loop: LOOP
        FETCH cur INTO v_schema, v_table, v_col;
        IF done THEN
            LEAVE read_loop;
        END IF;

        SET @s = CONCAT(
            'UPDATE `', v_schema, '`.`', v_table, '` ',
            'SET `', v_col, '` = NULL ',
            'WHERE `', v_col, '` IS NOT NULL ',
            '  AND (CAST(`', v_col, '` AS CHAR) = '''' ',
            '   OR TRIM(LOWER(CAST(`', v_col, '` AS CHAR))) = ''null'')'
        );

        PREPARE stmt FROM @s;
        EXECUTE stmt;
        DEALLOCATE PREPARE stmt;

    END LOOP;

    CLOSE cur;
END$$

DELIMITER ;