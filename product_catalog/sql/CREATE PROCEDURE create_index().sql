DROP PROCEDURE IF EXISTS create_index;

DELIMITER $$
CREATE PROCEDURE create_index(IN p_table_name VARCHAR(100))
BEGIN
    DECLARE v_msg VARCHAR(200);

    -- ===== char_value =====
    IF p_table_name = 'char_value' THEN
        IF NOT EXISTS (SELECT 1 FROM information_schema.STATISTICS
                       WHERE table_schema = DATABASE() AND table_name = 'char_value' AND index_name = 'idx_cv_spec') THEN
            CREATE INDEX idx_cv_spec ON char_value(`Spec ID`);
            SELECT 'char_value: idx_cv_spec created.' AS message;
        ELSE SELECT 'char_value: idx_cv_spec already exists.' AS message; END IF;

        IF NOT EXISTS (SELECT 1 FROM information_schema.STATISTICS
                       WHERE table_schema = DATABASE() AND table_name = 'char_value' AND index_name = 'idx_cv_spec_char') THEN
            CREATE INDEX idx_cv_spec_char ON char_value(`Spec ID`, `Characteristics ID`);
            SELECT 'char_value: idx_cv_spec_char created.' AS message;
        ELSE SELECT 'char_value: idx_cv_spec_char already exists.' AS message; END IF;
    END IF;

    -- ===== ingest_batch =====
    IF p_table_name = 'ingest_batch' THEN
        IF NOT EXISTS (SELECT 1 FROM information_schema.STATISTICS
                       WHERE table_schema = DATABASE() AND table_name = 'ingest_batch' AND index_name = 'idx_batch_actor') THEN
            CREATE INDEX idx_batch_actor ON ingest_batch(created_by);
            SELECT 'ingest_batch: idx_batch_actor created.' AS message;
        ELSE SELECT 'ingest_batch: idx_batch_actor already exists.' AS message; END IF;

        IF NOT EXISTS (SELECT 1 FROM information_schema.STATISTICS
                       WHERE table_schema = DATABASE() AND table_name = 'ingest_batch' AND index_name = 'idx_batch_started') THEN
            CREATE INDEX idx_batch_started ON ingest_batch(started_at);
            SELECT 'ingest_batch: idx_batch_started created.' AS message;
        ELSE SELECT 'ingest_batch: idx_batch_started already exists.' AS message; END IF;

        IF NOT EXISTS (SELECT 1 FROM information_schema.STATISTICS
                       WHERE table_schema = DATABASE() AND table_name = 'ingest_batch' AND index_name = 'idx_batch_status') THEN
            CREATE INDEX idx_batch_status ON ingest_batch(status);
            SELECT 'ingest_batch: idx_batch_status created.' AS message;
        ELSE SELECT 'ingest_batch: idx_batch_status already exists.' AS message; END IF;
    END IF;

    -- ===== ingest_batch_detail =====
    IF p_table_name = 'ingest_batch_detail' THEN
        IF NOT EXISTS (SELECT 1 FROM information_schema.STATISTICS
                       WHERE table_schema = DATABASE() AND table_name = 'ingest_batch_detail' AND index_name = 'idx_detail_action') THEN
            CREATE INDEX idx_detail_action ON ingest_batch_detail(batch_id, action);
            SELECT 'ingest_batch_detail: idx_detail_action created.' AS message;
        ELSE SELECT 'ingest_batch_detail: idx_detail_action already exists.' AS message; END IF;

        IF NOT EXISTS (SELECT 1 FROM information_schema.STATISTICS
                       WHERE table_schema = DATABASE() AND table_name = 'ingest_batch_detail' AND index_name = 'idx_detail_batch') THEN
            CREATE INDEX idx_detail_batch ON ingest_batch_detail(batch_id);
            SELECT 'ingest_batch_detail: idx_detail_batch created.' AS message;
        ELSE SELECT 'ingest_batch_detail: idx_detail_batch already exists.' AS message; END IF;

        IF NOT EXISTS (SELECT 1 FROM information_schema.STATISTICS
                       WHERE table_schema = DATABASE() AND table_name = 'ingest_batch_detail' AND index_name = 'idx_detail_pid') THEN
            CREATE INDEX idx_detail_pid ON ingest_batch_detail(PRODUCT_ID);
            SELECT 'ingest_batch_detail: idx_detail_pid created.' AS message;
        ELSE SELECT 'ingest_batch_detail: idx_detail_pid already exists.' AS message; END IF;
    END IF;

    -- ===== PRICE_MST =====
    IF p_table_name = 'PRICE_MST' THEN
        IF NOT EXISTS (SELECT 1 FROM information_schema.STATISTICS
                       WHERE table_schema = DATABASE() AND table_name = 'PRICE_MST' AND index_name = 'IDX_RM_PRODUCT') THEN
            CREATE INDEX IDX_RM_PRODUCT ON PRICE_MST(PRODUCT_ID);
            SELECT 'PRICE_MST: IDX_RM_PRODUCT created.' AS message;
        ELSE SELECT 'PRICE_MST: IDX_RM_PRODUCT already exists.' AS message; END IF;
    END IF;

    -- ===== PRODUCT_MST =====
    IF p_table_name = 'PRODUCT_MST' THEN
        IF NOT EXISTS (SELECT 1 FROM information_schema.STATISTICS
                       WHERE table_schema = DATABASE() AND table_name = 'PRODUCT_MST' AND index_name = 'idx_stg_pid') THEN
            CREATE INDEX idx_stg_pid ON PRODUCT_MST(PRODUCT_ID);
            SELECT 'PRODUCT_MST: idx_stg_pid created.' AS message;
        ELSE SELECT 'PRODUCT_MST: idx_stg_pid already exists.' AS message; END IF;
    END IF;

    -- ===== product_type_mapping =====
    IF p_table_name = 'product_type_mapping' THEN
        IF NOT EXISTS (SELECT 1 FROM information_schema.STATISTICS
                       WHERE table_schema = DATABASE() AND table_name = 'product_type_mapping' AND index_name = 'idx_type_subtype') THEN
            CREATE INDEX idx_type_subtype ON product_type_mapping(PRODUCT_TYPE, PRODUCT_SUB_TYPE);
            SELECT 'product_type_mapping: idx_type_subtype created.' AS message;
        ELSE SELECT 'product_type_mapping: idx_type_subtype already exists.' AS message; END IF;
    END IF;

    -- ===== tbl_campaign_master =====
    IF p_table_name = 'tbl_campaign_master' THEN
        IF NOT EXISTS (SELECT 1 FROM information_schema.STATISTICS
                       WHERE table_schema = DATABASE() AND table_name = 'tbl_campaign_master' AND index_name = 'idx_name') THEN
            CREATE INDEX idx_name ON tbl_campaign_master(NAME);
            SELECT 'tbl_campaign_master: idx_name created.' AS message;
        ELSE SELECT 'tbl_campaign_master: idx_name already exists.' AS message; END IF;

        IF NOT EXISTS (SELECT 1 FROM information_schema.STATISTICS
                       WHERE table_schema = DATABASE() AND table_name = 'tbl_campaign_master' AND index_name = 'idx_rn') THEN
            CREATE INDEX idx_rn ON tbl_campaign_master(rn);
            SELECT 'tbl_campaign_master: idx_rn created.' AS message;
        ELSE SELECT 'tbl_campaign_master: idx_rn already exists.' AS message; END IF;
    END IF;

    -- ===== tbl_contract_master =====
    IF p_table_name = 'tbl_contract_master' THEN
        IF NOT EXISTS (SELECT 1 FROM information_schema.STATISTICS
                       WHERE table_schema = DATABASE() AND table_name = 'tbl_contract_master' AND index_name = 'idx_contract_id') THEN
            CREATE INDEX idx_contract_id ON tbl_contract_master(CONTRACT_ID);
            SELECT 'tbl_contract_master: idx_contract_id created.' AS message;
        ELSE SELECT 'tbl_contract_master: idx_contract_id already exists.' AS message; END IF;

        IF NOT EXISTS (SELECT 1 FROM information_schema.STATISTICS
                       WHERE table_schema = DATABASE() AND table_name = 'tbl_contract_master' AND index_name = 'idx_rn') THEN
            CREATE INDEX idx_rn ON tbl_contract_master(rn);
            SELECT 'tbl_contract_master: idx_rn created.' AS message;
        ELSE SELECT 'tbl_contract_master: idx_rn already exists.' AS message; END IF;
    END IF;

    -- ===== tbl_product_mst =====
    IF p_table_name = 'tbl_product_mst' THEN
        IF NOT EXISTS (SELECT 1 FROM information_schema.STATISTICS
                       WHERE table_schema = DATABASE() AND table_name = 'tbl_product_mst' AND index_name = 'idx_pm_contract') THEN
            CREATE INDEX idx_pm_contract ON tbl_product_mst(TD_CONTRACT_ID);
            SELECT 'tbl_product_mst: idx_pm_contract created.' AS message;
        ELSE SELECT 'tbl_product_mst: idx_pm_contract already exists.' AS message; END IF;

        IF NOT EXISTS (SELECT 1 FROM information_schema.STATISTICS
                       WHERE table_schema = DATABASE() AND table_name = 'tbl_product_mst' AND index_name = 'idx_pm_contract_end') THEN
            CREATE INDEX idx_pm_contract_end ON tbl_product_mst(TD_CONTRACT_ID, TD_END_DATE);
            SELECT 'tbl_product_mst: idx_pm_contract_end created.' AS message;
        ELSE SELECT 'tbl_product_mst: idx_pm_contract_end already exists.' AS message; END IF;

        IF NOT EXISTS (SELECT 1 FROM information_schema.STATISTICS
                       WHERE table_schema = DATABASE() AND table_name = 'tbl_product_mst' AND index_name = 'idx_pm_end_contract_trade') THEN
            CREATE INDEX idx_pm_end_contract_trade ON tbl_product_mst(TD_END_DATE, TD_CONTRACT_ID, TD_TRADE_PRODUCT_ID);
            SELECT 'tbl_product_mst: idx_pm_end_contract_trade created.' AS message;
        ELSE SELECT 'tbl_product_mst: idx_pm_end_contract_trade already exists.' AS message; END IF;

        IF NOT EXISTS (SELECT 1 FROM information_schema.STATISTICS
                       WHERE table_schema = DATABASE() AND table_name = 'tbl_product_mst' AND index_name = 'idx_pm_end_date') THEN
            CREATE INDEX idx_pm_end_date ON tbl_product_mst(TD_END_DATE);
            SELECT 'tbl_product_mst: idx_pm_end_date created.' AS message;
        ELSE SELECT 'tbl_product_mst: idx_pm_end_date already exists.' AS message; END IF;

        IF NOT EXISTS (SELECT 1 FROM information_schema.STATISTICS
                       WHERE table_schema = DATABASE() AND table_name = 'tbl_product_mst' AND index_name = 'idx_pm_trade_contract_end') THEN
            CREATE INDEX idx_pm_trade_contract_end ON tbl_product_mst(TD_TRADE_PRODUCT_ID, TD_CONTRACT_ID, TD_END_DATE);
            SELECT 'tbl_product_mst: idx_pm_trade_contract_end created.' AS message;
        ELSE SELECT 'tbl_product_mst: idx_pm_trade_contract_end already exists.' AS message; END IF;

        IF NOT EXISTS (SELECT 1 FROM information_schema.STATISTICS
                       WHERE table_schema = DATABASE() AND table_name = 'tbl_product_mst' AND index_name = 'idx_pm_trade_product') THEN
            CREATE INDEX idx_pm_trade_product ON tbl_product_mst(TD_TRADE_PRODUCT_ID);
            SELECT 'tbl_product_mst: idx_pm_trade_product created.' AS message;
        ELSE SELECT 'tbl_product_mst: idx_pm_trade_product already exists.' AS message; END IF;
    END IF;

    -- ===== tbl_product_offering =====
    IF p_table_name = 'tbl_product_offering' THEN
        IF NOT EXISTS (SELECT 1 FROM information_schema.STATISTICS
                       WHERE table_schema = DATABASE() AND table_name = 'tbl_product_offering' AND index_name = 'idx_po_name_type') THEN
            CREATE UNIQUE INDEX idx_po_name_type ON tbl_product_offering(PO_NAME, PRODUCT_LINE, PRODUCT_TYPE);
            SELECT 'tbl_product_offering: idx_po_name_type created.' AS message;
        ELSE SELECT 'tbl_product_offering: idx_po_name_type already exists.' AS message; END IF;

        IF NOT EXISTS (SELECT 1 FROM information_schema.STATISTICS
                       WHERE table_schema = DATABASE() AND table_name = 'tbl_product_offering' AND index_name = 'idx_rn') THEN
            CREATE INDEX idx_rn ON tbl_product_offering(rn);
            SELECT 'tbl_product_offering: idx_rn created.' AS message;
        ELSE SELECT 'tbl_product_offering: idx_rn already exists.' AS message; END IF;
    END IF;

    -- ===== tbl_product_offering_char_value =====
    IF p_table_name = 'tbl_product_offering_char_value' THEN
        IF NOT EXISTS (SELECT 1 FROM information_schema.STATISTICS
                       WHERE table_schema = DATABASE() AND table_name = 'tbl_product_offering_char_value' AND index_name = 'idx_snap_char') THEN
            CREATE INDEX idx_snap_char ON tbl_product_offering_char_value(`Char Value.Product Offer Characteristics ID`);
            SELECT 'tbl_product_offering_char_value: idx_snap_char created.' AS message;
        ELSE SELECT 'tbl_product_offering_char_value: idx_snap_char already exists.' AS message; END IF;

        IF NOT EXISTS (SELECT 1 FROM information_schema.STATISTICS
                       WHERE table_schema = DATABASE() AND table_name = 'tbl_product_offering_char_value' AND index_name = 'idx_snap_po') THEN
            CREATE INDEX idx_snap_po ON tbl_product_offering_char_value(`Char Value.Product Offer ID`);
            SELECT 'tbl_product_offering_char_value: idx_snap_po created.' AS message;
        ELSE SELECT 'tbl_product_offering_char_value: idx_snap_po already exists.' AS message; END IF;
    END IF;

    -- ===== tbl_product_offering_price =====
    IF p_table_name = 'tbl_product_offering_price' THEN
        IF NOT EXISTS (SELECT 1 FROM information_schema.STATISTICS
                       WHERE table_schema = DATABASE() AND table_name = 'tbl_product_offering_price' AND index_name = 'idx_po_id') THEN
            CREATE INDEX idx_po_id ON tbl_product_offering_price(PO_ID);
            SELECT 'tbl_product_offering_price: idx_po_id created.' AS message;
        ELSE SELECT 'tbl_product_offering_price: idx_po_id already exists.' AS message; END IF;

        IF NOT EXISTS (SELECT 1 FROM information_schema.STATISTICS
                       WHERE table_schema = DATABASE() AND table_name = 'tbl_product_offering_price' AND index_name = 'idx_src_key') THEN
            CREATE INDEX idx_src_key ON tbl_product_offering_price(SRC_PO_ID, PRICE_GROUP, EXC_VAT);
            SELECT 'tbl_product_offering_price: idx_src_key created.' AS message;
        ELSE SELECT 'tbl_product_offering_price: idx_src_key already exists.' AS message; END IF;
    END IF;

    -- ===== tbl_product_offering_variant =====
    IF p_table_name = 'tbl_product_offering_variant' THEN
        IF NOT EXISTS (SELECT 1 FROM information_schema.STATISTICS
                       WHERE table_schema = DATABASE() AND table_name = 'tbl_product_offering_variant' AND index_name = 'idx_pid') THEN
            CREATE INDEX idx_pid ON tbl_product_offering_variant(`Product Id`);
            SELECT 'tbl_product_offering_variant: idx_pid created.' AS message;
        ELSE SELECT 'tbl_product_offering_variant: idx_pid already exists.' AS message; END IF;

        IF NOT EXISTS (SELECT 1 FROM information_schema.STATISTICS
                       WHERE table_schema = DATABASE() AND table_name = 'tbl_product_offering_variant' AND index_name = 'idx_rn') THEN
            CREATE INDEX idx_rn ON tbl_product_offering_variant(rn);
            SELECT 'tbl_product_offering_variant: idx_rn created.' AS message;
        ELSE SELECT 'tbl_product_offering_variant: idx_rn already exists.' AS message; END IF;

        IF NOT EXISTS (SELECT 1 FROM information_schema.STATISTICS
                       WHERE table_schema = DATABASE() AND table_name = 'tbl_product_offering_variant' AND index_name = 'idx_sku') THEN
            CREATE INDEX idx_sku ON tbl_product_offering_variant(SKU);
            SELECT 'tbl_product_offering_variant: idx_sku created.' AS message;
        ELSE SELECT 'tbl_product_offering_variant: idx_sku already exists.' AS message; END IF;
    END IF;

    -- ===== tbl_product_offering_variant_unpivot =====
    IF p_table_name = 'tbl_product_offering_variant_unpivot' THEN
        IF NOT EXISTS (SELECT 1 FROM information_schema.STATISTICS
                       WHERE table_schema = DATABASE() AND table_name = 'tbl_product_offering_variant_unpivot' AND index_name = 'idx_product_id') THEN
            CREATE INDEX idx_product_id ON tbl_product_offering_variant_unpivot(`Product ID`);
            SELECT 'tbl_product_offering_variant_unpivot: idx_product_id created.' AS message;
        ELSE SELECT 'tbl_product_offering_variant_unpivot: idx_product_id already exists.' AS message; END IF;

        IF NOT EXISTS (SELECT 1 FROM information_schema.STATISTICS
                       WHERE table_schema = DATABASE() AND table_name = 'tbl_product_offering_variant_unpivot' AND index_name = 'idx_product_line') THEN
            CREATE INDEX idx_product_line ON tbl_product_offering_variant_unpivot(po_product_line);
            SELECT 'tbl_product_offering_variant_unpivot: idx_product_line created.' AS message;
        ELSE SELECT 'tbl_product_offering_variant_unpivot: idx_product_line already exists.' AS message; END IF;

        IF NOT EXISTS (SELECT 1 FROM information_schema.STATISTICS
                       WHERE table_schema = DATABASE() AND table_name = 'tbl_product_offering_variant_unpivot' AND index_name = 'idx_rn') THEN
            CREATE INDEX idx_rn ON tbl_product_offering_variant_unpivot(rn);
            SELECT 'tbl_product_offering_variant_unpivot: idx_rn created.' AS message;
        ELSE SELECT 'tbl_product_offering_variant_unpivot: idx_rn already exists.' AS message; END IF;

        IF NOT EXISTS (SELECT 1 FROM information_schema.STATISTICS
                       WHERE table_schema = DATABASE() AND table_name = 'tbl_product_offering_variant_unpivot' AND index_name = 'idx_sku') THEN
            CREATE INDEX idx_sku ON tbl_product_offering_variant_unpivot(SKU);
            SELECT 'tbl_product_offering_variant_unpivot: idx_sku created.' AS message;
        ELSE SELECT 'tbl_product_offering_variant_unpivot: idx_sku already exists.' AS message; END IF;
    END IF;

    -- ===== tbl_promotion =====
    IF p_table_name = 'tbl_promotion' THEN
        IF NOT EXISTS (SELECT 1 FROM information_schema.STATISTICS
                       WHERE table_schema = DATABASE() AND table_name = 'tbl_promotion' AND index_name = 'idx_external_id') THEN
            CREATE INDEX idx_external_id ON tbl_promotion(EXTERNAL_ID);
            SELECT 'tbl_promotion: idx_external_id created.' AS message;
        ELSE SELECT 'tbl_promotion: idx_external_id already exists.' AS message; END IF;

        IF NOT EXISTS (SELECT 1 FROM information_schema.STATISTICS
                       WHERE table_schema = DATABASE() AND table_name = 'tbl_promotion' AND index_name = 'idx_external_variant') THEN
            CREATE INDEX idx_external_variant ON tbl_promotion(EXTERNAL_ID, VARIANT_ID);
            SELECT 'tbl_promotion: idx_external_variant created.' AS message;
        ELSE SELECT 'tbl_promotion: idx_external_variant already exists.' AS message; END IF;

        IF NOT EXISTS (SELECT 1 FROM information_schema.STATISTICS
                       WHERE table_schema = DATABASE() AND table_name = 'tbl_promotion' AND index_name = 'idx_promotion_trade_no_rn') THEN
            CREATE INDEX idx_promotion_trade_no_rn ON tbl_promotion(TRADE_NO, rn);
            SELECT 'tbl_promotion: idx_promotion_trade_no_rn created.' AS message;
        ELSE SELECT 'tbl_promotion: idx_promotion_trade_no_rn already exists.' AS message; END IF;

        IF NOT EXISTS (SELECT 1 FROM information_schema.STATISTICS
                       WHERE table_schema = DATABASE() AND table_name = 'tbl_promotion' AND index_name = 'idx_rn') THEN
            CREATE INDEX idx_rn ON tbl_promotion(rn);
            SELECT 'tbl_promotion: idx_rn created.' AS message;
        ELSE SELECT 'tbl_promotion: idx_rn already exists.' AS message; END IF;
    END IF;

    -- ===== TR_CN =====
    IF p_table_name = 'TR_CN' THEN
        IF NOT EXISTS (SELECT 1 FROM information_schema.STATISTICS
                       WHERE table_schema = DATABASE() AND table_name = 'TR_CN' AND index_name = 'TRADE_NO') THEN
            CREATE INDEX TRADE_NO ON TR_CN(TRADE_NO);
            SELECT 'TR_CN: TRADE_NO created.' AS message;
        ELSE SELECT 'TR_CN: TRADE_NO already exists.' AS message; END IF;
    END IF;

    -- ===== TR_DISCOUNT =====
    IF p_table_name = 'TR_DISCOUNT' THEN
        IF NOT EXISTS (SELECT 1 FROM information_schema.STATISTICS
                       WHERE table_schema = DATABASE() AND table_name = 'TR_DISCOUNT' AND index_name = 'IDX_TD_PAY_ADVANCE') THEN
            CREATE INDEX IDX_TD_PAY_ADVANCE ON TR_DISCOUNT(PAY_ADVANCE_GROUP_ID);
            SELECT 'TR_DISCOUNT: IDX_TD_PAY_ADVANCE created.' AS message;
        ELSE SELECT 'TR_DISCOUNT: IDX_TD_PAY_ADVANCE already exists.' AS message; END IF;

        IF NOT EXISTS (SELECT 1 FROM information_schema.STATISTICS
                       WHERE table_schema = DATABASE() AND table_name = 'TR_DISCOUNT' AND index_name = 'IDX_TD_TRADE_PRODUCT') THEN
            CREATE INDEX IDX_TD_TRADE_PRODUCT ON TR_DISCOUNT(TRADE_PRODUCT_ID);
            SELECT 'TR_DISCOUNT: IDX_TD_TRADE_PRODUCT created.' AS message;
        ELSE SELECT 'TR_DISCOUNT: IDX_TD_TRADE_PRODUCT already exists.' AS message; END IF;
    END IF;

    -- ===== TR_MST =====
    IF p_table_name = 'TR_MST' THEN
        IF NOT EXISTS (SELECT 1 FROM information_schema.STATISTICS
                       WHERE table_schema = DATABASE() AND table_name = 'TR_MST' AND index_name = 'IDX_TM_TRADE_NO') THEN
            CREATE INDEX IDX_TM_TRADE_NO ON TR_MST(TRADE_NO);
            SELECT 'TR_MST: IDX_TM_TRADE_NO created.' AS message;
        ELSE SELECT 'TR_MST: IDX_TM_TRADE_NO already exists.' AS message; END IF;
    END IF;

    -- ===== TR_PRODUCT =====
    IF p_table_name = 'TR_PRODUCT' THEN
        IF NOT EXISTS (SELECT 1 FROM information_schema.STATISTICS
                       WHERE table_schema = DATABASE() AND table_name = 'TR_PRODUCT' AND index_name = 'IDX_TP_TRADE_NO') THEN
            CREATE INDEX IDX_TP_TRADE_NO ON TR_PRODUCT(TRADE_NO);
            SELECT 'TR_PRODUCT: IDX_TP_TRADE_NO created.' AS message;
        ELSE SELECT 'TR_PRODUCT: IDX_TP_TRADE_NO already exists.' AS message; END IF;
    END IF;

    -- ===== TR_FREE_GOODS =====
    IF p_table_name = 'TR_FREE_GOODS' THEN
        IF NOT EXISTS (SELECT 1 FROM information_schema.STATISTICS
                       WHERE table_schema = DATABASE() AND table_name = 'TR_FREE_GOODS' AND index_name = 'idx_tr_free_goods_trade_no') THEN
            CREATE INDEX idx_tr_free_goods_trade_no ON TR_FREE_GOODS(trade_no);
            SELECT 'TR_FREE_GOODS: idx_tr_free_goods_trade_no created.' AS message;
        ELSE SELECT 'TR_FREE_GOODS: idx_tr_free_goods_trade_no already exists.' AS message; END IF;

        IF NOT EXISTS (SELECT 1 FROM information_schema.STATISTICS
                       WHERE table_schema = DATABASE() AND table_name = 'TR_FREE_GOODS' AND index_name = 'idx_tr_free_goods_product_id') THEN
            CREATE INDEX idx_tr_free_goods_product_id ON TR_FREE_GOODS(trade_product_id);
            SELECT 'TR_FREE_GOODS: idx_tr_free_goods_product_id created.' AS message;
        ELSE SELECT 'TR_FREE_GOODS: idx_tr_free_goods_product_id already exists.' AS message; END IF;
    END IF;

    -- ===== x_MCH_HIERARCHY =====
    IF p_table_name = 'x_MCH_HIERARCHY' THEN
        IF NOT EXISTS (SELECT 1 FROM information_schema.STATISTICS
                       WHERE table_schema = DATABASE() AND table_name = 'x_MCH_HIERARCHY' AND index_name = 'idx_level') THEN
            CREATE INDEX idx_level ON x_MCH_HIERARCHY(level);
            SELECT 'x_MCH_HIERARCHY: idx_level created.' AS message;
        ELSE SELECT 'x_MCH_HIERARCHY: idx_level already exists.' AS message; END IF;

        IF NOT EXISTS (SELECT 1 FROM information_schema.STATISTICS
                       WHERE table_schema = DATABASE() AND table_name = 'x_MCH_HIERARCHY' AND index_name = 'idx_parent_code') THEN
            CREATE INDEX idx_parent_code ON x_MCH_HIERARCHY(parent_code);
            SELECT 'x_MCH_HIERARCHY: idx_parent_code created.' AS message;
        ELSE SELECT 'x_MCH_HIERARCHY: idx_parent_code already exists.' AS message; END IF;
    END IF;

    -- ===== x_MCH_OTHER_HIERARCHY =====
    IF p_table_name = 'x_MCH_OTHER_HIERARCHY' THEN
        IF NOT EXISTS (SELECT 1 FROM information_schema.STATISTICS
                       WHERE table_schema = DATABASE() AND table_name = 'x_MCH_OTHER_HIERARCHY' AND index_name = 'idx_level') THEN
            CREATE INDEX idx_level ON x_MCH_OTHER_HIERARCHY(level);
            SELECT 'x_MCH_OTHER_HIERARCHY: idx_level created.' AS message;
        ELSE SELECT 'x_MCH_OTHER_HIERARCHY: idx_level already exists.' AS message; END IF;

        IF NOT EXISTS (SELECT 1 FROM information_schema.STATISTICS
                       WHERE table_schema = DATABASE() AND table_name = 'x_MCH_OTHER_HIERARCHY' AND index_name = 'idx_parent_code') THEN
            CREATE INDEX idx_parent_code ON x_MCH_OTHER_HIERARCHY(parent_code);
            SELECT 'x_MCH_OTHER_HIERARCHY: idx_parent_code created.' AS message;
        ELSE SELECT 'x_MCH_OTHER_HIERARCHY: idx_parent_code already exists.' AS message; END IF;
    END IF;

    -- ===== ไม่รู้จัก table =====
    IF p_table_name NOT IN (
        'char_value', 'ingest_batch', 'ingest_batch_detail', 'PRICE_MST', 'PRODUCT_MST',
        'product_type_mapping', 'tbl_campaign_master', 'tbl_contract_master', 'tbl_product_mst',
        'tbl_product_offering', 'tbl_product_offering_char_value', 'tbl_product_offering_price',
        'tbl_product_offering_variant', 'tbl_product_offering_variant_unpivot', 'tbl_promotion',
        'TR_CN', 'TR_DISCOUNT', 'TR_MST', 'TR_PRODUCT', 'TR_FREE_GOODS',
        'x_MCH_HIERARCHY', 'x_MCH_OTHER_HIERARCHY'
    ) THEN
        SELECT CONCAT('Unknown table: ', p_table_name) AS message;
    END IF;

END$$
DELIMITER ;