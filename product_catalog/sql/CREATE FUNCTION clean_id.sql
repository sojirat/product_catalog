DELIMITER $$
DROP FUNCTION
IF EXISTS clean_id$$ CREATE FUNCTION clean_id (val TEXT) RETURNS TEXT DETERMINISTIC
	BEGIN
		RETURN LOWER(
			REGEXP_REPLACE (
				REGEXP_REPLACE (REGEXP_REPLACE (REGEXP_REPLACE (IFNULL(val, ''), '[[:space:]_-]+', '_'), '[^\\p{L}\\p{N}_]', ''), '_+', '_'),
				'^_|_$',
				''
			)
		);
	END $$
	DELIMITER;