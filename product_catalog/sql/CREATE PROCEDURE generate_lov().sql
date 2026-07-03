DELIMITER $$

DROP PROCEDURE IF EXISTS generate_lov$$

CREATE PROCEDURE generate_lov()
BEGIN
    DECLARE done_tpl  BOOL DEFAULT FALSE;
    DECLARE done_map  BOOL DEFAULT FALSE;
 
    DECLARE v_template    VARCHAR(255);
    DECLARE v_table       VARCHAR(255);
    DECLARE v_column      VARCHAR(255);
    DECLARE v_view_name   VARCHAR(255);
    DECLARE v_sql         LONGTEXT;
    DECLARE v_ddl         LONGTEXT;
 
    /* ------------------------------------------------------------------ */
    /* Cursor 1 : distinct templates                                        */
    /* ------------------------------------------------------------------ */
    DECLARE cur_tpl CURSOR FOR
        SELECT DISTINCT `AIS Template Excel File`
        FROM list_of_value_mapping
        WHERE `AIS Template Excel File` IS NOT NULL
          AND TRIM(`AIS Template Excel File`) <> '' COLLATE utf8mb4_general_ci
        ORDER BY `AIS Template Excel File`;
 
    DECLARE CONTINUE HANDLER FOR NOT FOUND SET done_tpl = TRUE;
 
    OPEN cur_tpl;
 
    tpl_loop: LOOP
        FETCH cur_tpl INTO v_template;
        IF done_tpl THEN LEAVE tpl_loop; END IF;
 
        /* ----------------------------------------------------------------
           Build view name: "v_lov_" + template
           Replace characters that are invalid in identifiers with "_"
           (spaces, /, \, ., -, etc.)
        ---------------------------------------------------------------- */
        SET v_view_name = CONCAT(
            'v_lov_',
            clean_to_snake_case(v_template)
        );
 
        /* strip trailing underscore if any */
        IF RIGHT(v_view_name, 1) = '_' THEN
            SET v_view_name = LEFT(v_view_name, LENGTH(v_view_name) - 1);
        END IF;
 
        SET done_map = FALSE;
        SET v_sql    = '';
 
        /* -------------------------------------------------------------- */
        /* Cursor 2 : columns mapped to this template                      */
        /* -------------------------------------------------------------- */
        BEGIN
            DECLARE cur_map CURSOR FOR
                SELECT `DATABASE NAME`, `COLUMN NAME`
                FROM list_of_value_mapping
                WHERE `AIS Template Excel File` = v_template;
 
            DECLARE CONTINUE HANDLER FOR NOT FOUND SET done_map = TRUE;
 
            OPEN cur_map;
 
            map_loop: LOOP
                FETCH cur_map INTO v_table, v_column;
                IF done_map THEN LEAVE map_loop; END IF;
 
                /* Verify table and column actually exist */
                IF EXISTS (
                    SELECT 1 FROM information_schema.tables
                    WHERE table_schema = DATABASE()
                      AND table_name   = v_table
                )
                AND EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema = DATABASE()
                      AND table_name   = v_table
                      AND column_name  = v_column
                ) THEN
 
                    IF v_sql <> '' COLLATE utf8mb4_general_ci THEN
                        SET v_sql = CONCAT(v_sql, '\n    UNION ALL\n    ');
                    END IF;
 
                    SET v_sql = CONCAT(
                        v_sql,
                        'SELECT DISTINCT\n',
                        '        ''', REPLACE(v_column, '''', ''''''), ''' AS lovName,\n',
                        '        TRIM(`', REPLACE(v_column, '`', '``'), '`) COLLATE utf8mb4_general_ci AS lovValue\n',
                        '    FROM `', REPLACE(v_table, '`', '``'), '`\n',
                        '    WHERE `', REPLACE(v_column, '`', '``'), '` IS NOT NULL\n',
                        '      AND TRIM(`', REPLACE(v_column, '`', '``'), '`) COLLATE utf8mb4_general_ci <> '''''
                    );
 
                END IF;
            END LOOP;
 
            CLOSE cur_map;
        END;
        /* -------------------------------------------------------------- */
 
        IF v_sql <> '' COLLATE utf8mb4_general_ci THEN
            /* DROP existing view first, then CREATE */
            SET @drop_view = CONCAT('DROP VIEW IF EXISTS `', v_view_name, '`');
            PREPARE s FROM @drop_view;
            EXECUTE s;
            DEALLOCATE PREPARE s;
 
            SET v_ddl = CONCAT(
                'CREATE VIEW `', v_view_name, '` AS\n',
                '    ', v_sql, '\n',
                '    ORDER BY lovName, lovValue'
            );
 
            SET @create_view = v_ddl;
            PREPARE s FROM @create_view;
            EXECUTE s;
            DEALLOCATE PREPARE s;
 
            /* Optional: show which view was just created */
            SELECT CONCAT('✔ Created view: ', v_view_name) AS status;
        ELSE
            SELECT CONCAT('⚠ Skipped (no valid columns found): ', v_template) AS status;
        END IF;
 
    END LOOP;
 
    CLOSE cur_tpl;
END$$
 
DELIMITER ;