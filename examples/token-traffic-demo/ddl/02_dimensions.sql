CREATE SCHEMA IF NOT EXISTS dim;

CREATE TABLE dim.dim_region (
    region_code  VARCHAR(16) NOT NULL,
    region_name  VARCHAR(64),
    bureau_code  VARCHAR(16),
    bureau_name  VARCHAR(64),
    enabled_flag CHAR(1)
);

CREATE TABLE dim.dim_tenant (
    tenant_id    VARCHAR(32) NOT NULL,
    tenant_name  VARCHAR(128),
    industry     VARCHAR(64),
    customer_tier VARCHAR(16)
);

CREATE TABLE dim.dim_model (
    model_code   VARCHAR(64) NOT NULL,
    model_family VARCHAR(64),
    provider     VARCHAR(64)
);
