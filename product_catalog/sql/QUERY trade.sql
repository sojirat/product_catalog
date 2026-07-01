-- ============================================================
-- PART 1: DISCOUNT / REDUCTION
-- ============================================================
SELECT
    TDC.TRADE_DISCOUNT_ID AS EXTERNAL_ID,
    CONCAT(
--         CAST(TPD.TRADE_PRODUCT_ID AS CHAR), ' ',
        TM.CAMPAIGN, ' ',
        TM.TRADE_NAME, ' discount ',
        CAST(IFNULL(TDC.TRADE_PRICE_EXC_VAT, TDC.DISCOUNT_EXC) AS CHAR), ' Baht for ',
        IFNULL(TPD.BRAND,     ''), ' ',
        IFNULL(TPD.MODEL,     ''), ' ',
        IFNULL(TPD.COLOR,     ''), ' ',
        IFNULL(TPD.MAT_CODE,  '')
    ) AS PROMOTION_NAME,
    CASE
        WHEN TDC.TRADE_PRICE_EXC_VAT IS NULL THEN 'Discount'
        ELSE 'Reduction'
    END AS PROMOTION_TYPE,
    NULL              AS CODE,
    'Launched'        AS LIFECYCLE_STATUS,
    NULL              AS COUPON,
    'mutuallyExclusive' AS PROMOTION_CLASSIFICATION,
    'Cart'            AS PROMOTION_APPLICATION_LEVEL,
    DATE_FORMAT(TDC.START_DATE, '%Y-%m-%dT%H:%i:%s:000Z') AS valid_for_start_datetime,
    DATE_FORMAT(TDC.END_DATE,   '%Y-%m-%dT%H:%i:%s:000Z') AS valid_for_end_datetime,
    NULL              AS ACTION_CARDINALITY,
    CAST(IFNULL(TDC.TRADE_PRICE_EXC_VAT, TDC.DISCOUNT_EXC) AS CHAR) AS ACTION_VALUE,
    'Onetime'         AS PRICE_TYPE,
    TDC.OPTIONS       AS `PRIORITY`,
    NULL              AS ACTION_OBJECT_ID,
    NULL              AS PRICE_ID,
    CASE
        WHEN TDC.DISCOUNT_BY = 'B'               THEN 'Flat Discount'
        WHEN TDC.DISCOUNT_BY = 'P'               THEN 'Percent Discount'
        WHEN TDC.TRADE_PRICE_EXC_VAT IS NOT NULL THEN 'Reduct'
        ELSE NULL
    END               AS ACTION_TYPE,
    NULL              AS Award_Product_id,
    NULL              AS VARIANT_ID,
    NULL              AS PRODUCT_OFFER_ID,
    NULL              AS CHARACTERISTIC_VALUE,
    NULL              AS APPLICATION_DURATION
FROM       TR_PRODUCT  TPD
LEFT JOIN  TR_MST      TM  ON TM.TRADE_NO          = TPD.TRADE_NO
LEFT JOIN  TR_DISCOUNT TDC ON TDC.TRADE_PRODUCT_ID = TPD.TRADE_PRODUCT_ID
WHERE  NOW() BETWEEN TPD.START_DATE AND TPD.END_DATE
  AND  TDC.TRADE_DISCOUNT_ID IS NOT NULL
  AND  NOW() BETWEEN TDC.START_DATE AND TDC.END_DATE AND TM.SALE_TYPE = 'SALE'

UNION ALL

