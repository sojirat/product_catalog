DELIMITER $$

DROP PROCEDURE IF EXISTS sp_export_center_files $$

CREATE PROCEDURE sp_export_center_files (
    IN p_batch_id_insert INT
)
BEGIN

    -- =====================================================
    -- Master Char
    -- =====================================================

    SELECT
        `tmp`.`Characteristics ID` AS `Characteristics ID`,
        `tmp`.`Resource Spec Charactristics Name` AS `Characteristics Name`,
        `tmp`.`isDefault` AS `isDefault`,
        `tmp`.`valueType` AS `Value Type`,
        CAST(`tmp`.`value` AS CHAR CHARSET utf8mb4) AS `value`,
        `tmp`.`regex` AS `regex`,
        `tmp`.`valueFrom` AS `valueFrom`,
        `tmp`.`valueTo` AS `valueTo`,
        `tmp`.`rangeInterval` AS `rangeInterval`,
        `tmp`.`unitOfMeasure` AS `unitOfMeasure`,
        COALESCE(`tmp`.`validForStartDateTime`, '2026-01-01T00:00:00.000Z') AS `validForStartDateTime`,
        COALESCE(`tmp`.`validForendDateTime`, '9999-12-31T00:00:00.000Z') AS `validForendDateTime`
    FROM (
        SELECT
            cv.`Spec ID`,
            cv.`Characteristics ID`,
            cv.`Resource Spec Charactristics Name`,
            cv.`isDefault`,
            cv.`valueType`,
            cv.`value`,
            cv.`regex`,
            cv.`valueFrom`,
            cv.`valueTo`,
            cv.`rangeInterval`,
            cv.`unitOfMeasure`,
            cv.`validForStartDateTime`,
            cv.`validForendDateTime`,
            cv.`batch_id_insert`,
            cv.`batch_id_update`,
            cv.`created_by`,
            cv.`created_at`,
            cv.`updated_by`,
            cv.`updated_at`,
            ROW_NUMBER() OVER (
                PARTITION BY 
                    cv.`Characteristics ID`,
                    TRIM(
                        REPLACE(
                            REPLACE(
                                CAST(cv.`value` AS CHAR CHARSET utf8mb4),
                                UNHEX('C2A0'),
                                ' '
                            ),
                            '  ',
                            ' '
                        )
                    )
                ORDER BY cv.`created_at`
            ) AS `rn`
        FROM `characteristics_value` cv
        WHERE (
            p_batch_id_insert IS NULL
            OR cv.batch_id_insert = p_batch_id_insert
        )
    ) `tmp`
    WHERE `tmp`.`rn` = 1;


    -- =====================================================
    -- Resource Spec
    -- =====================================================

    SELECT 
        cv.`Spec ID`,
        cv.`Characteristics ID`,
        cv.`Resource Spec Charactristics Name`,
        cv.`valueType`,
        cv.`value`,
        cv.`isDefault`
    FROM characteristics_value cv
    INNER JOIN spec_characteristics sc_spec
        ON cv.`Spec ID` = sc_spec.`Spec ID`
    INNER JOIN spec_characteristics sc_char
        ON cv.`Characteristics ID` = sc_char.`Characteristics ID`
    WHERE sc_spec.characteristicType = 'ResourceSpecification'
        AND sc_char.characteristicType = 'ResourceSpecification'
        AND (
            p_batch_id_insert IS NULL
            OR cv.batch_id_insert = p_batch_id_insert
        )
    GROUP BY
        cv.`Spec ID`,
        cv.`Characteristics ID`,
        cv.`Resource Spec Charactristics Name`,
        cv.`valueType`,
        cv.`value`,
        cv.`isDefault`
    ORDER BY 
        cv.`Characteristics ID`,
        cv.`Resource Spec Charactristics Name`,
        cv.`value`;


    -- =====================================================
    -- Product Spec
    -- =====================================================

    SELECT 
        `Spec ID`,
        `Characteristics ID`,
        `Product Spec Charactristics Name`,
        `valueType`,
        `value`,
        CASE 
            WHEN `isDefault` IS NULL OR `isDefault` = '' THEN 'false'
            ELSE `isDefault`
        END AS `isDefault`
    FROM char_value
    WHERE (
        p_batch_id_insert IS NULL
        OR batch_id_insert = p_batch_id_insert
    )
    ORDER BY 
        `Spec ID`,
        `Characteristics ID`,
        `Product Spec Charactristics Name`,
        `value`;

END $$

DELIMITER ;


-- =====================================================
-- Example
-- =====================================================

-- filter batch_id_insert = 1
CALL sp_export_center_files(1);

-- no filter
-- CALL sp_export_center_files(NULL);