DELIMITER $$

DROP PROCEDURE IF EXISTS generate_allowed_airtime_installment$$

CREATE PROCEDURE generate_allowed_airtime_installment(
    IN batch_id INT,
    IN p_created_by VARCHAR(255),
    IN p_force_rerun TINYINT(1)
)

proc_label: BEGIN

    DECLARE v_ed_start   INT          DEFAULT 0;
    DECLARE v_ed_prefix  VARCHAR(50)  DEFAULT '';
    DECLARE v_ed_suffix  VARCHAR(50)  DEFAULT '';
    DECLARE v_ed_pad     INT          DEFAULT 6;

    DECLARE v_new_count  INT          DEFAULT 0;
    DECLARE v_rn_offset  INT          DEFAULT 0;
    DECLARE v_actor      VARCHAR(255) DEFAULT 'system';

    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        RESIGNAL;
    END;

    SET v_actor = IFNULL(NULLIF(TRIM(p_created_by), ''), 'system');

    -- ============================================================
    -- FIX: INCREASE GROUP_CONCAT LIMIT, SORT BUFFER & COLLATION
    -- ============================================================
    SET SESSION group_concat_max_len = 1000000;
    SET SESSION sort_buffer_size     = 8388608;
    SET NAMES utf8mb4 COLLATE utf8mb4_general_ci;

    -- ============================================================
    -- STEP 1: CREATE TABLE
    -- ============================================================
    CREATE TABLE IF NOT EXISTS tbl_allowed_airtime_installment (
        BM_ENTITY_TYPE                  VARCHAR(255)  COLLATE utf8mb4_general_ci,
        PROMOTION_ID                    VARCHAR(255)  COLLATE utf8mb4_general_ci,
        EXTENSION_NAME                  TEXT          COLLATE utf8mb4_general_ci,
        EXTENSION_TYPE                  VARCHAR(100)  COLLATE utf8mb4_general_ci,
        MARKET_SEGMENT                  VARCHAR(255)  COLLATE utf8mb4_general_ci,
        CHANNEL                         VARCHAR(255)  COLLATE utf8mb4_general_ci,
        LANGUAGES                       VARCHAR(255)  COLLATE utf8mb4_general_ci,
        IS_ALLOWED_AIRTIME_INSTALLMENT  VARCHAR(255)  COLLATE utf8mb4_general_ci,
        TRADE_PRODUCT_ID                MEDIUMTEXT    COLLATE utf8mb4_general_ci,  -- FIX: TEXT → MEDIUMTEXT
        TRADE_NO                        MEDIUMTEXT    COLLATE utf8mb4_general_ci,  -- FIX: TEXT → MEDIUMTEXT
        rn                              INT,
        batch_id_insert                 INT,
        batch_id_update                 INT,
        created_by                      VARCHAR(255)  COLLATE utf8mb4_general_ci DEFAULT 'system',
        created_at                      DATETIME(3)   DEFAULT NOW(3),
        updated_by                      VARCHAR(255)  COLLATE utf8mb4_general_ci DEFAULT NULL,
        updated_at                      DATETIME(3)   DEFAULT NULL,

        INDEX idx_promotion_id (PROMOTION_ID),
        INDEX idx_rn (rn)
    ) COLLATE utf8mb4_general_ci;

    -- ============================================================
    -- FIX: ALTER EXISTING TABLE (in case table already exists with TEXT columns)
    -- ============================================================
    ALTER TABLE tbl_allowed_airtime_installment
        MODIFY COLUMN TRADE_PRODUCT_ID  MEDIUMTEXT COLLATE utf8mb4_general_ci,
        MODIFY COLUMN TRADE_NO          MEDIUMTEXT COLLATE utf8mb4_general_ci;

    -- ============================================================
    -- STEP 2: BUILD TEMP TABLE
    -- ============================================================
    DROP TEMPORARY TABLE IF EXISTS tmp_allowed_airtime_installment;

    CREATE TEMPORARY TABLE tmp_allowed_airtime_installment
    COLLATE utf8mb4_general_ci
    AS
    SELECT DISTINCT
        CONVERT('Promotion Extension'         USING utf8mb4) COLLATE utf8mb4_general_ci  AS BM_ENTITY_TYPE,
        CONVERT('Allowed Airtime Installment' USING utf8mb4) COLLATE utf8mb4_general_ci  AS EXTENSION_NAME,
        CONVERT('allowedAirtimeInstallment'   USING utf8mb4) COLLATE utf8mb4_general_ci  AS EXTENSION_TYPE,
        CONVERT('Residence'                   USING utf8mb4) COLLATE utf8mb4_general_ci  AS MARKET_SEGMENT,
        CONVERT('All'                         USING utf8mb4) COLLATE utf8mb4_general_ci  AS CHANNEL,
        CONVERT(''                            USING utf8mb4) COLLATE utf8mb4_general_ci  AS LANGUAGES,
        CONVERT(
            CASE
                WHEN ASP_FLG = 'Y' THEN 'TRUE'
                ELSE 'FALSE'
            END
        USING utf8mb4) COLLATE utf8mb4_general_ci                                        AS IS_ALLOWED_AIRTIME_INSTALLMENT,
        CONVERT(
            GROUP_CONCAT(DISTINCT TRADE_PRODUCT_ID ORDER BY TRADE_PRODUCT_ID)
        USING utf8mb4) COLLATE utf8mb4_general_ci                                        AS TRADE_PRODUCT_ID,
        CONVERT(
            GROUP_CONCAT(DISTINCT TRADE_NO ORDER BY TRADE_NO)
        USING utf8mb4) COLLATE utf8mb4_general_ci                                        AS TRADE_NO
    FROM TR_PRODUCT
    WHERE CURRENT_DATE BETWEEN START_DATE AND END_DATE
    GROUP BY ASP_FLG;

    -- ============================================================
    -- GUARD: NO DATA
    -- ============================================================
    IF NOT EXISTS (
        SELECT 1
        FROM tmp_allowed_airtime_installment
        LIMIT 1
    ) THEN

        SELECT 'No active contract master found.' AS message;

        DROP TEMPORARY TABLE IF EXISTS tmp_allowed_airtime_installment;

        LEAVE proc_label;
    END IF;

    -- ============================================================
    -- STEP 3: COUNT NEW RECORDS
    -- ============================================================
    SELECT COUNT(*)
    INTO v_new_count
    FROM tmp_allowed_airtime_installment t
    WHERE NOT EXISTS (
        SELECT 1
        FROM tbl_allowed_airtime_installment e
        WHERE e.IS_ALLOWED_AIRTIME_INSTALLMENT = t.IS_ALLOWED_AIRTIME_INSTALLMENT
    );

    SELECT IFNULL(MAX(rn), -1)
    INTO v_rn_offset
    FROM tbl_allowed_airtime_installment;

    START TRANSACTION;

    -- ============================================================
    -- STEP 4: RESERVE SEQUENCE
    -- pattern = meta_extension
    -- ============================================================
    IF v_new_count > 0 THEN

        CALL get_next_sequence_batch(
            'meta_extension-allowed_airtime_installment',
            NULL,
            v_new_count,
            v_ed_start,
            @v_ed_end,
            @v_ed_prefix,
            @v_ed_suffix,
            @v_ed_pad
        );

        SET v_ed_prefix = IFNULL(@v_ed_prefix, '');
        SET v_ed_suffix = IFNULL(@v_ed_suffix, '');
        SET v_ed_pad    = IFNULL(@v_ed_pad, 6);

    END IF;

    SET @v_rn  = v_rn_offset;
    SET @v_seq = v_ed_start - 1;

    -- ============================================================
    -- STEP 5A: INSERT NEW RECORDS
    -- ============================================================
    IF v_new_count > 0 THEN

        INSERT INTO tbl_allowed_airtime_installment (
            BM_ENTITY_TYPE,
            PROMOTION_ID,
            EXTENSION_NAME,
            EXTENSION_TYPE,
            MARKET_SEGMENT,
            CHANNEL,
            LANGUAGES,
            IS_ALLOWED_AIRTIME_INSTALLMENT,
            TRADE_PRODUCT_ID,
            TRADE_NO,
            rn,
            batch_id_insert,
            created_by,
            created_at
        )

        SELECT
            t.BM_ENTITY_TYPE,
            CONVERT(CONCAT(
                v_ed_prefix,
                v_ed_suffix,
								LPAD(@v_seq := @v_seq + 1, v_ed_pad, '0')
            ) USING utf8mb4) COLLATE utf8mb4_general_ci  AS PROMOTION_ID,
            t.EXTENSION_NAME,
            t.EXTENSION_TYPE,
            t.MARKET_SEGMENT,
            t.CHANNEL,
            t.LANGUAGES,
            t.IS_ALLOWED_AIRTIME_INSTALLMENT,
            t.TRADE_PRODUCT_ID,
            t.TRADE_NO,
            @v_rn := @v_rn + 1                          AS rn,
            batch_id,
            v_actor,
            NOW(3)

        FROM tmp_allowed_airtime_installment t
        WHERE NOT EXISTS (
            SELECT 1
            FROM tbl_allowed_airtime_installment e
            WHERE e.IS_ALLOWED_AIRTIME_INSTALLMENT = t.IS_ALLOWED_AIRTIME_INSTALLMENT
        )
        ORDER BY t.IS_ALLOWED_AIRTIME_INSTALLMENT;

    END IF;

    -- ============================================================
    -- STEP 5B: UPDATE EXISTING RECORDS
    -- ============================================================
    UPDATE tbl_allowed_airtime_installment e
    JOIN tmp_allowed_airtime_installment t
        ON e.IS_ALLOWED_AIRTIME_INSTALLMENT = t.IS_ALLOWED_AIRTIME_INSTALLMENT

    SET
        e.BM_ENTITY_TYPE                 = t.BM_ENTITY_TYPE,
        e.EXTENSION_NAME                 = t.EXTENSION_NAME,
        e.EXTENSION_TYPE                 = t.EXTENSION_TYPE,
        e.MARKET_SEGMENT                 = t.MARKET_SEGMENT,
        e.CHANNEL                        = t.CHANNEL,
        e.LANGUAGES                      = t.LANGUAGES,
        e.IS_ALLOWED_AIRTIME_INSTALLMENT = t.IS_ALLOWED_AIRTIME_INSTALLMENT,
        e.TRADE_PRODUCT_ID               = t.TRADE_PRODUCT_ID,
        e.TRADE_NO                       = t.TRADE_NO,
        e.batch_id_update                = batch_id,
        e.updated_by                     = v_actor,
        e.updated_at                     = NOW(3)

    WHERE
        p_force_rerun = 1
        OR e.batch_id_insert <> batch_id
        OR e.batch_id_insert IS NULL;

    COMMIT;

    DROP TEMPORARY TABLE IF EXISTS tmp_allowed_airtime_installment;

    -- ============================================================
    -- STEP 6: CREATE VIEW
    -- ============================================================
    DROP VIEW IF EXISTS v_promotion_meta_ext_value_allowed_airtime_installment;

    CREATE VIEW v_promotion_meta_ext_value_allowed_airtime_installment AS
    SELECT
        CAST(BM_ENTITY_TYPE                 AS CHAR) AS `BM Entity Type`,
        CAST(PROMOTION_ID                   AS CHAR) AS `Promotion ID`,
        CAST(EXTENSION_NAME                 AS CHAR) AS `Name`,
        CAST(EXTENSION_TYPE                 AS CHAR) AS `Extension Type`,
        CAST(MARKET_SEGMENT                 AS CHAR) AS `marketSegment`,
        CAST(CHANNEL                        AS CHAR) AS `Channels`,
        CAST(LANGUAGES                      AS CHAR) AS `Languages`,
        CAST(IS_ALLOWED_AIRTIME_INSTALLMENT AS CHAR) AS `isAllowedAirtimeInstallment`
    FROM tbl_allowed_airtime_installment
    ORDER BY rn;

END proc_label$$

DELIMITER ;