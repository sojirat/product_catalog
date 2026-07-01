-- =====================================================
-- Master Characteristics
-- =====================================================

-- Master Characteristics
DROP VIEW IF EXISTS vw_01_master_characteristics;

CREATE VIEW vw_01_master_characteristics AS
SELECT
    CAST(`Characteristics ID` AS CHAR) AS `Characteristics ID`,
    CAST(`Characteristics Name` AS CHAR) AS `Characteristics Name`,
    CAST(`Char Display Name` AS CHAR) AS `Char Display Name`,
    CAST(`External ID` AS CHAR) AS `External ID`,
    CAST(`Value Type` AS CHAR) AS `Value Type`,
    CAST(`Value SubType` AS CHAR) AS `Value SubType`,
    CAST(`Display Sequence` AS CHAR) AS `Display Sequence`,
    CAST(`minCardinality` AS CHAR) AS `minCardinality`,
    CAST(`maxCardinality` AS CHAR) AS `maxCardinality`,
    CAST(`characteristicType` AS CHAR) AS `characteristicType`,
    CAST(`regex` AS CHAR) AS `regex`,
    CAST(`code` AS CHAR) AS `code`,
    CAST(`href` AS CHAR) AS `href`,
    CAST(`createdBy` AS CHAR) AS `createdBy`,
    CAST(`createdOn` AS CHAR) AS `createdOn`,
    CAST(`lastUpdatedBy` AS CHAR) AS `lastUpdatedBy`,
    CAST(`lastUpdate` AS CHAR) AS `lastUpdate`
FROM master_characteristics;

-- Master Characteristics Value
DROP VIEW IF EXISTS vw_02_master_characteristics_value;

CREATE VIEW vw_02_master_characteristics_value AS
SELECT
    CAST(`tmp`.`Characteristics ID` AS CHAR) AS `Characteristics ID`,
    CAST(`tmp`.`Resource Spec Charactristics Name` AS CHAR) AS `Characteristics Name`,
    CAST(`tmp`.`isDefault` AS CHAR) AS `isDefault`,
    CAST(`tmp`.`valueType` AS CHAR) AS `Value Type`,
    CAST(`tmp`.`value` AS CHAR CHARSET utf8mb4) AS `value`,
		CAST(`tmp`.`rangeInterval` AS CHAR) AS `rangeInterval`,
    CAST(`tmp`.`regex` AS CHAR) AS `regex`,
    CAST(`tmp`.`valueFrom` AS CHAR) AS `valueFrom`,
    CAST(`tmp`.`valueTo` AS CHAR) AS `valueTo`,
		CAST(`tmp`.`unitOfMeasure` AS CHAR) AS `unitOfMeasure`,
    CAST(
        COALESCE(`tmp`.`validForStartDateTime`, '2026-01-01T00:00:00.000Z')
        AS CHAR
    ) AS `validForStartDateTime`,
    CAST(
        COALESCE(`tmp`.`validForendDateTime`, '9999-12-31T00:00:00.000Z')
        AS CHAR
    ) AS `validForendDateTime`
FROM (
    SELECT
        `characteristics_value`.`Spec ID` AS `Spec ID`,
        `characteristics_value`.`Characteristics ID` AS `Characteristics ID`,
        `characteristics_value`.`Resource Spec Charactristics Name` AS `Resource Spec Charactristics Name`,
        `characteristics_value`.`isDefault` AS `isDefault`,
        `characteristics_value`.`valueType` AS `valueType`,
        `characteristics_value`.`value` AS `value`,
        `characteristics_value`.`regex` AS `regex`,
        `characteristics_value`.`valueFrom` AS `valueFrom`,
        `characteristics_value`.`valueTo` AS `valueTo`,
        `characteristics_value`.`rangeInterval` AS `rangeInterval`,
        `characteristics_value`.`unitOfMeasure` AS `unitOfMeasure`,
        `characteristics_value`.`validForStartDateTime` AS `validForStartDateTime`,
        `characteristics_value`.`validForendDateTime` AS `validForendDateTime`,
        `characteristics_value`.`batch_id_insert` AS `batch_id_insert`,
        `characteristics_value`.`batch_id_update` AS `batch_id_update`,
        `characteristics_value`.`created_by` AS `created_by`,
        `characteristics_value`.`created_at` AS `created_at`,
        `characteristics_value`.`updated_by` AS `updated_by`,
        `characteristics_value`.`updated_at` AS `updated_at`,
        ROW_NUMBER() OVER (
            PARTITION BY 
                `characteristics_value`.`Characteristics ID`,
                `characteristics_value`.`Resource Spec Charactristics Name`,
                `characteristics_value`.`value`
            ORDER BY `characteristics_value`.`created_at`
        ) AS `rn`
    FROM `characteristics_value`
    WHERE batch_id_insert = 1 AND NULLIF(TRIM(`value`), '') IS NOT NULL
) `tmp`
WHERE (`tmp`.`rn` = 1);

