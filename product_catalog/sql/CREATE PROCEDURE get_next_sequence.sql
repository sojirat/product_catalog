DELIMITER $$

DROP PROCEDURE IF EXISTS get_next_sequence$$
CREATE PROCEDURE get_next_sequence(
    IN  p_pattern   VARCHAR(100),
    IN  p_name      VARCHAR(500),
    OUT p_result    VARCHAR(700)
)
BEGIN
    DECLARE v_prefix       VARCHAR(50);
    DECLARE v_suffix       VARCHAR(50);
    DECLARE v_padding      INT;
    DECLARE v_next_seq     INT;
    DECLARE v_start_default INT;

    SELECT prefix, suffix, padding, last_sequence, IFNULL(start_default, 0)
    INTO   v_prefix, v_suffix, v_padding, v_next_seq, v_start_default
    FROM   sequence_registry
    WHERE  pattern = p_pattern
    FOR UPDATE;

    IF v_next_seq < v_start_default THEN
        SET v_next_seq = v_start_default;
    END IF;

    SET v_next_seq = v_next_seq + 1;

    UPDATE sequence_registry
    SET    last_sequence = v_next_seq,
           last_used_at  = NOW()
    WHERE  pattern = p_pattern;

    SET p_result = CASE
        WHEN v_prefix IS NOT NULL AND p_name IS NULL
            THEN CONCAT(v_prefix, LPAD(v_next_seq, v_padding, '0'))
        WHEN v_suffix IS NOT NULL AND p_name IS NOT NULL
            THEN CONCAT(p_name, v_suffix, LPAD(v_next_seq, v_padding, '0'))
        ELSE
            CONCAT(IFNULL(v_prefix,''), IFNULL(p_name,''), LPAD(v_next_seq, v_padding, '0'), IFNULL(v_suffix,''))
    END;
END$$

DROP PROCEDURE IF EXISTS get_next_sequence_batch$$
CREATE PROCEDURE get_next_sequence_batch(
    IN  p_pattern   VARCHAR(100),
    IN  p_name      VARCHAR(500),
    IN  p_count     INT,
    OUT p_start     INT,
    OUT p_end       INT,
    OUT p_prefix    VARCHAR(50),
    OUT p_suffix    VARCHAR(50),
    OUT p_padding   INT
)
BEGIN
    DECLARE v_current_seq   INT;
    DECLARE v_start_default INT;

    SELECT last_sequence, prefix, suffix, padding, IFNULL(start_default, 0)
    INTO   v_current_seq, p_prefix, p_suffix, p_padding, v_start_default
    FROM   sequence_registry
    WHERE  pattern = p_pattern
    FOR UPDATE;

    IF v_current_seq < v_start_default THEN
        SET v_current_seq = v_start_default;
    END IF;

    SET p_start = v_current_seq + 1;
    SET p_end   = v_current_seq + p_count;

    UPDATE sequence_registry
    SET    last_sequence = p_end,
           last_used_at  = NOW()
    WHERE  pattern = p_pattern;

END$$

DELIMITER ;