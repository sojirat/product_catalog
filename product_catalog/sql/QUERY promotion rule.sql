-- [1] ดู overview ทุก condition ต่อ rule
SELECT
    r.identifier,
    r.name,
    r.priority,
    r.effective_from,
    r.effective_to,
    r.channel,
    r.market_segment,
    r.process_context,
    r.category,

    -- Conditions (แตก JSON ออกมาเป็น row)
    c.seq              AS cond_seq,
    c.entity           AS cond_entity,
    c.function_name    AS cond_function,
    c.params           AS cond_params,
    c.operator         AS cond_operator,
    c.sub_seq          AS cond_sub_seq,
    c.sub_op           AS cond_sub_op,
    c.sub_group        AS cond_sub_group,

    -- Actions (แตก JSON ออกมาเป็น row)
    a.entity           AS action_entity,
    a.function_name    AS action_function,
    a.params           AS action_params,
    a.target_entity    AS target_entity,
    a.target_function  AS target_function,
    a.target_params    AS target_params

FROM promotion_rules r

JOIN JSON_TABLE(
    r.conditions,
    '$[*]' COLUMNS (
        seq            INT          PATH '$.seq',
        entity         VARCHAR(100) PATH '$.entity',
        function_name  VARCHAR(200) PATH '$.function',
        params         JSON         PATH '$.params',
        operator       VARCHAR(10)  PATH '$.operator',
        sub_seq        INT          PATH '$.subSeq',
        sub_op         VARCHAR(10)  PATH '$.subOp',
        sub_group      INT          PATH '$.subGroup'
    )
) AS c ON TRUE

JOIN JSON_TABLE(
    r.actions,
    '$[*]' COLUMNS (
        entity          VARCHAR(100) PATH '$.entity',
        function_name   VARCHAR(200) PATH '$.function',
        params          JSON         PATH '$.params',
        target_entity   VARCHAR(100) PATH '$.target.entity',
        target_function VARCHAR(200) PATH '$.target.function',
        target_params   JSON         PATH '$.target.params'
    )
) AS a ON TRUE

ORDER BY r.identifier, c.seq;

-- [2] ดู param ทีละค่า เช่น เช็คว่า variant ไหนอยู่ใน rule ไหน
SELECT
    r.identifier,
    c.seq              AS cond_seq,
    c.entity           AS cond_entity,
    c.function_name    AS cond_function,
    p.param_value      AS cond_param,     -- แตก params ออกทีละค่า
    a.function_name    AS action_function,
    a.params           AS action_params

FROM promotion_rules r

JOIN JSON_TABLE(
    r.conditions,
    '$[*]' COLUMNS (
        seq            INT          PATH '$.seq',
        entity         VARCHAR(100) PATH '$.entity',
        function_name  VARCHAR(200) PATH '$.function',
        params         JSON         PATH '$.params'
    )
) AS c ON TRUE

JOIN JSON_TABLE(
    c.params,
    '$[*]' COLUMNS (
        param_value  VARCHAR(500) PATH '$'
    )
) AS p ON TRUE

JOIN JSON_TABLE(
    r.actions,
    '$[*]' COLUMNS (
        function_name  VARCHAR(200) PATH '$.function',
        params         JSON         PATH '$.params'
    )
) AS a ON TRUE

ORDER BY r.identifier, c.seq, p.param_value;