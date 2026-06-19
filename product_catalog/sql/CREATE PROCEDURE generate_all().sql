DELIMITER $$

DROP PROCEDURE IF EXISTS generate_all$$

CREATE PROCEDURE generate_all()
BEGIN
    DECLARE v_start      DATETIME(3);
    DECLARE v_step_start DATETIME(3);
    DECLARE v_step       INT DEFAULT 0;
    DECLARE v_log_id     INT DEFAULT 0;
    DECLARE v_error      VARCHAR(500);

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

    -- สร้าง log table ถ้ายังไม่มี
    CREATE TABLE IF NOT EXISTS generate_all_log (
        id              INT AUTO_INCREMENT PRIMARY KEY,
        step            INT,
        step_name       VARCHAR(100),
        status          VARCHAR(20),
        duration_sec    DECIMAL(12,3),
        error_message   TEXT,
        created_at      DATETIME(3)
    );

    SET v_start = NOW(3);

    -- Step 1 generate_product_offering
    SET v_step = 1;
    SET v_step_start = NOW(3);
    INSERT INTO generate_all_log (step, step_name, status, created_at)
    VALUES (1, 'generate_product_offering', 'RUNNING', NOW(3));
    SET v_log_id = LAST_INSERT_ID();

    CALL generate_product_offering();

    UPDATE generate_all_log
    SET status       = 'SUCCESS',
        duration_sec = TIMESTAMPDIFF(MICROSECOND, v_step_start, NOW(3)) / 1000000
    WHERE id = v_log_id;

    -- Step 2 generate_product_offering_char_value
    SET v_step = 2;
    SET v_step_start = NOW(3);
    INSERT INTO generate_all_log (step, step_name, status, created_at)
    VALUES (2, 'generate_product_offering_char_value', 'RUNNING', NOW(3));
    SET v_log_id = LAST_INSERT_ID();

    CALL generate_product_offering_char_value();

    UPDATE generate_all_log
    SET status       = 'SUCCESS',
        duration_sec = TIMESTAMPDIFF(MICROSECOND, v_step_start, NOW(3)) / 1000000
    WHERE id = v_log_id;

    -- Step 3 generate_product_offering_variant_unpivot
    SET v_step = 3;
    SET v_step_start = NOW(3);
    INSERT INTO generate_all_log (step, step_name, status, created_at)
    VALUES (3, 'generate_product_offering_variant_unpivot', 'RUNNING', NOW(3));
    SET v_log_id = LAST_INSERT_ID();

		CALL generate_product_offering_variant_unpivot();

    UPDATE generate_all_log
    SET status       = 'SUCCESS',
        duration_sec = TIMESTAMPDIFF(MICROSECOND, v_step_start, NOW(3)) / 1000000
    WHERE id = v_log_id;

    -- Step 4 generate_product_offering_variant
    SET v_step = 4;
    SET v_step_start = NOW(3);
    INSERT INTO generate_all_log (step, step_name, status, created_at)
    VALUES (4, 'generate_product_offering_variant', 'RUNNING', NOW(3));
    SET v_log_id = LAST_INSERT_ID();

    CALL generate_product_offering_variant();

    UPDATE generate_all_log
    SET status       = 'SUCCESS',
        duration_sec = TIMESTAMPDIFF(MICROSECOND, v_step_start, NOW(3)) / 1000000
    WHERE id = v_log_id;

	-- Step 5 generate_product_offering_price
			SET v_step = 5;
			SET v_step_start = NOW(3);
			INSERT INTO generate_product_offering_price (step, step_name, status, created_at)
			VALUES (5, 'generate_product_offering_price', 'RUNNING', NOW(3));
			SET v_log_id = LAST_INSERT_ID();

			CALL generate_product_offering_price();

			UPDATE generate_all_log
			SET status       = 'SUCCESS',
					duration_sec = TIMESTAMPDIFF(MICROSECOND, v_step_start, NOW(3)) / 1000000
			WHERE id = v_log_id;
		
    -- Summary
    SELECT
        step,
        step_name,
        status,
        CONCAT(FORMAT(duration_sec, 3), ' sec') AS duration,
        error_message,
        created_at
    FROM generate_all_log
    WHERE created_at >= v_start
    ORDER BY step;

    SELECT CONCAT(FORMAT(TIMESTAMPDIFF(MICROSECOND, v_start, NOW(3)) / 1000000, 3), ' sec') AS total_duration;

END$$

DELIMITER ;