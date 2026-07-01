SELECT
    ANY_VALUE(COLOR) AS value_cs,
    COUNT(*) AS duplicate_count
FROM PRODUCT_MST
GROUP BY CONVERT(COLOR USING BINARY)
HAVING COUNT(*) > 1
ORDER BY value_cs ASC;

SELECT
    PO_NAME,
    COUNT(*) AS duplicate_count
FROM tbl_product_offering
WHERE PO_NAME IS NOT NULL
  AND TRIM(PO_NAME) <> ''
GROUP BY PO_NAME
HAVING COUNT(*) > 1
ORDER BY duplicate_count DESC, PO_NAME;

SELECT
    PO_NAME,
    COUNT(*) AS duplicate_count
FROM tbl_product_offering_price
WHERE PO_NAME IS NOT NULL
  AND TRIM(PO_NAME) <> ''
GROUP BY PO_NAME
HAVING COUNT(*) > 1
ORDER BY duplicate_count DESC, PO_NAME;


SELECT
    ANY_VALUE(`Char Value.value`) AS value_cs,
		`Char Value.Product Offer Characteristics ID`,
    COUNT(*) AS duplicate_count
FROM tbl_product_offering_char_value
WHERE `Char Value.Product Offer Characteristics Name` = 'color'
  AND TRIM(`Char Value.value`) <> ''
GROUP BY CONVERT(`Char Value.value` USING BINARY), `Char Value.Product Offer Characteristics ID`
HAVING COUNT(*) > 1
ORDER BY value_cs ASC;

SELECT
    ANY_VALUE(`Char Value.value`) AS value_cs,
		`Char Value.Product Offer Characteristics ID`,
		`Char Value.Product Spec ID`,
    COUNT(*) AS duplicate_count
FROM v_product_offering_char_value
GROUP BY CONVERT(`Char Value.value` USING BINARY), `Char Value.Product Offer Characteristics ID`, `Char Value.Product Spec ID`
HAVING COUNT(*) > 1
ORDER BY value_cs ASC;

SELECT
    ANY_VALUE(`value`) AS value_cs,
		`Spec ID`,
		`Resource Spec Charactristics Name`,
    COUNT(*) AS duplicate_count
FROM characteristics_value
GROUP BY CONVERT(`value` USING BINARY), `Resource Spec Charactristics Name`,`Spec ID`
HAVING COUNT(*) > 1
ORDER BY value_cs ASC;

SELECT
    ANY_VALUE(`value`) AS value_cs,
		`Spec ID`,
		`Product Spec Charactristics Name`,
    COUNT(*) AS duplicate_count
FROM char_value
GROUP BY CONVERT(`value` USING BINARY), `Product Spec Charactristics Name`,`Spec ID`
HAVING COUNT(*) > 1
ORDER BY value_cs ASC;