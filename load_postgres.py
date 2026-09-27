"""Load the synthetic logistics source into a PostgreSQL star schema."""

import json
import os
from pathlib import Path

import psycopg


SCHEMA_SQL = Path(__file__).parent / "postgres/schema.sql"
SOURCE_CSV = Path(__file__).parent / "data/shipments.csv"


def load_postgres(dsn: str, source_csv: Path = SOURCE_CSV) -> dict:
    with psycopg.connect(dsn) as connection:
        for statement in SCHEMA_SQL.read_text(encoding="utf-8").split(";"):
            if statement.strip():
                connection.execute(statement)
        connection.execute("""
            TRUNCATE portfolio_logistics.fact_shipments,
                     portfolio_logistics.dim_date,
                     portfolio_logistics.dim_region,
                     portfolio_logistics.dim_carrier,
                     portfolio_logistics.source_shipments
        """)
        with connection.cursor().copy("""
            COPY portfolio_logistics.source_shipments
            (shipment_id, order_date, promised_date, delivered_date, region_id, region,
             carrier_id, carrier, shipping_cost_usd, returned)
            FROM STDIN WITH (FORMAT CSV, HEADER TRUE)
        """) as copy:
            copy.write(source_csv.read_bytes())
        connection.execute("""
            INSERT INTO portfolio_logistics.dim_date
            SELECT DISTINCT to_char(order_date, 'YYYYMMDD')::integer,
                            order_date, extract(year from order_date)::integer,
                            extract(month from order_date)::integer
            FROM portfolio_logistics.source_shipments
        """)
        connection.execute("""
            INSERT INTO portfolio_logistics.dim_region
            SELECT DISTINCT region_id, region FROM portfolio_logistics.source_shipments
        """)
        connection.execute("""
            INSERT INTO portfolio_logistics.dim_carrier
            SELECT DISTINCT carrier_id, carrier FROM portfolio_logistics.source_shipments
        """)
        connection.execute("""
            INSERT INTO portfolio_logistics.fact_shipments
            SELECT shipment_id, to_char(order_date, 'YYYYMMDD')::integer,
                   region_id, carrier_id, promised_date, delivered_date,
                   delivered_date <= promised_date, shipping_cost_usd, returned
            FROM portfolio_logistics.source_shipments
        """)
        source_rows, source_cost = connection.execute("""
            SELECT count(*), sum(shipping_cost_usd) FROM portfolio_logistics.source_shipments
        """).fetchone()
        fact_rows, fact_cost, on_time, returns = connection.execute("""
            SELECT count(*), sum(shipping_cost_usd), count(*) FILTER (WHERE on_time),
                   count(*) FILTER (WHERE returned)
            FROM portfolio_logistics.fact_shipments
        """).fetchone()
        if source_rows != fact_rows or source_cost != fact_cost:
            raise ValueError("PostgreSQL warehouse reconciliation failed")
        return {
            "source_shipments": source_rows,
            "fact_shipments": fact_rows,
            "shipping_cost_usd": float(fact_cost),
            "cost_difference_usd": float(source_cost - fact_cost),
            "on_time_pct": round(on_time * 100 / fact_rows, 2),
            "returns": returns,
        }


if __name__ == "__main__":
    dsn_value = os.environ.get("PORTFOLIO_PG_DSN")
    if not dsn_value:
        raise SystemExit("Set PORTFOLIO_PG_DSN locally before running this loader")
    print(json.dumps(load_postgres(dsn_value), indent=2))
