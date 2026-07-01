-- ============================================================
-- STEP 1: PO
-- ============================================================

-- UPDATE tbl_product_offering tpo
-- JOIN tbl_product_offering_copy1 tpc
--     ON tpo.rn = tpc.rn
-- SET tpo.PO_ID_ORIGINAL = tpc.PO_ID;

-- UPDATE tbl_product_offering_category tpc
-- JOIN tbl_product_offering tpo
--     ON tpc.PO_ID = tpo.PO_ID_ORIGINAL
-- SET tpc.PO_ID = tpo.PO_ID
-- WHERE tpo.PO_ID REGEXP '[ก-๙]';

-- Query Time: 160.459s
-- UPDATE tbl_product_offering_char_value tpocv
-- JOIN tbl_product_offering tpo
--     ON tpocv.`Char Value.Product Offer ID` = tpo.PO_ID_ORIGINAL
-- SET tpocv.`Char Value.Product Offer ID` = tpo.PO_ID
-- WHERE tpocv.`Char Value.Product Offer ID` REGEXP '[ก-๙]';

-- UPDATE tbl_product_offering_price tpop
-- JOIN tbl_product_offering tpo
--     ON tpop.SRC_PO_ID = tpo.PO_ID_ORIGINAL
-- SET tpop.SRC_PO_ID = tpo.PO_ID
-- WHERE tpop.SRC_PO_ID REGEXP '[ก-๙]';

-- UPDATE tbl_product_offering_variant tpov
-- JOIN tbl_product_offering tpo
--     ON tpov.`Product Id` = tpo.PO_ID_ORIGINAL
-- SET tpov.`Product Id` = tpo.PO_ID
-- WHERE tpov.`Product Id` REGEXP '[ก-๙]';

-- UPDATE tbl_product_offering_variant_unpivot tpovu
-- JOIN tbl_product_offering tpo
--     ON tpovu.`Product ID` = tpo.PO_ID_ORIGINAL
-- SET tpovu.`Product ID` = tpo.PO_ID
-- WHERE tpovu.`Product ID` REGEXP '[ก-๙]';

-- Query Time: 457.459s
-- UPDATE tbl_promotion tp
-- JOIN tbl_product_offering tpo
--     ON tp.PRODUCT_OFFER_ID = tpo.PO_ID_ORIGINAL
-- SET tp.PRODUCT_OFFER_ID = tpo.PO_ID
-- WHERE tp.PRODUCT_OFFER_ID REGEXP '[ก-๙]';