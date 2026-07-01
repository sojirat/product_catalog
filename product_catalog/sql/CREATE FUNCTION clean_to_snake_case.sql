
DELIMITER $$
 
-- ===========================================================================
-- Helper function: convert any string to snake_case lowercase
-- "MetaExtension Promotion" → "meta_extension_promotion"
-- "MetaExtension PO"        → "meta_extension_po"
-- ===========================================================================
DROP FUNCTION IF EXISTS clean_to_snake_case$$
 
CREATE FUNCTION clean_to_snake_case(p_input TEXT)
RETURNS TEXT
DETERMINISTIC
BEGIN
    DECLARE v_result  TEXT DEFAULT '';
    DECLARE v_char    CHAR(1);
    DECLARE v_prev    CHAR(1) DEFAULT '';
    DECLARE v_next    CHAR(1) DEFAULT '';
    DECLARE i         INT DEFAULT 1;
    DECLARE v_len     INT;
 
    SET v_len = CHAR_LENGTH(TRIM(p_input));
 
    WHILE i <= v_len DO
        SET v_char = SUBSTRING(TRIM(p_input), i, 1);
        SET v_next = IF(i < v_len, SUBSTRING(TRIM(p_input), i + 1, 1), '');
 
        IF BINARY v_char REGEXP BINARY '[A-Z]' THEN
            -- ใส่ '_' ก่อน uppercase เมื่อ:
            -- กรณี 1: ตัวก่อนหน้าเป็น lowercase  (e.g. "nP" → "n_p")
            -- กรณี 2: ตัวก่อนหน้าเป็น uppercase และตัวถัดไปเป็น lowercase
            --          (e.g. "POw" → "p_ow" จาก "POWer" → "po_wer")
            --          แต่ "PO" ท้ายคำหรือตามด้วย space/พิเศษ → ไม่ใส่ '_'
            IF (BINARY v_prev REGEXP BINARY '[a-z]')
            OR (BINARY v_prev REGEXP BINARY '[A-Z]' AND BINARY v_next REGEXP BINARY '[a-z]')
            THEN
                IF v_result <> '' AND RIGHT(v_result, 1) <> '_' THEN
                    SET v_result = CONCAT(v_result, '_');
                END IF;
            END IF;
            SET v_result = CONCAT(v_result, LOWER(v_char));
 
        ELSEIF BINARY v_char REGEXP BINARY '[a-z0-9]' THEN
            SET v_result = CONCAT(v_result, v_char);
 
        ELSE
            -- space, dash, dot ฯลฯ → '_' (ไม่ซ้ำ)
            IF v_result <> '' AND RIGHT(v_result, 1) <> '_' THEN
                SET v_result = CONCAT(v_result, '_');
            END IF;
        END IF;
 
        SET v_prev = v_char;
        SET i = i + 1;
    END WHILE;
 
    -- ตัด trailing underscore
    IF RIGHT(v_result, 1) = '_' THEN
        SET v_result = LEFT(v_result, LENGTH(v_result) - 1);
    END IF;
 
    RETURN v_result;
END$$