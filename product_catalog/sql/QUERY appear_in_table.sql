-- column ไหนไปอยู่ใน table ไหนบ้าง
SELECT
    c.COLUMN_NAME,
    GROUP_CONCAT(c.TABLE_NAME ORDER BY c.TABLE_NAME SEPARATOR ', ') AS appears_in_tables,
    COUNT(c.TABLE_NAME) AS table_count
FROM   INFORMATION_SCHEMA.COLUMNS c
WHERE  c.TABLE_SCHEMA = 'product_catalog'
GROUP  BY c.COLUMN_NAME
HAVING COUNT(c.TABLE_NAME) > 1
ORDER  BY table_count DESC, c.COLUMN_NAME;