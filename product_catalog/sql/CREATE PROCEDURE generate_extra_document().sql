DELIMITER $$

DROP PROCEDURE IF EXISTS generate_extra_document$$

CREATE PROCEDURE generate_extra_document(
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
    -- FIX: INCREASE GROUP_CONCAT LIMIT
    -- ============================================================
    SET SESSION group_concat_max_len = 1000000;

    -- ============================================================
    -- STEP 1: CREATE TABLE
    -- ============================================================
    CREATE TABLE IF NOT EXISTS tbl_extra_document (
        BM_ENTITY_TYPE        VARCHAR(255),
        PROMOTION_ID          VARCHAR(255),
        EXTENSION_NAME        TEXT,
        EXTENSION_TYPE        VARCHAR(100),
        MARKET_SEGMENT        VARCHAR(255),
        CHANNEL               VARCHAR(255),
        LANGUAGES             VARCHAR(255),
        DOCUMENT_NAME         TEXT,
        TRADE_PRODUCT_ID      TEXT,
        TRADE_NO              TEXT,
        rn                    INT,
        batch_id_insert       INT,
        batch_id_update       INT,
        created_by            VARCHAR(255) DEFAULT 'system',
        created_at            DATETIME(3) DEFAULT NOW(3),
        updated_by            VARCHAR(255) DEFAULT NULL,
        updated_at            DATETIME(3) DEFAULT NULL,

        INDEX idx_promotion_id (PROMOTION_ID),
        INDEX idx_rn (rn)
    );

    -- ============================================================
    -- STEP 2: BUILD TEMP TABLE
    -- ============================================================
    DROP TEMPORARY TABLE IF EXISTS tmp_extra_document;

    CREATE TEMPORARY TABLE tmp_extra_document AS
    SELECT DISTINCT
        'Promotion Extension'                                                   AS BM_ENTITY_TYPE,
        'Extra Document'                                                        AS EXTENSION_NAME,
        'extraDocument'                                                         AS EXTENSION_TYPE,
        'Residence'                                                             AS MARKET_SEGMENT,
        'All'                                                                   AS CHANNEL,
        ''                                                                      AS LANGUAGES,
        tc.CRITERIA_VALUE                                                       AS DOCUMENT_NAME,
        GROUP_CONCAT(DISTINCT tp.TRADE_PRODUCT_ID ORDER BY tp.TRADE_PRODUCT_ID) AS TRADE_PRODUCT_ID,
        GROUP_CONCAT(DISTINCT tp.TRADE_NO ORDER BY tp.TRADE_NO)                 AS TRADE_NO
    FROM TR_PRODUCT tp
    LEFT JOIN tr_mst tm
        ON tm.TRADE_NO = tp.TRADE_NO
    LEFT JOIN TR_CRITERIA tc
        ON tc.TRADE_NO = tp.TRADE_NO
    WHERE tc.CRITERIA_TYPE = 'extraDoc'
    GROUP BY tc.CRITERIA_VALUE;

    -- ============================================================
    -- GUARD: NO DATA
    -- ============================================================
    IF NOT EXISTS (
        SELECT 1
        FROM tmp_extra_document
        LIMIT 1
    ) THEN

        SELECT 'No active contract master found.' AS message;

        DROP TEMPORARY TABLE IF EXISTS tmp_extra_document;

        LEAVE proc_label;
    END IF;

    -- ============================================================
    -- STEP 3: COUNT NEW RECORDS
    -- ============================================================
    SELECT COUNT(*)
    INTO v_new_count
    FROM tmp_extra_document t
    WHERE NOT EXISTS (
        SELECT 1
        FROM tbl_extra_document e
        WHERE e.DOCUMENT_NAME = t.DOCUMENT_NAME
    );

    SELECT IFNULL(MAX(rn), -1)
    INTO v_rn_offset
    FROM tbl_extra_document;

    START TRANSACTION;

    -- ============================================================
    -- STEP 4: RESERVE SEQUENCE
    -- pattern = meta_extension
    -- ============================================================
    IF v_new_count > 0 THEN

        CALL get_next_sequence_batch(
            'meta_extension-extra_document',
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

        INSERT INTO tbl_extra_document (
            BM_ENTITY_TYPE,
            PROMOTION_ID,
            EXTENSION_NAME,
            EXTENSION_TYPE,
            MARKET_SEGMENT,
            CHANNEL,
            LANGUAGES,
            DOCUMENT_NAME,
            TRADE_PRODUCT_ID,
            TRADE_NO,
            rn,
            batch_id_insert,
            created_by,
            created_at
        )

        SELECT
            t.BM_ENTITY_TYPE,
            CONCAT(
                v_ed_prefix,
                v_ed_suffix,
								LPAD(@v_seq := @v_seq + 1, v_ed_pad, '0')
            )                    AS PROMOTION_ID,
            t.EXTENSION_NAME,
            t.EXTENSION_TYPE,
            t.MARKET_SEGMENT,
            t.CHANNEL,
            t.LANGUAGES,
            t.DOCUMENT_NAME,
            t.TRADE_PRODUCT_ID,
            t.TRADE_NO,
            @v_rn := @v_rn + 1  AS rn,
            batch_id,
            v_actor,
            NOW(3)

        FROM tmp_extra_document t
        WHERE NOT EXISTS (
            SELECT 1
            FROM tbl_extra_document e
            WHERE e.DOCUMENT_NAME = t.DOCUMENT_NAME
        )
        ORDER BY t.DOCUMENT_NAME;

    END IF;

    -- ============================================================
    -- STEP 5B: UPDATE EXISTING RECORDS
    -- ============================================================
    UPDATE tbl_extra_document e
    JOIN tmp_extra_document t
        ON e.DOCUMENT_NAME = t.DOCUMENT_NAME

    SET
        e.BM_ENTITY_TYPE      = t.BM_ENTITY_TYPE,
        e.EXTENSION_NAME      = t.EXTENSION_NAME,
        e.EXTENSION_TYPE      = t.EXTENSION_TYPE,
        e.MARKET_SEGMENT      = t.MARKET_SEGMENT,
        e.CHANNEL             = t.CHANNEL,
        e.LANGUAGES           = t.LANGUAGES,
        e.DOCUMENT_NAME       = t.DOCUMENT_NAME,
        e.TRADE_PRODUCT_ID    = t.TRADE_PRODUCT_ID,
        e.TRADE_NO            = t.TRADE_NO,
        e.batch_id_update     = batch_id,
        e.updated_by          = v_actor,
        e.updated_at          = NOW(3)

    WHERE
        p_force_rerun = 1
        OR e.batch_id_insert <> batch_id
        OR e.batch_id_insert IS NULL;

    COMMIT;

    DROP TEMPORARY TABLE IF EXISTS tmp_extra_document;

    -- ============================================================
    -- STEP 6: CREATE VIEW
    -- ============================================================
    DROP VIEW IF EXISTS v_promotion_meta_ext_value_extra_document;

    CREATE VIEW v_promotion_meta_ext_value_extra_document AS
    SELECT
        CAST(BM_ENTITY_TYPE  AS CHAR)   AS `BM Entity Type`,
        CAST(PROMOTION_ID    AS CHAR)   AS `Promotion ID`,
        CAST(EXTENSION_NAME  AS CHAR)   AS `Name`,
        CAST(EXTENSION_TYPE  AS CHAR)   AS `Extension Type`,
        CAST(MARKET_SEGMENT  AS CHAR)   AS `marketSegment`,
        CAST(CHANNEL         AS CHAR)   AS `Channels`,
        CAST(LANGUAGES       AS CHAR)   AS `Languages`,
        CAST(DOCUMENT_NAME   AS CHAR)   AS `documentName`
    FROM tbl_extra_document
    ORDER BY rn;

END proc_label$$

DELIMITER ;