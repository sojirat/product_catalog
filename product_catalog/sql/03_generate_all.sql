-- =============================================================================
-- FILE: 03_generate_all.sql
-- PURPOSE: generate_all() รับ p_triggered_by เพื่อบันทึกว่าใครสั่ง
--          ถ้าเรียกจาก load_product_mst() → ส่งชื่อต่อมาอัตโนมัติ
--          ถ้าเรียกเอง manual → ระบุชื่อหรือ NULL (ใช้ 'system')
--
-- HOW TO USE:
--   -- เรียก manual ระบุชื่อ
--   CALL generate_all(NULL, 'somchai.k');
--
--   -- เรียก manual ไม่ระบุชื่อ
--   CALL generate_all(NULL, NULL);
--
--   -- เรียกจาก load_product_mst() → batch_id + ชื่อส่งต่อมาอัตโนมัติ
-- =============================================================================

DELIMITER $$

DROP PROCEDURE IF EXISTS generate_all$$

CREATE PROCEDURE generate_all(
    IN p_batch_id       INT,            -- NULL = run ทุก step (manual)
    IN p_triggered_by   VARCHAR(255)    -- NULL = 'system'
)
BEGIN
    DECLARE v_start         DATETIME(3);
    DECLARE v_step_start    DATETIME(3);
    DECLARE v_log_id        INT DEFAULT 0;
    DECLARE v_actor         VARCHAR(255);
    DECLARE v_error         VARCHAR(500);

    DECLARE v_run_offering  				TINYINT DEFAULT 0;
    DECLARE v_run_charval   				TINYINT DEFAULT 0;
    DECLARE v_run_variant   				TINYINT DEFAULT 0;
    DECLARE v_run_price     				TINYINT DEFAULT 0;
		DECLARE v_run_promotion    			TINYINT DEFAULT 0;
		DECLARE v_run_contract_master		TINYINT DEFAULT 0;

    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        GET DIAGNOSTICS CONDITION 1 v_error = MESSAGE_TEXT;
        UPDATE generate_all_log
        SET status        = 'ERROR',
            duration_sec  = TIMESTAMPDIFF(MICROSECOND, v_step_start, NOW(3)) / 1000000,
            error_message = v_error
        WHERE id = v_log_id;
        RESIGNAL;
    END;

    SET v_actor = IFNULL(NULLIF(TRIM(p_triggered_by), ''), 'system');
    SET v_start = NOW(3);

    -- สร้าง log table ถ้ายังไม่มี
    CREATE TABLE IF NOT EXISTS generate_all_log (
        id              INT AUTO_INCREMENT PRIMARY KEY,
        batch_id        INT,
        step            INT,
        step_name       VARCHAR(100),
        status          VARCHAR(20),
        duration_sec    DECIMAL(12,3),
        error_message   TEXT,
        triggered_by    VARCHAR(255)    DEFAULT 'system',   -- ← ชื่อคน
        triggered_at    DATETIME(3),                        -- ← เวลา
        created_at      DATETIME(3),
        INDEX idx_gal_batch (batch_id),
        INDEX idx_gal_actor (triggered_by)
    );

    -- ----------------------------------------------------------------
    -- ตรวจ downstream flags
    -- ----------------------------------------------------------------
    IF p_batch_id IS NULL THEN
        SET v_run_offering 					= 1;
        SET v_run_charval  					= 1;
        SET v_run_variant  					= 1;
        SET v_run_price    					= 1;
				SET v_run_promotion					=	1;
				SET v_run_contract_master	= 1;
    ELSE
        SELECT
            MAX(needs_offering),
            MAX(needs_offering),
            MAX(needs_variant),
            MAX(needs_price),
						MAX(needs_promotion),
						MAX(needs_contract_master)
        INTO v_run_offering, v_run_charval, v_run_variant, v_run_price, v_run_promotion, v_run_contract_master
        FROM ingest_batch_detail
        WHERE batch_id = p_batch_id
          AND action IN ('INSERT','UPDATE');

        IF v_run_offering = 1 THEN SET v_run_charval = 1; END IF;
    END IF;

    -- ================================================================
    -- helper macro: INSERT log row
    --   เก็บ triggered_by + triggered_at ทุก step
    -- ================================================================

    -- STEP 1
    IF v_run_offering = 1 THEN
        SET v_step_start = NOW(3);
        INSERT INTO generate_all_log
            (batch_id, step, step_name, status, triggered_by, triggered_at, created_at)
        VALUES
            (p_batch_id, 1, 'generate_product_offering', 'RUNNING', v_actor, NOW(3), NOW(3));
        SET v_log_id = LAST_INSERT_ID();

        CALL generate_product_offering(p_batch_id, v_actor);

        UPDATE generate_all_log
        SET status       = 'SUCCESS',
            duration_sec = TIMESTAMPDIFF(MICROSECOND, v_step_start, NOW(3)) / 1000000
        WHERE id = v_log_id;
    ELSE
        INSERT INTO generate_all_log
            (batch_id, step, step_name, status, duration_sec, triggered_by, triggered_at, created_at)
        VALUES (p_batch_id, 1, 'generate_product_offering', 'SKIPPED', 0, v_actor, NOW(3), NOW(3));
    END IF;

    -- STEP 2
    IF v_run_charval = 1 THEN
        SET v_step_start = NOW(3);
        INSERT INTO generate_all_log
            (batch_id, step, step_name, status, triggered_by, triggered_at, created_at)
        VALUES
            (p_batch_id, 2, 'generate_product_offering_char_value', 'RUNNING', v_actor, NOW(3), NOW(3));
        SET v_log_id = LAST_INSERT_ID();

        CALL generate_product_offering_char_value(p_batch_id, v_actor);

        UPDATE generate_all_log
        SET status       = 'SUCCESS',
            duration_sec = TIMESTAMPDIFF(MICROSECOND, v_step_start, NOW(3)) / 1000000
        WHERE id = v_log_id;
    ELSE
        INSERT INTO generate_all_log
            (batch_id, step, step_name, status, duration_sec, triggered_by, triggered_at, created_at)
        VALUES (p_batch_id, 2, 'generate_product_offering_char_value', 'SKIPPED', 0, v_actor, NOW(3), NOW(3));
    END IF;

    -- STEP 3
    IF v_run_variant = 1 THEN
        SET v_step_start = NOW(3);
        INSERT INTO generate_all_log
            (batch_id, step, step_name, status, triggered_by, triggered_at, created_at)
        VALUES
            (p_batch_id, 3, 'generate_product_offering_variant_unpivot', 'RUNNING', v_actor, NOW(3), NOW(3));
        SET v_log_id = LAST_INSERT_ID();

        CALL generate_product_offering_variant_unpivot();

        UPDATE generate_all_log
        SET status       = 'SUCCESS',
            duration_sec = TIMESTAMPDIFF(MICROSECOND, v_step_start, NOW(3)) / 1000000
        WHERE id = v_log_id;
    ELSE
        INSERT INTO generate_all_log
            (batch_id, step, step_name, status, duration_sec, triggered_by, triggered_at, created_at)
        VALUES (p_batch_id, 3, 'generate_product_offering_variant_unpivot', 'SKIPPED', 0, v_actor, NOW(3), NOW(3));
    END IF;

    -- STEP 4
    IF v_run_variant = 1 THEN
        SET v_step_start = NOW(3);
        INSERT INTO generate_all_log
            (batch_id, step, step_name, status, triggered_by, triggered_at, created_at)
        VALUES
            (p_batch_id, 4, 'generate_product_offering_variant', 'RUNNING', v_actor, NOW(3), NOW(3));
        SET v_log_id = LAST_INSERT_ID();

        CALL generate_product_offering_variant(p_batch_id, v_actor);

        UPDATE generate_all_log
        SET status       = 'SUCCESS',
            duration_sec = TIMESTAMPDIFF(MICROSECOND, v_step_start, NOW(3)) / 1000000
        WHERE id = v_log_id;
    ELSE
        INSERT INTO generate_all_log
            (batch_id, step, step_name, status, duration_sec, triggered_by, triggered_at, created_at)
        VALUES (p_batch_id, 4, 'generate_product_offering_variant', 'SKIPPED', 0, v_actor, NOW(3), NOW(3));
    END IF;

    -- STEP 5
    IF v_run_price = 1 THEN
        SET v_step_start = NOW(3);
        INSERT INTO generate_all_log
            (batch_id, step, step_name, status, triggered_by, triggered_at, created_at)
        VALUES
            (p_batch_id, 5, 'generate_product_offering_price', 'RUNNING', v_actor, NOW(3), NOW(3));
        SET v_log_id = LAST_INSERT_ID();

        CALL generate_product_offering_price(p_batch_id, v_actor);

        UPDATE generate_all_log
        SET status       = 'SUCCESS',
            duration_sec = TIMESTAMPDIFF(MICROSECOND, v_step_start, NOW(3)) / 1000000
        WHERE id = v_log_id;
    ELSE
        INSERT INTO generate_all_log
            (batch_id, step, step_name, status, duration_sec, triggered_by, triggered_at, created_at)
        VALUES (p_batch_id, 5, 'generate_product_offering_price', 'SKIPPED', 0, v_actor, NOW(3), NOW(3));
    END IF;
		
		-- STEP 6
    IF v_run_promotion = 1 THEN
        SET v_step_start = NOW(3);
        INSERT INTO generate_all_log
            (batch_id, step, step_name, status, triggered_by, triggered_at, created_at)
        VALUES
            (p_batch_id, 6, 'generate_promotion', 'RUNNING', v_actor, NOW(3), NOW(3));
        SET v_log_id = LAST_INSERT_ID();

        CALL generate_promotion(p_batch_id, v_actor, 0);

        UPDATE generate_all_log
        SET status       = 'SUCCESS',
            duration_sec = TIMESTAMPDIFF(MICROSECOND, v_step_start, NOW(3)) / 1000000
        WHERE id = v_log_id;
    ELSE
        INSERT INTO generate_all_log
            (batch_id, step, step_name, status, duration_sec, triggered_by, triggered_at, created_at)
        VALUES (p_batch_id, 6, 'generate_promotion', 'SKIPPED', 0, v_actor, NOW(3), NOW(3));
    END IF;
		
				-- STEP 7
    IF v_run_contract_master = 1 THEN
        SET v_step_start = NOW(3);
        INSERT INTO generate_all_log
            (batch_id, step, step_name, status, triggered_by, triggered_at, created_at)
        VALUES
            (p_batch_id, 7, 'generate_contract_master', 'RUNNING', v_actor, NOW(3), NOW(3));
        SET v_log_id = LAST_INSERT_ID();

        CALL generate_contract_master(p_batch_id, v_actor, 0);

        UPDATE generate_all_log
        SET status       = 'SUCCESS',
            duration_sec = TIMESTAMPDIFF(MICROSECOND, v_step_start, NOW(3)) / 1000000
        WHERE id = v_log_id;
    ELSE
        INSERT INTO generate_all_log
            (batch_id, step, step_name, status, duration_sec, triggered_by, triggered_at, created_at)
        VALUES (p_batch_id, 7, 'generate_contract_master', 'SKIPPED', 0, v_actor, NOW(3), NOW(3));
    END IF;
		

    -- Summary
    SELECT
        step,
        step_name,
        status,
        CONCAT(FORMAT(duration_sec, 3), ' sec')     AS duration,
        triggered_by,
        triggered_at,
        error_message
    FROM generate_all_log
    WHERE created_at >= v_start
      AND (batch_id = p_batch_id OR p_batch_id IS NULL)
    ORDER BY step;

    SELECT CONCAT(FORMAT(TIMESTAMPDIFF(MICROSECOND, v_start, NOW(3)) / 1000000, 3), ' sec')
        AS total_duration;

END$$

DELIMITER ;