-- ============================================================
-- PART 2: FREE GOODS (get all — MAX_RECEIVE = COUNT)
-- ============================================================
SELECT
    TFG.TRADE_FREE_GOODS_ID AS EXTERNAL_ID,
    CONCAT(
--         CAST(TPD.TRADE_PRODUCT_ID AS CHAR), ' ',
        TM.CAMPAIGN, ' ',
        TM.TRADE_NAME, ' reward ',
        TFG.MAT_CODE, ' for ',
        IFNULL(TPD.BRAND,    ''), ' ',
        IFNULL(TPD.MODEL,    ''), ' ',
        IFNULL(TPD.COLOR,    ''), ' ',
        IFNULL(TPD.MAT_CODE, '')
    ) AS PROMOTION_NAME,
    'Award'           AS PROMOTION_TYPE,
    NULL              AS CODE,
    'Launched'        AS LIFECYCLE_STATUS,
    NULL              AS COUPON,
    'stackable'       AS PROMOTION_CLASSIFICATION,
    'Cart'            AS PROMOTION_APPLICATION_LEVEL,
    DATE_FORMAT(TFG.START_DATE, '%Y-%m-%dT%H:%i:%s:000Z') AS valid_for_start_datetime,
    DATE_FORMAT(TFG.END_DATE,   '%Y-%m-%dT%H:%i:%s:000Z') AS valid_for_end_datetime,
    1                 AS ACTION_CARDINALITY,
    TFG.QTY           AS ACTION_VALUE,
    NULL              AS PRICE_TYPE,
    NULL              AS `PRIORITY`,
    NULL              AS ACTION_OBJECT_ID,
    NULL              AS PRICE_ID,
    'Reward'          AS ACTION_TYPE,
    TFG.MAT_CODE      AS Award_Product_id,
    NULL              AS VARIANT_ID,
    NULL              AS PRODUCT_OFFER_ID,
    NULL              AS CHARACTERISTIC_VALUE,
    NULL              AS APPLICATION_DURATION
FROM       TR_PRODUCT   TPD
LEFT JOIN  TR_MST       TM  ON TM.TRADE_NO          = TPD.TRADE_NO
LEFT JOIN  TR_FREE_GOODS TFG ON TFG.TRADE_PRODUCT_ID = TPD.TRADE_PRODUCT_ID
WHERE  NOW() BETWEEN TPD.START_DATE AND TPD.END_DATE
  AND  TFG.TRADE_PRODUCT_ID IN (
           SELECT A.TRADE_PRODUCT_ID
           FROM (
               SELECT
                   TPD2.TRADE_PRODUCT_ID,
                   TPD2.MAX_RECEIVE_FREE_GOODS,
                   TFG2.QTY,
                   COUNT(*) AS NUMBER_OF_CHOICES
               FROM       TR_PRODUCT   TPD2
               INNER JOIN TR_FREE_GOODS TFG2
                       ON TFG2.TRADE_PRODUCT_ID = TPD2.TRADE_PRODUCT_ID
               WHERE  NOW() BETWEEN TFG2.START_DATE AND TFG2.END_DATE
               GROUP  BY TPD2.TRADE_PRODUCT_ID, TPD2.MAX_RECEIVE_FREE_GOODS, TFG2.QTY
               HAVING TPD2.MAX_RECEIVE_FREE_GOODS = COUNT(*)
           ) AS A
       )
  AND  NOW() BETWEEN TFG.START_DATE AND TFG.END_DATE

UNION ALL

-- ============================================================
-- PART 3: FREE GOODS x in y (MAX_RECEIVE < COUNT)
-- ============================================================
SELECT
    TFG.TRADE_FREE_GOODS_ID AS EXTERNAL_ID,
    CONCAT(
--         CAST(TPD.TRADE_PRODUCT_ID AS CHAR), ' ',
        TM.CAMPAIGN, ' ',
        TM.TRADE_NAME, ' reward ',
        TFG.MAT_CODE, ' for ',
        IFNULL(TPD.BRAND,    ''), ' ',
        IFNULL(TPD.MODEL,    ''), ' ',
        IFNULL(TPD.COLOR,    ''), ' ',
        IFNULL(TPD.MAT_CODE, '')
    ) AS PROMOTION_NAME,
    'Award'           AS PROMOTION_TYPE,
    NULL              AS CODE,
    'Launched'        AS LIFECYCLE_STATUS,
    NULL              AS COUPON,
    'stackable'       AS PROMOTION_CLASSIFICATION,
    'Cart'            AS PROMOTION_APPLICATION_LEVEL,
    DATE_FORMAT(TFG.START_DATE, '%Y-%m-%dT%H:%i:%s:000Z') AS valid_for_start_datetime,
    DATE_FORMAT(TFG.END_DATE,   '%Y-%m-%dT%H:%i:%s:000Z') AS valid_for_end_datetime,
