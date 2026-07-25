CREATE TABLE schema.ods_source_b (
    pk_id BIGINT,
    trace_id VARCHAR(255)
    /* OMITTED BY SOURCE DOCUMENT:
       Remaining columns are described as matching ods_source_a,
       except err_detail is absent. They are intentionally not invented here. */
)
WITH (ORIENTATION = COLUMN, COMPRESSION = 'middle', period = '1 day', ttl = '5 days')
DISTRIBUTE BY HASH (pk_id)
PARTITION BY RANGE (mq_timestamp);