-- =====================================================
-- Resource Spec
-- =====================================================
		
-- Resource Specification
DROP VIEW IF EXISTS vw_03_resource_specification;

CREATE VIEW vw_03_resource_specification AS
SELECT
--     CAST(`OLD_ID` AS CHAR) AS `OLD_ID`,
    CAST(`Spec ID` AS CHAR) AS `Spec ID`,
    CAST(`Name` AS CHAR) AS `Name`,
    CAST(`Description` AS CHAR) AS `Description`,
    CAST(`Specification Type` AS CHAR) AS `Specification Type`,

    CASE
        WHEN `isBundle` = 1 THEN 'TRUE'
        ELSE 'FALSE'
    END AS `isBundle`,

    CASE
        WHEN `isAssetable` = 1 THEN 'TRUE'
        ELSE 'FALSE'
    END AS `isAssetable`,

    CAST(`owningSystem` AS CHAR) AS `owningSystem`,
    CAST(`relatedSystemName` AS CHAR) AS `relatedSystemName`,
    CAST(`externalID` AS CHAR) AS `externalID`,
		CAST(
        COALESCE(`Start Date`, '2026-01-01T00:00:00.000Z')
        AS CHAR
    ) AS `Start Date`,
    CAST(
        COALESCE(`End Date`, '9999-12-31T00:00:00.000Z')
        AS CHAR
    ) AS `End Date`

FROM resource_specification;


-- Resource Spec Char Value
DROP VIEW IF EXISTS vw_04_resource_spec_characteristics;

CREATE VIEW vw_04_resource_spec_characteristics AS
SELECT 
    CAST(`Spec ID` AS CHAR) AS `Spec ID`,
    CAST(`Characteristics ID` AS CHAR) AS `Characteristics ID`,
		CAST(`name` AS CHAR) AS `name`,
		CAST(`displayName` AS CHAR) AS `displayName`,
		CAST(`valueType` AS CHAR) AS `valueType`,
		CAST(`valueSubType` AS CHAR) AS `valueSubType`,
		CAST(`displaySequence` AS CHAR) AS `displaySequence`,
		CAST(`minCardinality` AS CHAR) AS `minCardinality`,
		CAST(`maxCardinality` AS CHAR) AS `maxCardinality`,
		CASE
        WHEN `isVisible` = 1 THEN 'TRUE'
        ELSE 'FALSE'
    END AS `isVisible`,

    CASE
        WHEN `isUnique` = 1 THEN 'TRUE'
        ELSE 'FALSE'
    END AS `isUnique`,
		CAST(`characteristicType` AS CHAR) AS `characteristicType`,
		CASE
        WHEN `extensible` = 1 THEN 'TRUE'
        ELSE 'FALSE'
    END AS `extensible`,

    CASE
        WHEN `configurable` = 1 THEN 'TRUE'
        ELSE 'FALSE'
    END AS `configurable`,
		CAST(`configurationStage` AS CHAR) AS `configurationStage`
FROM spec_characteristics
WHERE characteristicType = 'ResourceSpecification'
ORDER BY `Characteristics ID`;


-- Resource Spec Characteristics 
DROP VIEW IF EXISTS vw_05_resource_spec_char_value;

CREATE VIEW vw_05_resource_spec_char_value AS
SELECT 
    CAST(cv.`Spec ID` AS CHAR) AS `Spec ID`,
    CAST(cv.`Characteristics ID` AS CHAR) AS `Characteristics ID`,
    CAST(cv.`Resource Spec Charactristics Name` AS CHAR) AS `Resource Spec Charactristics Name`,
    CAST(cv.`valueType` AS CHAR) AS `valueType`,
    CAST(cv.`value` AS CHAR CHARSET utf8mb4) AS `value`,
		IFNULL(CAST(cv.`isDefault` AS CHAR), 'FALSE') AS isDefault
FROM characteristics_value cv
INNER JOIN spec_characteristics sc_spec
    ON cv.`Spec ID` = sc_spec.`Spec ID`
INNER JOIN spec_characteristics sc_char
    ON cv.`Characteristics ID` = sc_char.`Characteristics ID`
WHERE sc_spec.characteristicType = 'ResourceSpecification'
    AND sc_char.characteristicType = 'ResourceSpecification'
    AND cv.batch_id_insert = 1 AND NULLIF(TRIM(cv.`value`), '') IS NOT NULL
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
-- Product Specification
-- =====================================================

