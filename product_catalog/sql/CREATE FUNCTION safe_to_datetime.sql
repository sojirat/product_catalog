DELIMITER $$

DROP FUNCTION IF EXISTS safe_to_datetime$$

CREATE FUNCTION safe_to_datetime(p_val TEXT)
RETURNS DATETIME
DETERMINISTIC
BEGIN
    DECLARE v_str  VARCHAR(50);
    DECLARE v_dt   DATETIME DEFAULT NULL;

    -- ตัด whitespace และ NULL/ว่าง
    SET v_str = NULLIF(TRIM(p_val), '');
    IF v_str IS NULL THEN
        RETURN NULL;
    END IF;

    -- ── Guard: time-only (HH:MM:SS หรือ HH:MM:SS.fff) → คืน NULL ─
    IF v_str REGEXP '^[0-9]{1,2}:[0-9]{2}:[0-9]{2}(\\.[0-9]+)?$' THEN
        RETURN NULL;
    END IF;

    -- ── Guard: ตัวเลขล้วนที่สั้นเกินไป → คืน NULL ───────────────
    IF v_str REGEXP '^[0-9]{1,7}$' THEN
        RETURN NULL;
    END IF;

    -- ── ISO / MySQL standard ──────────────────────────────────────

    -- '2020-01-08 00:00:00.000'  (with milliseconds)
    IF v_str REGEXP '^[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}\\.[0-9]+$' THEN
        SET v_dt = STR_TO_DATE(v_str, '%Y-%m-%d %H:%i:%s.%f');
        IF v_dt IS NOT NULL THEN RETURN v_dt; END IF;
    END IF;

    -- '2020-01-08 00:00:00'
    IF v_str REGEXP '^[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}$' THEN
        SET v_dt = STR_TO_DATE(v_str, '%Y-%m-%d %H:%i:%s');
        IF v_dt IS NOT NULL THEN RETURN v_dt; END IF;
    END IF;

    -- '2020-01-08T00:00:00.000'  (ISO-8601 with milliseconds)
    IF v_str REGEXP '^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\\.[0-9]+' THEN
        SET v_dt = STR_TO_DATE(v_str, '%Y-%m-%dT%H:%i:%s.%f');
        IF v_dt IS NOT NULL THEN RETURN v_dt; END IF;
    END IF;

    -- '2020-01-08T00:00:00'  (ISO-8601)
    IF v_str REGEXP '^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}$' THEN
        SET v_dt = STR_TO_DATE(v_str, '%Y-%m-%dT%H:%i:%s');
        IF v_dt IS NOT NULL THEN RETURN v_dt; END IF;
    END IF;

    -- '2020-01-08'
    IF v_str REGEXP '^[0-9]{4}-[0-9]{2}-[0-9]{2}$' THEN
        SET v_dt = STR_TO_DATE(v_str, '%Y-%m-%d');
        IF v_dt IS NOT NULL THEN RETURN v_dt; END IF;
    END IF;

    -- ── M/D/YYYY หรือ MM/DD/YYYY (Excel / Windows locale) ────────

    -- '1/8/2020 00:00:00.000'
    IF v_str REGEXP '^[0-9]{1,2}/[0-9]{1,2}/[0-9]{4} [0-9]{2}:[0-9]{2}:[0-9]{2}\\.[0-9]+$' THEN
        SET v_dt = STR_TO_DATE(v_str, '%m/%d/%Y %H:%i:%s.%f');
        IF v_dt IS NOT NULL THEN RETURN v_dt; END IF;
    END IF;

    -- '1/8/2020 00:00:00'
    IF v_str REGEXP '^[0-9]{1,2}/[0-9]{1,2}/[0-9]{4} [0-9]{2}:[0-9]{2}:[0-9]{2}$' THEN
        SET v_dt = STR_TO_DATE(v_str, '%m/%d/%Y %H:%i:%s');
        IF v_dt IS NOT NULL THEN RETURN v_dt; END IF;
    END IF;

    -- '1/8/2020'
    IF v_str REGEXP '^[0-9]{1,2}/[0-9]{1,2}/[0-9]{4}$' THEN
        SET v_dt = STR_TO_DATE(v_str, '%m/%d/%Y');
        IF v_dt IS NOT NULL THEN RETURN v_dt; END IF;
    END IF;

    -- ── DD-MM-YYYY (dash separator) ───────────────────────────────

    -- '08-01-2020 00:00:00.000'
    IF v_str REGEXP '^[0-9]{2}-[0-9]{2}-[0-9]{4} [0-9]{2}:[0-9]{2}:[0-9]{2}\\.[0-9]+$' THEN
        SET v_dt = STR_TO_DATE(v_str, '%d-%m-%Y %H:%i:%s.%f');
        IF v_dt IS NOT NULL THEN RETURN v_dt; END IF;
    END IF;

    -- '08-01-2020 00:00:00'
    IF v_str REGEXP '^[0-9]{2}-[0-9]{2}-[0-9]{4} [0-9]{2}:[0-9]{2}:[0-9]{2}$' THEN
        SET v_dt = STR_TO_DATE(v_str, '%d-%m-%Y %H:%i:%s');
        IF v_dt IS NOT NULL THEN RETURN v_dt; END IF;
    END IF;

    -- '08-01-2020'
    IF v_str REGEXP '^[0-9]{2}-[0-9]{2}-[0-9]{4}$' THEN
        SET v_dt = STR_TO_DATE(v_str, '%d-%m-%Y');
        IF v_dt IS NOT NULL THEN RETURN v_dt; END IF;
    END IF;

    -- ── Compact yyyymmdd ──────────────────────────────────────────

    -- '20200108'
    IF v_str REGEXP '^[0-9]{8}$' THEN
        SET v_dt = STR_TO_DATE(v_str, '%Y%m%d');
        IF v_dt IS NOT NULL THEN RETURN v_dt; END IF;
    END IF;

    -- ── รูปแบบที่ parse ไม่ได้เลย → คืน NULL แทน error ──────────
		
		-- '15/4/2020 00:59:59.000'  (DD/MM/YYYY with time + ms)
		IF v_str REGEXP '^[0-9]{1,2}/[0-9]{1,2}/[0-9]{4} [0-9]{1,2}:[0-9]{2}:[0-9]{2}\\.[0-9]+$' THEN
				SET v_dt = STR_TO_DATE(v_str, '%d/%m/%Y %H:%i:%s.%f');
				IF v_dt IS NOT NULL THEN RETURN v_dt; END IF;
		END IF;

		-- '15/4/2020 00:59:59'  (DD/MM/YYYY with time)
		IF v_str REGEXP '^[0-9]{1,2}/[0-9]{1,2}/[0-9]{4} [0-9]{1,2}:[0-9]{2}:[0-9]{2}$' THEN
				SET v_dt = STR_TO_DATE(v_str, '%d/%m/%Y %H:%i:%s');
				IF v_dt IS NOT NULL THEN RETURN v_dt; END IF;
		END IF;

		-- '15/4/2020'  (DD/MM/YYYY date only)
		IF v_str REGEXP '^[0-9]{1,2}/[0-9]{1,2}/[0-9]{4}$' THEN
				SET v_dt = STR_TO_DATE(v_str, '%d/%m/%Y');
				IF v_dt IS NOT NULL THEN RETURN v_dt; END IF;
		END IF;

    RETURN NULL;
END$$

DELIMITER ;