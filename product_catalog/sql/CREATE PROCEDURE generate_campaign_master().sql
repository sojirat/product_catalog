DELIMITER $$

DROP PROCEDURE IF EXISTS generate_campaign_master$$

CREATE PROCEDURE generate_campaign_master(
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

    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        RESIGNAL;
    END;

    SET v_actor = IFNULL(NULLIF(TRIM(p_created_by), ''), 'system');

    -- ============================================================
    -- STEP 1: CREATE TABLE
    -- ============================================================
		CREATE TABLE IF NOT EXISTS tbl_campaign_master (
				BM_ENTITY_TYPE        VARCHAR(255)  COLLATE utf8mb4_general_ci,
				META_EXTENSION_ID     VARCHAR(255)  COLLATE utf8mb4_general_ci,
				NAME                  TEXT          COLLATE utf8mb4_general_ci,
				EXTENSION_TYPE        VARCHAR(100)  COLLATE utf8mb4_general_ci,
				MARKET_SEGMENT        VARCHAR(255)  COLLATE utf8mb4_general_ci,
				CHANNELS              VARCHAR(255)  COLLATE utf8mb4_general_ci,
				LANGUAGES             VARCHAR(255)  COLLATE utf8mb4_general_ci,
				CAMPAIGN_GROUP_NAME   VARCHAR(255)  COLLATE utf8mb4_general_ci,
				CAMPAIGN_NAME         TEXT          COLLATE utf8mb4_general_ci,
				rn                    INT,
				batch_id_insert       INT,
				batch_id_update       INT,
				created_by            VARCHAR(255)  COLLATE utf8mb4_general_ci DEFAULT 'system',
				created_at            DATETIME(3)   DEFAULT NOW(3),
				updated_by            VARCHAR(255)  COLLATE utf8mb4_general_ci DEFAULT NULL,
				updated_at            DATETIME(3)   DEFAULT NULL,

				INDEX idx_name (NAME(255)),
				INDEX idx_rn (rn)
		) COLLATE utf8mb4_general_ci;

    -- ============================================================
    -- STEP 2: BUILD TEMP TABLE
    -- ============================================================
    -- STEP 2: BUILD TEMP TABLE
		DROP TEMPORARY TABLE IF EXISTS tmp_campaign_master;

		CREATE TEMPORARY TABLE tmp_campaign_master AS
		SELECT DISTINCT
				CAST('Master Extension' AS CHAR) COLLATE utf8mb4_general_ci    AS BM_ENTITY_TYPE,
				CONCAT(
						CAST(TP.CAMPAIGN   AS CHAR), ' ',
						CAST(TP.TRADE_NAME AS CHAR)
				) COLLATE utf8mb4_general_ci                                    AS NAME,
				CAST('campaignMaster' AS CHAR)   COLLATE utf8mb4_general_ci    AS EXTENSION_TYPE,
				CAST('Residence'      AS CHAR)   COLLATE utf8mb4_general_ci    AS MARKET_SEGMENT,
				CAST('All'            AS CHAR)   COLLATE utf8mb4_general_ci    AS CHANNELS,
				NULL                                                            AS LANGUAGES,
				CAST(TP.CAMPAIGN   AS CHAR)      COLLATE utf8mb4_general_ci    AS CAMPAIGN_GROUP_NAME,
				CAST(TP.TRADE_NAME AS CHAR)      COLLATE utf8mb4_general_ci    AS CAMPAIGN_NAME
		FROM tbl_promotion TP;

    -- ============================================================
    -- GUARD: NO DATA
    -- ============================================================
    IF NOT EXISTS (
        SELECT 1 FROM tmp_campaign_master LIMIT 1
    ) THEN
        SELECT 'No campaign master records found.' AS message;
        DROP TEMPORARY TABLE IF EXISTS tmp_campaign_master;
        LEAVE proc_label;
    END IF;

    -- ============================================================
    -- STEP 3: COUNT NEW RECORDS
    -- ============================================================
    SELECT COUNT(*)
    INTO v_new_count
    FROM tmp_campaign_master t
    WHERE NOT EXISTS (
        SELECT 1
        FROM tbl_campaign_master m
        WHERE m.NAME = t.NAME
    );

    SELECT IFNULL(MAX(rn), -1)
    INTO v_rn_offset
    FROM tbl_campaign_master;

    START TRANSACTION;

    -- ============================================================
    -- STEP 4: RESERVE SEQUENCE
    -- ============================================================
    IF v_new_count > 0 THEN

        CALL get_next_sequence_batch(
            'meta_extension-campaign_master',
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
    -- STEP 5A: INSERT NEW RECORDS
    -- ============================================================
    IF v_new_count > 0 THEN

        INSERT INTO tbl_campaign_master (
            BM_ENTITY_TYPE,
            META_EXTENSION_ID,
            NAME,
            EXTENSION_TYPE,
            MARKET_SEGMENT,
            CHANNELS,
            LANGUAGES,
            CAMPAIGN_GROUP_NAME,
            CAMPAIGN_NAME,
            rn,
            batch_id_insert,
            created_by,
            created_at
        )
        SELECT
            t.BM_ENTITY_TYPE,
            CONCAT(
                v_me_prefix,
                v_me_suffix,
                LPAD(@v_seq := @v_seq + 1, v_me_pad, '0')
            )                  AS META_EXTENSION_ID,
            t.NAME,
            t.EXTENSION_TYPE,
            t.MARKET_SEGMENT,
            t.CHANNELS,
            t.LANGUAGES,
            t.CAMPAIGN_GROUP_NAME,
            t.CAMPAIGN_NAME,
            @v_rn := @v_rn + 1 AS rn,
            batch_id,
            v_actor,
            NOW(3)

        FROM tmp_campaign_master t
        WHERE NOT EXISTS (
            SELECT 1
            FROM tbl_campaign_master m
            WHERE m.NAME = t.NAME
        )
        ORDER BY t.NAME;

    END IF;

    -- ============================================================
    -- STEP 5B: UPDATE EXISTING RECORDS
    -- ============================================================
    UPDATE tbl_campaign_master m
    JOIN tmp_campaign_master t
        ON m.NAME = t.NAME

    SET
        m.BM_ENTITY_TYPE      = t.BM_ENTITY_TYPE,
        m.EXTENSION_TYPE      = t.EXTENSION_TYPE,
        m.MARKET_SEGMENT      = t.MARKET_SEGMENT,
        m.CHANNELS            = t.CHANNELS,
        m.LANGUAGES           = t.LANGUAGES,
        m.CAMPAIGN_GROUP_NAME = t.CAMPAIGN_GROUP_NAME,
        m.CAMPAIGN_NAME       = t.CAMPAIGN_NAME,
        m.batch_id_update     = batch_id,
        m.updated_by          = v_actor,
        m.updated_at          = NOW(3)

    WHERE
        p_force_rerun = 1
        OR m.batch_id_insert <> batch_id
        OR m.batch_id_insert IS NULL;

    COMMIT;

    DROP TEMPORARY TABLE IF EXISTS tmp_campaign_master;
		
		
		-- ============================================================
		-- VIEW
		-- ============================================================
		DROP VIEW IF EXISTS v_master_meta_campaign_master;

		CREATE VIEW v_master_meta_campaign_master AS
		SELECT
				'Master Extension'        AS `BM Entity Type`,
				META_EXTENSION_ID         AS `MetaExtensionID`,
				`NAME`										AS `Name`,
				'campaignMaster'          AS `Extension Type`,
				'Residence'               AS `marketSegment`,
				'All'                     AS `Channels`,
				NULL                      AS `Languages`,
				CAMPAIGN_GROUP_NAME       AS `campaignGroupName`,
				CAMPAIGN_NAME             AS `campaignName`
		FROM tbl_campaign_master
		ORDER BY rn;

END proc_label$$

DELIMITER ;