DELIMITER $$
DROP FUNCTION
IF EXISTS clean_name_raw$$ CREATE FUNCTION clean_name_raw (val TEXT) RETURNS TEXT DETERMINISTIC
	BEGIN
     RETURN NULLIF(
			REGEXP_REPLACE(
					TRIM(
							REGEXP_REPLACE(
									REGEXP_REPLACE(
											REGEXP_REPLACE(
													IFNULL(val, ''),
													'^[ะัำิีึืุู็่้๊๋์]+',
													''
											),
											'[[:space:]]+',
											' '
									),
									'_+',
									'_'
							)
					),
					'^-+$',
					''
			),
			''
	);
	END $$
	DELIMITER;