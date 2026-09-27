CREATE SCHEMA IF NOT EXISTS portfolio_logistics;

CREATE TABLE IF NOT EXISTS portfolio_logistics.source_shipments (
    shipment_id text PRIMARY KEY,
    order_date date NOT NULL,
    promised_date date NOT NULL,
    delivered_date date NOT NULL,
    region_id text NOT NULL,
    region text NOT NULL,
    carrier_id text NOT NULL,
    carrier text NOT NULL,
    shipping_cost_usd numeric(14,2) NOT NULL CHECK (shipping_cost_usd > 0),
    returned boolean NOT NULL
);
CREATE TABLE IF NOT EXISTS portfolio_logistics.dim_date (
    date_key integer PRIMARY KEY,
    calendar_date date NOT NULL,
    year integer NOT NULL,
    month integer NOT NULL
);
CREATE TABLE IF NOT EXISTS portfolio_logistics.dim_region (
    region_key text PRIMARY KEY,
    region_name text NOT NULL
);
CREATE TABLE IF NOT EXISTS portfolio_logistics.dim_carrier (
    carrier_key text PRIMARY KEY,
    carrier_name text NOT NULL
);
CREATE TABLE IF NOT EXISTS portfolio_logistics.fact_shipments (
    shipment_id text PRIMARY KEY,
    date_key integer NOT NULL REFERENCES portfolio_logistics.dim_date(date_key),
    region_key text NOT NULL REFERENCES portfolio_logistics.dim_region(region_key),
    carrier_key text NOT NULL REFERENCES portfolio_logistics.dim_carrier(carrier_key),
    promised_date date NOT NULL,
    delivered_date date NOT NULL,
    on_time boolean NOT NULL,
    shipping_cost_usd numeric(14,2) NOT NULL,
    returned boolean NOT NULL
);
