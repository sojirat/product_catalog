DELIMITER $$
DROP PROCEDURE IF EXISTS generate_product_offering_price$$
CREATE PROCEDURE generate_product_offering_price(
    IN  batch_id   				INT,
    IN  p_created_by    	VARCHAR(255)
)
BEGIN
    DECLARE v_new_count      INT DEFAULT 0;
    DECLARE v_pb_new_count   INT DEFAULT 0;
    DECLARE v_of_start       INT DEFAULT 0;
    DECLARE v_of_pad         INT DEFAULT 6;
		DECLARE v_actor      		 VARCHAR(255) DEFAULT 'system';

    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        RESIGNAL;
    END;

    SET SESSION group_concat_max_len = 1000000;
		SET v_actor = IFNULL(NULLIF(TRIM(p_created_by), ''), 'system');

    -- Step 1: แตก PRODUCT_ID ออกเป็น rows (TEMPORARY TABLE)
    DROP TEMPORARY TABLE IF EXISTS tbl_po_product_id_exploded;
    CREATE TEMPORARY TABLE tbl_po_product_id_exploded AS
    SELECT DISTINCT
        po.PO_ID,
        clean_name(po.PO_NAME) AS PO_NAME,
        TRIM(jt.product_id_val) COLLATE utf8mb4_general_ci AS PRODUCT_ID
    FROM tbl_product_offering po
    JOIN JSON_TABLE(
        CONCAT('["', REPLACE(po.PRODUCT_ID COLLATE utf8mb4_general_ci, ',', '","'), '"]'),
        '$[*]' COLUMNS (product_id_val VARCHAR(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci PATH '$')
    ) jt ON TRUE;

    -- Step 1b: tmp_po_map สำหรับ Pre-Booking lookup
    DROP TEMPORARY TABLE IF EXISTS tmp_po_map;
    CREATE TEMPORARY TABLE tmp_po_map (
        PO_ID      VARCHAR(500),
        PO_NAME    VARCHAR(500),
        PRODUCT_ID VARCHAR(255)
    ) ENGINE=InnoDB;

    INSERT INTO tmp_po_map (PO_ID, PO_NAME, PRODUCT_ID)
    SELECT
        po.PO_ID,
        clean_name(po.PO_NAME) AS PO_NAME,
        TRIM(jt.product_id_val) AS PRODUCT_ID
    FROM tbl_product_offering po
    JOIN JSON_TABLE(
        CONCAT('["', REPLACE(po.PRODUCT_ID COLLATE utf8mb4_general_ci, ',', '","'), '"]'),
        '$[*]' COLUMNS (
            product_id_val VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci PATH '$'
        )
    ) jt ON TRUE;

    CREATE INDEX idx_tmp_product_id ON tmp_po_map(PRODUCT_ID(255));
    CREATE INDEX idx_tmp_po_id      ON tmp_po_map(PO_ID(255));

    -- Step 2 (raw): GROUP price ต่อ PO_ID พร้อม deduplicate PRICE_MST (เหมือนเดิม)
    DROP TEMPORARY TABLE IF EXISTS tbl_po_price_grouped_raw;
    CREATE TEMPORARY TABLE tbl_po_price_grouped_raw AS
    SELECT
        exp.PO_ID AS SRC_PO_ID,
        CONCAT_WS(' ',
            ANY_VALUE(exp.PO_NAME),
            p.PRICE_GROUP,
            p.INC_VAT,
            'Baht'
        ) AS PO_NAME,
        p.PRICE_GROUP,
        p.EXC_VAT,
        p.INC_VAT,
        p.VAT_AMT,
        p.VAT_RATE,
        MIN(p.EFFECTIVE_DATE) AS EFFECTIVE_DATE,
        MAX(p.EXPIRE_DATE)    AS EXPIRE_DATE,
        GROUP_CONCAT(
            DISTINCT p.PRODUCT_ID
            ORDER BY p.PRODUCT_ID ASC
            SEPARATOR ', '
        ) AS PRODUCT_ID
    FROM (SELECT DISTINCT PO_ID, PO_NAME, PRODUCT_ID FROM tbl_po_product_id_exploded) exp
    JOIN (
        SELECT
            PRODUCT_ID,
            PRICE_GROUP,
            EXC_VAT,
            ANY_VALUE(INC_VAT)  AS INC_VAT,
            ANY_VALUE(VAT_AMT)  AS VAT_AMT,
            ANY_VALUE(VAT_RATE) AS VAT_RATE,
            MIN(EFFECTIVE_DATE) AS EFFECTIVE_DATE,
            MAX(EXPIRE_DATE)    AS EXPIRE_DATE
        FROM PRICE_MST
        GROUP BY PRODUCT_ID, PRICE_GROUP, EXC_VAT
    ) p ON p.PRODUCT_ID COLLATE utf8mb4_general_ci = exp.PRODUCT_ID
    GROUP BY
        exp.PO_ID,
        p.PRICE_GROUP,
        p.EXC_VAT,
        p.INC_VAT,
        p.VAT_AMT,
        p.VAT_RATE;

    -- Step 2 (merge): ยุบแถวที่ PO_NAME / PRICE_GROUP / EXC_VAT / INC_VAT / VAT_AMT / VAT_RATE /
    -- EFFECTIVE_DATE / EXPIRE_DATE เหมือนกันทุก field ให้เหลือ 1 แถว
    -- พร้อมรวม SRC_PO_ID และ PRODUCT_ID เข้าด้วยกัน (PO_ID ค่อยไปรันใหม่ใน Step 7)
    DROP TEMPORARY TABLE IF EXISTS tbl_product_offering_price_tmp;
    CREATE TEMPORARY TABLE tbl_product_offering_price_tmp AS
    SELECT
        GROUP_CONCAT(DISTINCT r.SRC_PO_ID ORDER BY r.SRC_PO_ID SEPARATOR ', ') AS SRC_PO_ID,
        r.PO_NAME,
        r.PRICE_GROUP,
        r.EXC_VAT,
        r.INC_VAT,
        r.VAT_AMT,
        r.VAT_RATE,
        r.EFFECTIVE_DATE,
        r.EXPIRE_DATE,
        GROUP_CONCAT(DISTINCT jt.pid ORDER BY jt.pid SEPARATOR ', ') AS PRODUCT_ID
    FROM tbl_po_price_grouped_raw r
    JOIN JSON_TABLE(
        CONCAT('["', REPLACE(r.PRODUCT_ID, ', ', '","'), '"]'),
        '$[*]' COLUMNS (pid VARCHAR(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci PATH '$')
    ) jt ON TRUE
    GROUP BY
        r.PO_NAME,
        r.PRICE_GROUP,
        r.EXC_VAT,
        r.INC_VAT,
        r.VAT_AMT,
        r.VAT_RATE,
        r.EFFECTIVE_DATE,
        r.EXPIRE_DATE;

    -- Step 2b (raw): Pre-Booking price จาก TR_DISCOUNT ต่อ PO_ID (เหมือนเดิม)
    DROP TEMPORARY TABLE IF EXISTS tbl_prebooking_price_raw;
    CREATE TEMPORARY TABLE tbl_prebooking_price_raw AS
    SELECT
        pom.PO_ID                                                                       AS SRC_PO_ID,
        CONCAT_WS(' ',
            ANY_VALUE(pom.PO_NAME),
						td.GROUP_PRICE,
						td.DEPOSIT_INC_VAT,
            'Baht'
        ) AS PO_NAME,
        td.GROUP_PRICE                                                                  AS PRICE_GROUP,
        'Pre-Booking'                                                                   AS PRICE_TYPE,
        td.DEPOSIT_EXC_VAT                                                              AS EXC_VAT,
        td.DEPOSIT_INC_VAT                                                              AS INC_VAT,
        td.DEPOSIT_VAT_AMT                                                              AS VAT_AMT,
        td.VAT_RATE                                                                     AS VAT_RATE,
        td.START_DATE                                                                   AS EFFECTIVE_DATE,
        td.END_DATE                                                                     AS EXPIRE_DATE,
        GROUP_CONCAT(
            DISTINCT pm.PRODUCT_ID
            ORDER BY pm.PRODUCT_ID ASC
            SEPARATOR ', '
        )                                                                               AS PRODUCT_ID
    FROM TR_DISCOUNT td
    JOIN TR_PRODUCT tp
        ON td.TRADE_PRODUCT_ID = tp.TRADE_PRODUCT_ID
    JOIN PRODUCT_MST pm
        ON tp.BRAND            = pm.BRAND
        AND tp.COLOR           = pm.COLOR
        AND tp.MAT_CODE        = pm.MAT_CODE
        AND tp.MODEL           = pm.MODEL
        AND tp.PRODUCT_TYPE    = pm.PRODUCT_TYPE
        AND tp.PRODUCT_SUBTYPE = pm.PRODUCT_SUBTYPE
    LEFT JOIN tmp_po_map pom
        ON pm.PRODUCT_ID COLLATE utf8mb4_general_ci = pom.PRODUCT_ID COLLATE utf8mb4_general_ci
    WHERE td.DEPOSIT_INC_VAT IS NOT NULL
    GROUP BY
        pom.PO_ID,
        td.GROUP_PRICE,
        td.DEPOSIT_EXC_VAT,
        td.DEPOSIT_INC_VAT,
        td.DEPOSIT_VAT_AMT,
        td.VAT_RATE,
        td.START_DATE,
        td.END_DATE;

    -- Step 2b (merge): ยุบแถว Pre-Booking ที่ PO_NAME / PRICE_GROUP / EXC_VAT / INC_VAT /
    -- VAT_AMT / VAT_RATE / EFFECTIVE_DATE / EXPIRE_DATE เหมือนกันทุก field ให้เหลือ 1 แถว
    DROP TEMPORARY TABLE IF EXISTS tbl_prebooking_price_tmp;
    CREATE TEMPORARY TABLE tbl_prebooking_price_tmp AS
    SELECT
        GROUP_CONCAT(DISTINCT r.SRC_PO_ID ORDER BY r.SRC_PO_ID SEPARATOR ', ') AS SRC_PO_ID,
        r.PO_NAME,
        r.PRICE_GROUP,
        r.PRICE_TYPE,
        r.EXC_VAT,
        r.INC_VAT,
        r.VAT_AMT,
        r.VAT_RATE,
        r.EFFECTIVE_DATE,
        r.EXPIRE_DATE,
        GROUP_CONCAT(DISTINCT jt.pid ORDER BY jt.pid SEPARATOR ', ') AS PRODUCT_ID
    FROM tbl_prebooking_price_raw r
    JOIN JSON_TABLE(
        CONCAT('["', REPLACE(r.PRODUCT_ID, ', ', '","'), '"]'),
        '$[*]' COLUMNS (pid VARCHAR(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci PATH '$')
    ) jt ON TRUE
    GROUP BY
        r.PO_NAME,
        r.PRICE_GROUP,
        r.PRICE_TYPE,
        r.EXC_VAT,
        r.INC_VAT,
        r.VAT_AMT,
        r.VAT_RATE,
        r.EFFECTIVE_DATE,
        r.EXPIRE_DATE;

    -- Step 3: สร้าง tbl_product_offering_price ถ้ายังไม่มี
    CREATE TABLE IF NOT EXISTS tbl_product_offering_price (
        `PO_ID`          VARCHAR(500),
        `SRC_PO_ID`      VARCHAR(500),
        `PO_NAME`        VARCHAR(500),
        `PRICE_GROUP`    VARCHAR(100),
        `PRICE_TYPE`     VARCHAR(100) DEFAULT 'Onetime',
        `EXC_VAT`        DECIMAL(15,2),
        `INC_VAT`        DECIMAL(15,2),
        `VAT_AMT`        DECIMAL(15,2),
        `VAT_RATE`       DECIMAL(5,2),
        `EFFECTIVE_DATE` DATE,
        `EXPIRE_DATE`    DATETIME,
        `PRODUCT_ID`     TEXT,
				`batch_id_insert`	INT,
				`batch_id_update` INT,
        `created_by`     VARCHAR(255) DEFAULT 'system',
        `created_at`     DATETIME(3)  DEFAULT NOW(3),
        `updated_by`     VARCHAR(255) DEFAULT NULL,
        `updated_at`     DATETIME(3)  DEFAULT NULL,
        INDEX idx_po_id   (`PO_ID`(255)),
        INDEX idx_src_key (`SRC_PO_ID`(255), `PRICE_GROUP`, `EXC_VAT`)
    );

    -- Step 4: หา Onetime rows ใหม่ (match ด้วย PO_NAME + PRICE_GROUP + EXC_VAT
    -- เพื่อให้ทนต่อกรณี SRC_PO_ID ยุบรวม/แตกต่างกันไปในแต่ละรอบรัน)
    DROP TEMPORARY TABLE IF EXISTS tbl_price_new_rows;
    CREATE TEMPORARY TABLE tbl_price_new_rows AS
    SELECT t.*
    FROM tbl_product_offering_price_tmp t
    LEFT JOIN tbl_product_offering_price e
        ON  e.PO_NAME      COLLATE utf8mb4_general_ci = t.PO_NAME     COLLATE utf8mb4_general_ci
        AND e.PRICE_GROUP  COLLATE utf8mb4_general_ci = t.PRICE_GROUP COLLATE utf8mb4_general_ci
        AND e.EXC_VAT = t.EXC_VAT
        AND e.PRICE_TYPE = 'Onetime'
    WHERE e.PO_NAME IS NULL;

    SELECT COUNT(*) INTO v_new_count FROM tbl_price_new_rows;

    -- Step 4b: หา Pre-Booking rows ใหม่
    DROP TEMPORARY TABLE IF EXISTS tbl_prebooking_new_rows;
    CREATE TEMPORARY TABLE tbl_prebooking_new_rows AS
    SELECT t.*
    FROM tbl_prebooking_price_tmp t
    LEFT JOIN tbl_product_offering_price e
        ON  e.PO_NAME      COLLATE utf8mb4_general_ci = t.PO_NAME     COLLATE utf8mb4_general_ci
        AND e.PRICE_GROUP  COLLATE utf8mb4_general_ci = t.PRICE_GROUP COLLATE utf8mb4_general_ci
        AND e.EXC_VAT      = t.EXC_VAT
        AND e.PRICE_TYPE   = 'Pre-Booking'
    WHERE e.PO_NAME IS NULL;

    SELECT COUNT(*) INTO v_pb_new_count FROM tbl_prebooking_new_rows;

    START TRANSACTION;

    -- Step 5: Reserve sequence — Onetime + Pre-Booking รวม batch เดียว
    IF (v_new_count + v_pb_new_count) > 0 THEN
        CALL get_next_sequence_batch(
            'product_offering_price', NULL, (v_new_count + v_pb_new_count),
            v_of_start, @v_of_end, @v_of_prefix, @v_of_suffix, v_of_pad
        );
    END IF;

    -- Step 6: Update Onetime rows ที่มีอยู่แล้ว (match ด้วย PO_NAME + PRICE_GROUP + EXC_VAT)
    UPDATE tbl_product_offering_price e
    JOIN tbl_product_offering_price_tmp t
        ON  e.PO_NAME      COLLATE utf8mb4_general_ci = t.PO_NAME     COLLATE utf8mb4_general_ci
        AND e.PRICE_GROUP  COLLATE utf8mb4_general_ci = t.PRICE_GROUP COLLATE utf8mb4_general_ci
        AND e.EXC_VAT = t.EXC_VAT
        AND e.PRICE_TYPE = 'Onetime'
    SET
        e.SRC_PO_ID      	= t.SRC_PO_ID,
        e.INC_VAT        	= t.INC_VAT,
        e.VAT_AMT        	= t.VAT_AMT,
        e.VAT_RATE       	= t.VAT_RATE,
        e.EFFECTIVE_DATE 	= t.EFFECTIVE_DATE,
        e.EXPIRE_DATE    	= t.EXPIRE_DATE,
        e.PRODUCT_ID     	= t.PRODUCT_ID,
				e.batch_id_update	= batch_id,
        e.updated_by     	= v_actor,
        e.updated_at     	= NOW(3);

    -- Step 6b: Update Pre-Booking rows ที่มีอยู่แล้ว
    UPDATE tbl_product_offering_price e
    JOIN tbl_prebooking_price_tmp t
        ON  e.PO_NAME      COLLATE utf8mb4_general_ci = t.PO_NAME     COLLATE utf8mb4_general_ci
        AND e.PRICE_GROUP  COLLATE utf8mb4_general_ci = t.PRICE_GROUP COLLATE utf8mb4_general_ci
        AND e.EXC_VAT      = t.EXC_VAT
        AND e.PRICE_TYPE   = 'Pre-Booking'
    SET
        e.SRC_PO_ID      	= t.SRC_PO_ID,
        e.INC_VAT        	= t.INC_VAT,
        e.VAT_AMT        	= t.VAT_AMT,
        e.VAT_RATE       	= t.VAT_RATE,
        e.EFFECTIVE_DATE 	= t.EFFECTIVE_DATE,
        e.EXPIRE_DATE    	= t.EXPIRE_DATE,
        e.PRODUCT_ID     	= t.PRODUCT_ID,
				e.batch_id_update	= batch_id,
        e.updated_by     	= v_actor,
        e.updated_at     	= NOW(3);

    -- Step 7: Insert Onetime rows ใหม่ (รัน PO_ID ใหม่ตอนนี้)
    SET @v_rn = v_of_start - 1;

    INSERT INTO tbl_product_offering_price
        (PO_ID, SRC_PO_ID, PO_NAME, PRICE_GROUP, EXC_VAT, INC_VAT,
         VAT_AMT, VAT_RATE, EFFECTIVE_DATE, EXPIRE_DATE, PRODUCT_ID,
         batch_id_insert, created_by, created_at)
    SELECT
        CONCAT(
            @v_of_prefix, LPAD(@v_rn := @v_rn + 1, v_of_pad, '0')
        ),
        SRC_PO_ID,
        PO_NAME,
        PRICE_GROUP,
        EXC_VAT,
        INC_VAT,
        VAT_AMT,
        VAT_RATE,
        EFFECTIVE_DATE,
        EXPIRE_DATE,
        PRODUCT_ID,
        batch_id, v_actor, NOW(3)
    FROM tbl_price_new_rows
    ORDER BY PO_NAME, PRICE_GROUP, EXC_VAT;

    -- Step 7b: Insert Pre-Booking rows ใหม่ (@v_rn ต่อจาก Onetime)
    INSERT INTO tbl_product_offering_price
        (PO_ID, SRC_PO_ID, PO_NAME, PRICE_GROUP, PRICE_TYPE,
         EXC_VAT, INC_VAT, VAT_AMT, VAT_RATE,
         EFFECTIVE_DATE, EXPIRE_DATE, PRODUCT_ID,
         batch_id_insert, created_by, created_at)
    SELECT
        CONCAT(
            @v_of_prefix, '_',
            LPAD(@v_rn := @v_rn + 1, v_of_pad, '0')
        ),
        SRC_PO_ID,
        PO_NAME,
        PRICE_GROUP,
        PRICE_TYPE,
        EXC_VAT,
        INC_VAT,
        VAT_AMT,
        VAT_RATE,
        EFFECTIVE_DATE,
        EXPIRE_DATE,
        PRODUCT_ID,
        batch_id, v_actor, NOW(3)
    FROM tbl_prebooking_new_rows
    ORDER BY PO_NAME, PRICE_GROUP, EXC_VAT;

    COMMIT;

    -- Step 8: Create Views
    DROP VIEW IF EXISTS v_product_offering_price;
		CREATE VIEW v_product_offering_price AS
		SELECT
				CAST(PO_ID AS CHAR)                                                    AS `Product Offer Price ID`,
				CAST(PO_NAME AS CHAR)                                                  AS `Product Offer Price Name`,
				CAST(NULL AS CHAR)                                                     AS `externalID`,
				CAST(NULL AS CHAR)                                                     AS `description`,
				CAST(NULL AS CHAR)                                                     AS `Channels`,
				CAST(NULL AS CHAR)                                                     AS `Process Context`,
				CAST(NULL AS CHAR)                                                     AS `Market Segment`,
				CAST(VAT_AMT AS CHAR)                                                  AS `Tax`,
				CAST(NULL AS CHAR)                                                     AS `Place`,
				CAST(NULL AS CHAR)                                                     AS `Term`,
				CAST(NULL AS CHAR)                                                     AS `isBundle`,
				CAST(NULL AS CHAR)                                                     AS `isDownPaymentRequired`,
				CAST(NULL AS CHAR)                                                     AS `minimumDownPaymentAmount`,
				CAST(NULL AS CHAR)                                                     AS `isDefault`,
				CAST(PRICE_TYPE AS CHAR)                                               AS `priceType`,
				CAST(NULL AS CHAR)                                                     AS `recurringChargePeriodType`,
				CAST(NULL AS CHAR)                                                     AS `recurringChargePeriodLength`,
				'Baht'                                                                 AS `price_unit`,
				CAST(INC_VAT AS CHAR)                                                  AS `price_value`,
				'TRUE'                                                                 AS `isTaxIncluded`,
				CAST(NULL AS CHAR)                                                     AS `offset`,
				CAST(NULL AS CHAR)                                                     AS `percentage`,
				CAST(NULL AS CHAR)                                                     AS `unitOfMeasure_amount`,
				CAST(NULL AS CHAR)                                                     AS `unitOfMeasure_units`,
				CAST(
						DATE_FORMAT(
								EFFECTIVE_DATE,
								'%Y-%m-%dT%H:%i:%s.000Z'
						) AS CHAR
				)                                                                      AS `validFor_startDateTime`,
				CAST(
						DATE_FORMAT(
								COALESCE(EXPIRE_DATE, '2999-12-31 23:59:00'),
								'%Y-%m-%dT%H:%i:%s.000Z'
						) AS CHAR
				)                                                                      AS `validFor_endDateTime`
		FROM tbl_product_offering_price;


		DROP VIEW IF EXISTS v_product_offering_price_tax;
		CREATE VIEW v_product_offering_price_tax AS
		SELECT
				CAST(PO_ID AS CHAR)                                                    AS `POP_id`,
				CAST(VAT_RATE AS CHAR)                                                 AS `taxRate`,
				'Baht'                                                                 AS `taxAmount_unit`,
				CAST(VAT_AMT AS CHAR)                                                  AS `taxAmount_value`,
				'VAT'                                                                  AS `taxCategory`,
				CAST(NULL AS CHAR)                                                     AS `Action`
		FROM tbl_product_offering_price;


		DROP VIEW IF EXISTS v_product_offering_with_product_offering_price;
		CREATE VIEW v_product_offering_with_product_offering_price AS
		SELECT
				CAST(po.PO_ID AS CHAR)    AS `Product Offer ID`,
				CAST(pop.PO_NAME AS CHAR) AS `Product Offer Price Name`,
				CAST(pop.PO_ID AS CHAR)   AS `Product Offer Price ID`
		FROM tbl_product_offering_price pop
		JOIN JSON_TABLE(
				CONCAT('["', REPLACE(pop.SRC_PO_ID, ', ', '","'), '"]'),
				'$[*]' COLUMNS (src_po_id TEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci PATH '$')
		) jt ON TRUE
		LEFT JOIN tbl_product_offering po
				ON po.PO_ID COLLATE utf8mb4_general_ci = jt.src_po_id
		ORDER BY pop.PO_ID, po.rn IS NULL, po.rn;


		DROP VIEW IF EXISTS v_product_offering_variant_product_offering_price;
		CREATE VIEW v_product_offering_variant_product_offering_price AS
		SELECT
				CAST(pov.variantId AS CHAR)                                            AS `variantProductOfferingPrice.variantId`,
				CAST(pop.PO_ID AS CHAR)                                                AS `variantProductOfferingPrice.productOfferingPrice`
		FROM tbl_product_offering_price pop
		LEFT JOIN tbl_product_offering_variant pov
				ON FIND_IN_SET(pov.`Product Id`, REPLACE(pop.SRC_PO_ID, ', ', ',')) > 0
		ORDER BY pop.PO_ID, pov.variantId;

    -- Step 9: Return result
    SELECT *
    FROM v_product_offering_price
    ORDER BY `Product Offer Price ID`;

    SELECT *
    FROM v_product_offering_with_product_offering_price;

    SELECT *
    FROM v_product_offering_variant_product_offering_price;

END$$
DELIMITER ;