-- Master Char
SELECT
	`tmp`.`Characteristics ID` AS `Characteristics ID`,
	`tmp`.`Resource Spec Charactristics Name` AS `Characteristics Name`,
	`tmp`.`isDefault` AS `isDefault`,
	`tmp`.`valueType` AS `Value Type`,
	cast(`tmp`.`value` AS CHAR CHARSET utf8mb4) AS `value`,
	`tmp`.`regex` AS `regex`,
	`tmp`.`valueFrom` AS `valueFrom`,
	`tmp`.`valueTo` AS `valueTo`,
	`tmp`.`rangeInterval` AS `rangeInterval`,
	`tmp`.`unitOfMeasure` AS `unitOfMeasure`,
	COALESCE(`tmp`.`validForStartDateTime`, '2026-01-01T00:00:00.000Z') AS `validForStartDateTime`,
	COALESCE(`tmp`.`validForendDateTime`, '9999-12-31T00:00:00.000Z') AS `validForendDateTime`
FROM
	(
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
			row_number() OVER (PARTITION BY `characteristics_value`.`Characteristics ID`, `characteristics_value`.`Resource Spec Charactristics Name`, `characteristics_value`.`value` ORDER BY `characteristics_value`.`created_at`) AS `rn`
		FROM
			`characteristics_value`
		WHERE batch_id_insert = 1
	) `tmp`
WHERE
	(`tmp`.`rn` = 1);

-- Resource Spec
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
    AND cv.batch_id_insert = 1
GROUP BY
		cv.`Spec ID`,
    cv.`Characteristics ID`,
    cv.`Resource Spec Charactristics Name`,
    cv.`valueType`,
    cv.`value`,
    cv.`isDefault`
ORDER BY cv.`Characteristics ID`, cv.`Resource Spec Charactristics Name`, cv.`value`;

-- Product Spec
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
WHERE batch_id_insert = 1
ORDER BY `Spec ID`, `Characteristics ID`, `Product Spec Charactristics Name`, `value`;