--     TPD.MAX_RECEIVE_FREE_GOODS AS ACTION_CARDINALITY,
		1 								AS ACTION_CARDINALITY,
    TFG.QTY           AS ACTION_VALUE,
    NULL              AS PRICE_TYPE,
    NULL              AS `PRIORITY`,
    NULL              AS ACTION_OBJECT_ID,
    NULL              AS PRICE_ID,
    'Reward'          AS ACTION_TYPE,
    TFG.MAT_CODE      AS Award_Product_id,
    NULL              AS VARIANT_ID,
    NULL              AS PRODUCT_OFFER_ID,
    NULL              AS CHARACTERISTIC_VALUE,
    NULL              AS APPLICATION_DURATION
FROM       TR_PRODUCT    TPD
LEFT JOIN  TR_MST        TM  ON TM.TRADE_NO          = TPD.TRADE_NO
LEFT JOIN  TR_FREE_GOODS TFG ON TFG.TRADE_PRODUCT_ID = TPD.TRADE_PRODUCT_ID
WHERE  NOW() BETWEEN TPD.START_DATE AND TPD.END_DATE
  AND  TFG.TRADE_PRODUCT_ID IN (
           SELECT A.TRADE_PRODUCT_ID
           FROM (
               SELECT
                   TPD2.TRADE_PRODUCT_ID,
                   TPD2.MAX_RECEIVE_FREE_GOODS,
                   TFG2.QTY,
                   COUNT(*) AS NUMBER_OF_CHOICES
               FROM       TR_PRODUCT   TPD2
               INNER JOIN TR_FREE_GOODS TFG2
                       ON TFG2.TRADE_PRODUCT_ID = TPD2.TRADE_PRODUCT_ID
               WHERE  NOW() BETWEEN TFG2.START_DATE AND TFG2.END_DATE
               GROUP  BY TPD2.TRADE_PRODUCT_ID, TPD2.MAX_RECEIVE_FREE_GOODS, TFG2.QTY
               HAVING TPD2.MAX_RECEIVE_FREE_GOODS < COUNT(*)
           ) AS A
       )
  AND  NOW() BETWEEN TFG.START_DATE AND TFG.END_DATE;


-- ============================================================
-- UTILITY 1: ดู TRADE_PRODUCT_ID ที่ MAX_RECEIVE = COUNT (get all)
-- ============================================================
SELECT A.TRADE_PRODUCT_ID
FROM (
    SELECT
        TPD.TRADE_PRODUCT_ID,
        TPD.MAX_RECEIVE_FREE_GOODS,
        TFG.QTY,
        COUNT(*) AS NUMBER_OF_CHOICES
    FROM       TR_PRODUCT   TPD
    INNER JOIN TR_FREE_GOODS TFG
            ON TFG.TRADE_PRODUCT_ID = TPD.TRADE_PRODUCT_ID
    WHERE  NOW() BETWEEN TFG.START_DATE AND TFG.END_DATE
    GROUP  BY TPD.TRADE_PRODUCT_ID, TPD.MAX_RECEIVE_FREE_GOODS, TFG.QTY
    HAVING TPD.MAX_RECEIVE_FREE_GOODS = COUNT(*)
) AS A;


-- ============================================================
-- UTILITY 2: ดู NUMBER_OF_CHOICES ทั้งหมด
-- ============================================================
SELECT
    TPD.TRADE_PRODUCT_ID,
    TPD.MAX_RECEIVE_FREE_GOODS,
    TFG.QTY,
    COUNT(*) AS NUMBER_OF_CHOICES
FROM       TR_PRODUCT   TPD
INNER JOIN TR_FREE_GOODS TFG
        ON TFG.TRADE_PRODUCT_ID = TPD.TRADE_PRODUCT_ID
WHERE  NOW() BETWEEN TFG.START_DATE AND TFG.END_DATE
GROUP  BY TPD.TRADE_PRODUCT_ID, TPD.MAX_RECEIVE_FREE_GOODS, TFG.QTY;