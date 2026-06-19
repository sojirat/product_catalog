DELIMITER $$

DROP PROCEDURE IF EXISTS mch_sap_org_build_hierarchy$$

CREATE PROCEDURE mch_sap_org_build_hierarchy()
BEGIN
    -- หลีกเลี่ยง lock timeout
    SET SESSION innodb_lock_wait_timeout = 5;

    -- สร้าง table ครั้งแรกครั้งเดียว
    CREATE TABLE IF NOT EXISTS MCH_HIERARCHY (
        level              CHAR(1)       NOT NULL,
        code               VARCHAR(255)   NOT NULL,
        name               VARCHAR(255),
        parent_code        VARCHAR(50),
        status             VARCHAR(50),
        remark             TEXT,
        sub_group          VARCHAR(100),
        sap_desc1          TEXT,
        sap_desc2          TEXT,
        variant_class      VARCHAR(100),
        profit_center      VARCHAR(20),
        profit_center_desc VARCHAR(255),
        PRIMARY KEY (level, code),
        INDEX idx_parent_code (parent_code),
        INDEX idx_level       (`level`)
    );

    -- ใช้ DELETE แทน TRUNCATE เพื่อหลีกเลี่ยง metadata lock
    DELETE FROM MCH_HIERARCHY;

    -- Insert ข้อมูลทุก level
    INSERT INTO MCH_HIERARCHY (
        level, code, name, parent_code,
        status, remark, sub_group,
        sap_desc1, sap_desc2, variant_class,
        profit_center, profit_center_desc
    )
    SELECT * FROM (
        SELECT '1' AS level, 
            `LV1 Code (Darft)` AS code, `LV1` AS name, NULL AS parent_code,
            NULL AS status, NULL AS remark, NULL AS sub_group,
            NULL AS sap_desc1, NULL AS sap_desc2, NULL AS variant_class,
            NULL AS profit_center, NULL AS profit_center_desc
        FROM MCH_SAP_ORG
        GROUP BY `LV1 Code (Darft)`, `LV1`

        UNION

        SELECT '2', 
            `LV2 Code`, `LV2`, `LV1 Code (Darft)`,
            NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL
        FROM MCH_SAP_ORG
        GROUP BY `LV2 Code`, `LV2`, `LV1 Code (Darft)`

        UNION

        SELECT '3', 
            `LV3 Code (Material group)`, `LV3`, `LV2 Code`,
            `Status`, `Remark`, `Sub Group`,
            `SAP Mat group Desc1 (20 char)`, `SAP Mat group Desc2 (50 char)`,
            `Variant Class`, `Profit Center`, `Profir Center Description`
        FROM MCH_SAP_ORG
        GROUP BY 
            `LV3 Code (Material group)`, `LV3`, `LV2 Code`,
            `Status`, `Remark`, `Sub Group`,
            `SAP Mat group Desc1 (20 char)`, `SAP Mat group Desc2 (50 char)`,
            `Variant Class`, `Profit Center`, `Profir Center Description`
    ) AS unioned
    ORDER BY level, code;

    -- แสดงจำนวน row ที่ insert
    SELECT 
        COUNT(*)         AS total_rows,
        SUM(level = '1') AS lv1_count,
        SUM(level = '2') AS lv2_count,
        SUM(level = '3') AS lv3_count,
        NOW()            AS executed_at
    FROM MCH_HIERARCHY;

END$$

DELIMITER ;