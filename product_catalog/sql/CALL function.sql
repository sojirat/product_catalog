-- CALL generate_product_offering(); -- 1s
-- CALL generate_product_offering_char_value(); -- 4s
-- CALL generate_product_offering_variant_unpivot(); -- 230s***********
-- CALL generate_product_offering_variant(); -- 20s
-- CALL generate_product_offering_price(); -- 7s

-- CALL generate_all();

-- CALL load_product_mst('test-01','Milk')

UPDATE sequence_registry SET last_sequence = 0;

UPDATE PRODUCT_MST SET isGenerate = 0;

DROP TABLE IF EXISTS PRODUCT_MST;

DROP TABLE IF EXISTS tbl_product_offering;

DROP TABLE IF EXISTS tbl_product_offering_category;

DROP TABLE IF EXISTS tbl_product_offering_char_value;

DROP TABLE IF EXISTS tbl_product_offering_variant;

DROP TABLE IF EXISTS tbl_product_offering_variant_unpivot;

DROP TABLE IF EXISTS tbl_product_offering_price;

DROP TABLE IF EXISTS tbl_promotion;

DROP TABLE IF EXISTS tbl_contract_master;

-- -----------------------------------------------

DROP VIEW IF EXISTS v_product_offering;

DROP VIEW IF EXISTS v_product_offering_category;

DROP VIEW IF EXISTS v_product_offering_channel;

DROP VIEW IF EXISTS v_product_offering_char_value;

DROP VIEW IF EXISTS v_product_offering_market_segment;

DROP VIEW IF EXISTS v_product_offering_place;

DROP VIEW IF EXISTS v_product_offering_spec_characteristic;

DROP VIEW IF EXISTS v_product_offering_variant;

DROP VIEW IF EXISTS v_product_offering_price;

DROP VIEW IF EXISTS v_product_offering_price_tax;

DROP VIEW IF EXISTS v_promotion;

DROP VIEW IF EXISTS v_promotion_action;

DROP VIEW IF EXISTS v_extension_contract_master;

DROP VIEW IF EXISTS v_master_meta_campaign_master;

DROP VIEW IF EXISTS v_promotion_meta_extension_value;

-- -----------------------------------------------
DROP TABLE IF EXISTS generate_all_log;

DROP TABLE IF EXISTS ingest_batch_detail;

DROP TABLE IF EXISTS ingest_batch;

DROP VIEW IF EXISTS v_product_mst_audit;

DROP VIEW IF EXISTS v_product_mst_with_batch;

-- ------------------- RUN ----------------------------

-- CALL staging_and_batch_tables();
-- CALL load_product_mst('PRODUCT_MST_01', 'sojirat.s');