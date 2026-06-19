DELIMITER $$

DROP PROCEDURE IF EXISTS generate_contract_master$$

CREATE PROCEDURE generate_contract_master(
    IN batch_id INT,
    IN p_created_by VARCHAR(255),
    IN p_force_rerun TINYINT(1)
)

proc_label: BEGIN

    DECLARE v_me_start   INT          DEFAULT 0;
    DECLARE v_me_prefix  VARCHAR(50)  DEFAULT '';
    DECLARE v_me_suffix  VARCHAR(50)  DEFAULT '';
    DECLARE v_me_pad     INT          DEFAULT 6;

    DECLARE v_new_count  INT          DEFAULT 0;
    DECLARE v_rn_offset  INT          DEFAULT 0;
    DECLARE v_actor      VARCHAR(255) DEFAULT 'system';
		
		DECLARE v_idx_exists INT DEFAULT 0;
		DECLARE v_idx_exists_pm INT DEFAULT 0;

    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        RESIGNAL;
    END;

    SET v_actor = IFNULL(NULLIF(TRIM(p_created_by), ''), 'system');

    -- ============================================================
    -- STEP 1: CREATE TABLE
    -- ============================================================
    CREATE TABLE IF NOT EXISTS tbl_contract_master (
				BM_ENTITY_TYPE_CONTRACT										VARCHAR(255),
				BM_ENTITY_TYPE_PROMOTION_METAEXT_VALUE		VARCHAR(255),
        META_EXTENSION_ID     VARCHAR(255),
        EXTENSION_NAME        TEXT,
        EXTENSION_TYPE        VARCHAR(100),
        MARKET_SEGMENT        VARCHAR(255),
        CHANNEL               VARCHAR(255),
        LANGUAGES             VARCHAR(255),
        PROFILE_TYPE          VARCHAR(100),
        CONTRACT_ID           BIGINT,
        CONTRACT_NAME         TEXT,
        COUNT_FLAG            VARCHAR(10),
        CONTRACT_RULE_ID      BIGINT,
        PENALTY_ID            BIGINT,
        PENALTY_CHARGE        DECIMAL(18,2),
        PENALTY_CHARGE_GROUP  VARCHAR(255),
				TRADE_DISCOUNT_ID			VARCHAR(255),
				TRADE_NO							VARCHAR(255),
				TRADE_PRODUCT_ID			VARCHAR(255),
				MAT_CODE							VARCHAR(255),
        rn                    INT,
        batch_id_insert       INT,
        batch_id_update       INT,
        created_by            VARCHAR(255) DEFAULT 'system',
        created_at            DATETIME(3) DEFAULT NOW(3),
        updated_by            VARCHAR(255) DEFAULT NULL,
        updated_at            DATETIME(3) DEFAULT NULL,

        INDEX idx_contract_id (CONTRACT_ID),
        INDEX idx_rn (rn)
    );

    -- ============================================================
    -- STEP 2: BUILD TEMP TABLE
    -- ============================================================
    DROP TEMPORARY TABLE IF EXISTS tmp_contract_master;

    CREATE TEMPORARY TABLE tmp_contract_master AS
    SELECT DISTINCT
				'Master Extension' AS BM_ENTITY_TYPE_CONTRACT,
				'Promotion Extension' AS BM_ENTITY_TYPE_PROMOTION_METAEXT_VALUE,
        CONCAT(
            CAST(CAST(TD.CONTRACT_ID AS SIGNED) AS CHAR),
            ' ',
            TD.CONTRACT_NAME,
            ' ',
            TD.PENALTY_CHARGE_GROUP
        ) AS EXTENSION_NAME,

        'contractDetail' AS EXTENSION_TYPE,
        '' AS MARKET_SEGMENT,
        '' AS CHANNEL,
        '' AS LANGUAGES,
        'Device' AS PROFILE_TYPE,

        CAST(TD.CONTRACT_ID AS SIGNED) AS CONTRACT_ID,
        TD.CONTRACT_NAME AS CONTRACT_NAME,

        CASE
            WHEN TD.COUNT_FLAG = 'Y' THEN 'TRUE'
            ELSE 'FALSE'
        END AS COUNT_FLAG,

        TD.CONTRACT_RULE_ID AS CONTRACT_RULE_ID,
        TD.PENALTY_ID AS PENALTY_ID,
        TD.DISCOUNT_EXC AS PENALTY_CHARGE,
        TD.PENALTY_CHARGE_GROUP AS PENALTY_CHARGE_GROUP,
				TD.TRADE_DISCOUNT_ID AS TRADE_DISCOUNT_ID,
				TD.TRADE_NO AS TRADE_NO,
				TD.TRADE_PRODUCT_ID AS TRADE_PRODUCT_ID,
				TP.MAT_CODE AS MAT_CODE

    FROM TR_DISCOUNT TD
		LEFT JOIN TR_PRODUCT TP ON TP.TRADE_PRODUCT_ID = TD.TRADE_PRODUCT_ID
    WHERE TD.CONTRACT_ID IS NOT NULL
      AND TD.END_DATE > NOW();

    -- ============================================================
    -- GUARD: NO DATA
    -- ============================================================
    IF NOT EXISTS (
        SELECT 1
        FROM tmp_contract_master
        LIMIT 1
    ) THEN

        SELECT 'No active contract master found.' AS message;

        DROP TEMPORARY TABLE IF EXISTS tmp_contract_master;

        LEAVE proc_label;
    END IF;

    -- ============================================================
    -- STEP 3: COUNT NEW RECORDS
    -- ============================================================
    SELECT COUNT(*)
    INTO v_new_count
    FROM tmp_contract_master t
    WHERE NOT EXISTS (
        SELECT 1
        FROM tbl_contract_master m
        WHERE m.CONTRACT_ID = t.CONTRACT_ID
    );

    SELECT IFNULL(MAX(rn), -1)
    INTO v_rn_offset
    FROM tbl_contract_master;

    START TRANSACTION;

    -- ============================================================
    -- STEP 4: RESERVE SEQUENCE
    -- pattern = meta_extension
    -- ============================================================
    IF v_new_count > 0 THEN

        CALL get_next_sequence_batch(
            'meta_extension-contract_master',
            NULL,
            v_new_count,
            v_me_start,
            @v_me_end,
            @v_me_prefix,
            @v_me_suffix,
            @v_me_pad
        );

        SET v_me_prefix = IFNULL(@v_me_prefix, '');
        SET v_me_suffix = IFNULL(@v_me_suffix, '');
        SET v_me_pad    = IFNULL(@v_me_pad, 6);

    END IF;

    SET @v_rn  = v_rn_offset;
    SET @v_seq = v_me_start - 1;

    -- ============================================================
    -- STEP 5A: INSERT NEW RECORD
    -- ============================================================
    IF v_new_count > 0 THEN

        INSERT INTO tbl_contract_master (
						BM_ENTITY_TYPE_CONTRACT,
						BM_ENTITY_TYPE_PROMOTION_METAEXT_VALUE,
            META_EXTENSION_ID,
            EXTENSION_NAME,
            EXTENSION_TYPE,
            MARKET_SEGMENT,
            CHANNEL,
            LANGUAGES,
            PROFILE_TYPE,
            CONTRACT_ID,
            CONTRACT_NAME,
            COUNT_FLAG,
            CONTRACT_RULE_ID,
            PENALTY_ID,
            PENALTY_CHARGE,
            PENALTY_CHARGE_GROUP,
						TRADE_DISCOUNT_ID,
						TRADE_NO,
						TRADE_PRODUCT_ID,
						MAT_CODE,
            rn,
            batch_id_insert,
            created_by,
            created_at
        )

        SELECT
						t.BM_ENTITY_TYPE_CONTRACT,
						t.BM_ENTITY_TYPE_PROMOTION_METAEXT_VALUE,
            CONCAT(
                v_me_prefix,
                v_me_suffix,
								LPAD(@v_seq := @v_seq + 1, v_me_pad, '0')
            ) AS META_EXTENSION_ID,
            t.EXTENSION_NAME,
            t.EXTENSION_TYPE,
            t.MARKET_SEGMENT,
            t.CHANNEL,
            t.LANGUAGES,
            t.PROFILE_TYPE,
            t.CONTRACT_ID,
            t.CONTRACT_NAME,
            t.COUNT_FLAG,
            t.CONTRACT_RULE_ID,
            t.PENALTY_ID,
            t.PENALTY_CHARGE,
            t.PENALTY_CHARGE_GROUP,
						t.TRADE_DISCOUNT_ID,
						t.TRADE_NO,
						t.TRADE_PRODUCT_ID,
						t.MAT_CODE,
            @v_rn := @v_rn + 1 AS rn,
            batch_id,
            v_actor,
            NOW(3)

        FROM tmp_contract_master t
        WHERE NOT EXISTS (
            SELECT 1
            FROM tbl_contract_master m
            WHERE m.CONTRACT_ID = t.CONTRACT_ID
        )
        ORDER BY t.CONTRACT_ID;

    END IF;

    -- ============================================================
    -- STEP 5B: UPDATE EXISTING RECORD
    -- ============================================================
    UPDATE tbl_contract_master m
    JOIN tmp_contract_master t
        ON m.CONTRACT_ID = t.CONTRACT_ID

    SET
				m.BM_ENTITY_TYPE_CONTRACT									= t.BM_ENTITY_TYPE_CONTRACT,
				m.BM_ENTITY_TYPE_PROMOTION_METAEXT_VALUE	= t.BM_ENTITY_TYPE_PROMOTION_METAEXT_VALUE,
        m.EXTENSION_NAME       = t.EXTENSION_NAME,
        m.EXTENSION_TYPE       = t.EXTENSION_TYPE,
        m.MARKET_SEGMENT       = t.MARKET_SEGMENT,
        m.CHANNEL              = t.CHANNEL,
        m.LANGUAGES            = t.LANGUAGES,
        m.PROFILE_TYPE         = t.PROFILE_TYPE,
        m.CONTRACT_NAME        = t.CONTRACT_NAME,
        m.COUNT_FLAG           = t.COUNT_FLAG,
        m.CONTRACT_RULE_ID     = t.CONTRACT_RULE_ID,
        m.PENALTY_ID           = t.PENALTY_ID,
        m.PENALTY_CHARGE       = t.PENALTY_CHARGE,
        m.PENALTY_CHARGE_GROUP = t.PENALTY_CHARGE_GROUP,
				m.TRADE_DISCOUNT_ID		 = t.TRADE_DISCOUNT_ID,
				m.TRADE_NO						 = t.TRADE_NO,
				m.TRADE_PRODUCT_ID		 = t.TRADE_PRODUCT_ID,
				m.MAT_CODE						 = t.MAT_CODE,
        m.batch_id_update      = batch_id,
        m.updated_by           = v_actor,
        m.updated_at           = NOW(3)

    WHERE
        p_force_rerun = 1
        OR m.batch_id_insert <> batch_id
        OR m.batch_id_insert IS NULL;

    COMMIT;

    DROP TEMPORARY TABLE IF EXISTS tmp_contract_master;

    -- ============================================================
    -- STEP 6: CREATE VIEW
    -- ============================================================
    DROP VIEW IF EXISTS v_master_meta_contract_master;
    CREATE VIEW v_master_meta_contract_master AS
    SELECT
				CAST(BM_ENTITY_TYPE_CONTRACT AS CHAR)    AS `BM Entity Type`,
        CAST(META_EXTENSION_ID AS CHAR)    AS `Meta Extension ID`,
        CAST(EXTENSION_NAME AS CHAR)       AS `Name`,
        'contractMaster'						       AS `Extension Type`,
       COALESCE(
						NULLIF(CAST(MARKET_SEGMENT AS CHAR CHARACTER SET utf8mb4), ''),
						'Residence'
				) AS `marketSegment`,
				COALESCE(
						NULLIF(TRIM(CAST(CHANNEL AS CHAR CHARACTER SET utf8mb4)), ''),
						'All'
				) AS `Channels`,
        CAST(LANGUAGES AS CHAR)            AS `Languages`,
        CAST(PROFILE_TYPE AS CHAR)         AS `profileType`,
        CAST(CONTRACT_ID AS CHAR)          AS `contractId`,
        CAST(CONTRACT_NAME AS CHAR)        AS `contractName`,
        CAST(COUNT_FLAG AS CHAR)           AS `countFlag`,
        CAST(CONTRACT_RULE_ID AS CHAR)     AS `contractRuleId`,
        CAST(PENALTY_ID AS CHAR)           AS `penaltyId`,
        CAST(PENALTY_CHARGE AS CHAR)       AS `penaltyCharge`,
        CAST(PENALTY_CHARGE_GROUP AS CHAR) AS `penaltyChargeGroup`
    FROM tbl_contract_master
    ORDER BY rn;

		-- idx_pm_end_contract_trade
		SELECT COUNT(*)
		INTO v_idx_exists
		FROM INFORMATION_SCHEMA.STATISTICS
		WHERE TABLE_SCHEMA = DATABASE()
			AND TABLE_NAME = 'tbl_product_mst'
			AND INDEX_NAME = 'idx_pm_end_contract_trade';

		IF v_idx_exists = 0 THEN

				SET @sql = '
						CREATE INDEX idx_pm_end_contract_trade
						ON tbl_product_mst (
								TD_END_DATE,
								TD_CONTRACT_ID,
								TD_TRADE_PRODUCT_ID
						)';

				PREPARE stmt FROM @sql;
				EXECUTE stmt;
				DEALLOCATE PREPARE stmt;

		END IF;


		-- idx_promotion_trade_no_rn
		SELECT COUNT(*)
		INTO v_idx_exists
		FROM INFORMATION_SCHEMA.STATISTICS
		WHERE TABLE_SCHEMA = DATABASE()
			AND TABLE_NAME = 'tbl_promotion'
			AND INDEX_NAME = 'idx_promotion_trade_no_rn';

		IF v_idx_exists = 0 THEN

				SET @sql = '
						CREATE INDEX idx_promotion_trade_no_rn
						ON tbl_promotion (
								TRADE_NO(10),
								rn
						)';

				PREPARE stmt FROM @sql;
				EXECUTE stmt;
				DEALLOCATE PREPARE stmt;

		END IF;

		DROP VIEW IF EXISTS v_promotion_meta_ext_value_contract_detail;
		CREATE VIEW v_promotion_meta_ext_value_contract_detail AS
		SELECT DISTINCT
				CM.BM_ENTITY_TYPE_PROMOTION_METAEXT_VALUE AS `BM Entity Type`,
				CAST(pmt.PROMOTION_ID AS CHAR) AS `Promotion ID`,
				CAST(pmt.PROMOTION_NAME AS CHAR) AS `Name`,
				'contractDetail' AS `Extension Type`,
				'Residence' AS `marketSegment`,
				'All' AS `Channels`,
				NULL AS `Languages`,
				PM.TD_DURATION_CONTRACT AS `durationContract`,
				'Continue' AS `contractType`,
				PM.TD_LIMIT_CONTRACT AS `limitContract`
		FROM (
				SELECT DISTINCT
						TRADE_NO,
						TRADE_PRODUCT_ID,
						BM_ENTITY_TYPE_PROMOTION_METAEXT_VALUE
				FROM tbl_contract_master
		) CM
		INNER JOIN (
				SELECT DISTINCT
						TD_TRADE_PRODUCT_ID,
						TD_DURATION_CONTRACT,
						TD_LIMIT_CONTRACT
				FROM tbl_product_mst
				WHERE TD_CONTRACT_ID IS NOT NULL
					AND TD_END_DATE > NOW()
		) PM
				ON PM.TD_TRADE_PRODUCT_ID = CM.TRADE_PRODUCT_ID
		INNER JOIN tbl_promotion pmt
				ON pmt.TRADE_NO = CM.TRADE_NO;
		
		/*
		SELECT
				`BM Entity Type`,
				`Promotion ID`,
				`Name`,
				`Extension Type`,
				`marketSegment`,
				`Channels`,
				`Languages`,
				`durationContract`,
				`contractType`,
				`limitContract`
		FROM (
				SELECT DISTINCT
						CM.BM_ENTITY_TYPE_PROMOTION_METAEXT_VALUE AS `BM Entity Type`,
						CAST(pmt.PROMOTION_ID AS CHAR)            AS `Promotion ID`,
						CAST(pmt.PROMOTION_NAME AS CHAR)          AS `Name`,
						'contractDetail'                          AS `Extension Type`,
						'Residence'                               AS `marketSegment`,
						'All'                                     AS `Channels`,
						NULL                                      AS `Languages`,
						TD.DURATION_CONTRACT                      AS `durationContract`,
						'Continue'                                AS `contractType`,
						TD.LIMIT_CONTRACT                         AS `limitContract`,
						pmt.rn
				FROM TR_DISCOUNT TD
				LEFT JOIN tbl_contract_master CM
						ON TD.TRADE_DISCOUNT_ID = CM.TRADE_DISCOUNT_ID
				INNER JOIN TR_PRODUCT tp
						ON CM.TRADE_PRODUCT_ID = tp.TRADE_PRODUCT_ID
				INNER JOIN PRODUCT_MST pm
						ON (tp.BRAND IS NULL OR tp.BRAND = '' OR tp.BRAND <=> pm.BRAND)
						AND (tp.MODEL IS NULL OR tp.MODEL = '' OR tp.MODEL <=> pm.MODEL)
						AND (tp.PRODUCT_TYPE IS NULL OR tp.PRODUCT_TYPE = '' OR tp.PRODUCT_TYPE <=> pm.PRODUCT_TYPE)
						AND (tp.PRODUCT_SUBTYPE IS NULL OR tp.PRODUCT_SUBTYPE = '' OR tp.PRODUCT_SUBTYPE <=> pm.PRODUCT_SUBTYPE)
						AND (tp.COLOR IS NULL OR tp.COLOR = '' OR tp.COLOR <=> pm.COLOR)
						AND (tp.MAT_CODE IS NULL OR tp.MAT_CODE = '' OR tp.MAT_CODE <=> pm.MAT_CODE)
				INNER JOIN tbl_promotion pmt
						ON pmt.SKU = pm.MAT_CODE
				WHERE TD.CONTRACT_ID IS NOT NULL
					AND TD.END_DATE > NOW()
		) sub
		ORDER BY rn;
		*/
		
		DROP VIEW IF EXISTS v_promotion_master_extension;
		CREATE VIEW v_promotion_master_extension AS
		SELECT
				CAST(cm.BM_ENTITY_TYPE_PROMOTION_METAEXT_VALUE AS CHAR) AS `BM Entity Type`,
				CAST(pmt.PROMOTION_ID AS CHAR) AS `Promotion ID`,
				CAST(cm.META_EXTENSION_ID AS CHAR) AS `MetaExtensionID`,
				CAST(cm.EXTENSION_NAME AS CHAR) AS `name`
		FROM tbl_contract_master cm
		INNER JOIN (
				SELECT DISTINCT
						TP_TRADE_PRODUCT_ID,
						PM_MAT_CODE
				FROM tbl_product_mst
		) tpm
				ON cm.TRADE_PRODUCT_ID = tpm.TP_TRADE_PRODUCT_ID
		INNER JOIN tbl_promotion pmt
				ON pmt.SKU = tpm.PM_MAT_CODE
		ORDER BY cm.rn;

		/*
    SELECT
				CAST(BM_ENTITY_TYPE_PROMOTION_METAEXT_VALUE AS CHAR)    AS `BM Entity Type`,
				CAST(pmt.PROMOTION_ID AS CHAR)		 AS `Promotion ID`,
        CAST(META_EXTENSION_ID AS CHAR)    AS `MetaExtensionID`,
				CAST(EXTENSION_NAME AS CHAR)       AS `name`
    FROM tbl_contract_master cm
		INNER JOIN TR_PRODUCT tp
				ON cm.TRADE_PRODUCT_ID = tp.TRADE_PRODUCT_ID
		INNER JOIN PRODUCT_MST pm
				ON (tp.BRAND IS NULL OR tp.BRAND = '' OR tp.BRAND <=> pm.BRAND)
				AND (tp.MODEL IS NULL OR tp.MODEL = '' OR tp.MODEL <=> pm.MODEL)
				AND (tp.PRODUCT_TYPE IS NULL OR tp.PRODUCT_TYPE = '' OR tp.PRODUCT_TYPE <=> pm.PRODUCT_TYPE)
				AND (tp.PRODUCT_SUBTYPE IS NULL OR tp.PRODUCT_SUBTYPE = '' OR tp.PRODUCT_SUBTYPE <=> pm.PRODUCT_SUBTYPE)
				AND (tp.COLOR IS NULL OR tp.COLOR = '' OR tp.COLOR <=> pm.COLOR)
				AND (tp.MAT_CODE IS NULL OR tp.MAT_CODE = '' OR tp.MAT_CODE <=> pm.MAT_CODE)
		INNER JOIN tbl_promotion pmt
				ON pmt.SKU = pm.MAT_CODE
		ORDER BY cm.rn;
		*/

END proc_label$$

DELIMITER ;