-- Product Specification
DROP VIEW IF EXISTS vw_06_product_specification;

CREATE VIEW vw_06_product_specification AS
SELECT
    CAST(`product_specification`.`Spec ID` AS CHAR CHARSET utf8mb4) AS `Spec ID`,
    CAST(`product_specification`.`name` AS CHAR CHARSET utf8mb4) AS `name`,
    CAST(`product_specification`.`description` AS CHAR CHARSET utf8mb4) AS `description`,

    CASE
        WHEN `product_specification`.`isBundle` = 1 THEN 'TRUE'
        ELSE 'FALSE'
    END AS `isBundle`,

    CAST(`product_specification`.`externalID` AS CHAR CHARSET utf8mb4) AS `externalID`,

    CASE
        WHEN `product_specification`.`Start Date` IS NULL
             OR `product_specification`.`Start Date` = '00:00:00'
        THEN '2026-01-01T00:00:00.000Z'
        ELSE CAST(`product_specification`.`Start Date` AS CHAR CHARSET utf8mb4)
    END AS `Start Date`,

    CASE
        WHEN `product_specification`.`end Date` IS NULL
             OR `product_specification`.`end Date` = '23:59:00'
        THEN '9999-12-31T00:00:00.000Z'
        ELSE CAST(`product_specification`.`end Date` AS CHAR CHARSET utf8mb4)
    END AS `end Date`

FROM `product_specification`;

-- Product Spec Characteristics
DROP VIEW IF EXISTS vw_07_product_spec_characteristics;

CREATE VIEW vw_07_product_spec_characteristics AS
SELECT
    CAST(`Spec ID` AS CHAR) AS `Spec ID`,
    CAST(`Characteristics ID` AS CHAR) AS `Characteristics ID`,
    CAST(`name` AS CHAR) AS `name`,
    CAST(`displayName` AS CHAR) AS `displayName`,
    CAST(`valueType` AS CHAR) AS `valueType`,
    CAST(`valueSubType` AS CHAR) AS `valueSubType`,
    CAST(`displaySequence` AS CHAR) AS `displaySequence`,
    CAST(`minCardinality` AS CHAR) AS `minCardinality`,
    CAST(`maxCardinality` AS CHAR) AS `maxCardinality`,
		IF(COALESCE(isVisible, 0) = 1, 'TRUE', 'FALSE') AS isVisible,
		IF(COALESCE(isUnique, 0) = 1, 'TRUE', 'FALSE') AS isUnique,
    CAST(`characteristicType` AS CHAR) AS `characteristicType`,
		IF(COALESCE(extensible, 0) = 1, 'TRUE', 'FALSE') AS extensible,
		IF(COALESCE(configurable, 0) = 1, 'TRUE', 'FALSE') AS configurable,
    CAST(`configurationStage` AS CHAR) AS `configurationStage`
FROM spec_characteristics
WHERE characteristicType = 'ProductSpecification'
ORDER BY `Spec ID`, `Characteristics ID`;

-- Product Spec Char Value
DROP VIEW IF EXISTS vw_08_product_spec_char_value;

CREATE VIEW vw_08_product_spec_char_value AS
SELECT 
    CAST(`Spec ID` AS CHAR) AS `Spec ID`,
    CAST(`Characteristics ID` AS CHAR) AS `Characteristic ID`,
    CAST(`Product Spec Charactristics Name` AS CHAR) AS `Product Spec Charactristics Name`,
    CAST(`valueType` AS CHAR) AS `valueType`,
    CAST(`value` AS CHAR CHARSET utf8mb4) AS `value`,
    IFNULL(CAST(isDefault AS CHAR), 'FALSE') AS isDefault
FROM char_value 
WHERE NULLIF(TRIM(`value`), '') IS NOT NULL
ORDER BY `Characteristics ID`;


-- Product Associated Specifications
DROP VIEW IF EXISTS vw_09_product_associated_specifications;

CREATE VIEW vw_09_product_associated_specifications AS
SELECT
    CAST(`Product Specification ID` AS CHAR) AS `Product Specification ID`,
    CAST(`Product Specification Name` AS CHAR) AS `Product Specification Name`,
    CAST(`Related Service Specification ID` AS CHAR) AS `Related Service Specification ID`,
    CAST(`Related Service Specification` AS CHAR) AS `Related Service Specification Name`,
    CAST(`Related Resource Specification ID` AS CHAR) AS `Related Resource Specification ID`,
    CAST(`Related Resource Specification` AS CHAR) AS `Related Resource Specification Name`
FROM associated_specifications
ORDER BY `Product Specification ID`;