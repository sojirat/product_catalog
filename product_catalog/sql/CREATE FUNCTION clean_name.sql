DELIMITER $$
DROP FUNCTION
IF EXISTS clean_name$$ CREATE FUNCTION clean_name (val TEXT) RETURNS TEXT DETERMINISTIC
	BEGIN
		RETURN NULLIF(
        REGEXP_REPLACE(
            REGEXP_REPLACE(
                REGEXP_REPLACE(
                    REGEXP_REPLACE(
                        IFNULL(val, ''),
                        '[[:space:]_-]+', '_'
                    ),
                    '[^\\p{L}\\p{N}_]', ''
                ),
                '_+', '_'
            ),
            '^_|_$', ''
        ),
        ''
    );
	END $$
	DELIMITER;