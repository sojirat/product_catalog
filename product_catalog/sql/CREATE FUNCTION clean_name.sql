DELIMITER $$
DROP FUNCTION
IF EXISTS clean_name$$ CREATE FUNCTION clean_name (val TEXT) RETURNS TEXT DETERMINISTIC
	BEGIN
		RETURN NULLIF(
        REGEXP_REPLACE(
            REGEXP_REPLACE(
                REGEXP_REPLACE(
                    IFNULL(val, ''),
                    '[[:space:]_-]+',
                    '_'
                ),
                '[^0-9A-Za-z_ก-๙]',
                ''
            ),
            '^_|_$',
            ''
        ),
        ''
    );
	END $$
	DELIMITER;