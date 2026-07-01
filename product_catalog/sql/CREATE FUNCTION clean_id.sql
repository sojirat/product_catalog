DELIMITER $$

DROP FUNCTION IF EXISTS clean_id$$

CREATE FUNCTION clean_id(val TEXT)
RETURNS TEXT DETERMINISTIC

	BEGIN
			DECLARE v TEXT;

			SET v = IFNULL(val, '');

			-- ลบสระ/วรรณยุกต์ที่ขึ้นต้น
			SET v = REGEXP_REPLACE(v, '^\\p{M}+', '');

			-- แปลงเลขไทยเป็นเลขอารบิก
			SET v = REPLACE(v, '๐', '0');
			SET v = REPLACE(v, '๑', '1');
			SET v = REPLACE(v, '๒', '2');
			SET v = REPLACE(v, '๓', '3');
			SET v = REPLACE(v, '๔', '4');
			SET v = REPLACE(v, '๕', '5');
			SET v = REPLACE(v, '๖', '6');
			SET v = REPLACE(v, '๗', '7');
			SET v = REPLACE(v, '๘', '8');
			SET v = REPLACE(v, '๙', '9');

			-- เปลี่ยน space/-/_ เป็น _
			SET v = REGEXP_REPLACE(v, '[[:space:]_-]+', '_');

			-- ลบอักขระพิเศษ
			SET v = REGEXP_REPLACE(v, '[^\\p{L}\\p{M}\\p{N}_]', '');

			-- รวม _ ให้เหลือตัวเดียว
			SET v = REGEXP_REPLACE(v, '_+', '_');

			-- ลบ _ หน้า/ท้าย
			SET v = REGEXP_REPLACE(v, '^_|_$', '');
			
			-- ลบ อักขระที่ไม่ควรขึ้นต้นคำ
			SET v = REGEXP_REPLACE(v, '^[ะัำิีึืุู็่้๊๋์]+', '');

			RETURN LOWER(v);

	END$$

DELIMITER ;