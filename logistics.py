"""Synthetic logistics ETL with a reconciled warehouse and Power BI extract."""

from __future__ import annotations

import argparse
import csv
import json
import random
from datetime import date, timedelta
from pathlib import Path

import duckdb
import pandas as pd


REGIONS = (("N", "North"), ("S", "South"), ("E", "East"), ("W", "West"))
CARRIERS = (("C1", "Swift"), ("C2", "Parcel"), ("C3", "Freight"))
FIELDS = (
    "shipment_id", "order_date", "promised_date", "delivered_date", "region_id",
    "region", "carrier_id", "carrier", "shipping_cost_usd", "returned",
)


def generate_shipments(count: int, seed: int = 20260927) -> list[dict]:
    if count < 1:
        raise ValueError("count must be positive")
    rng = random.Random(seed)
    rows = []
    for index in range(count):
        ordered = date(2026, 1, 1) + timedelta(days=rng.randrange(120))
        promised = ordered + timedelta(days=rng.randint(2, 5))
        delivered = promised + timedelta(days=rng.choice((-1, 0, 0, 0, 1, 2, 3)))
        region_id, region = rng.choice(REGIONS)
        carrier_id, carrier = rng.choice(CARRIERS)
        rows.append({
            "shipment_id": f"SHIP-{index + 1:05d}",
            "order_date": ordered.isoformat(),
            "promised_date": promised.isoformat(),
            "delivered_date": delivered.isoformat(),
            "region_id": region_id,
            "region": region,
            "carrier_id": carrier_id,
            "carrier": carrier,
            "shipping_cost_usd": round(rng.uniform(4.5, 42.0), 2),
            "returned": rng.random() < .08,
        })
    return rows


def build_warehouse(db_path: str | Path, rows: list[dict]) -> dict:
    ids = [str(row["shipment_id"]) for row in rows]
    if not rows or len(ids) != len(set(ids)):
        raise ValueError("source requires unique shipment_id values")
    frame = pd.DataFrame(rows, columns=FIELDS)
    if frame.isna().any().any() or (frame["shipping_cost_usd"] <= 0).any():
        raise ValueError("source contains null or nonpositive cost")
    for field in ("order_date", "promised_date", "delivered_date"):
        pd.to_datetime(frame[field], errors="raise")
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with duckdb.connect(str(path)) as db:
        db.register("incoming", frame)
        db.execute("BEGIN TRANSACTION")
        try:
            db.execute("CREATE OR REPLACE TABLE source_shipments AS SELECT * FROM incoming")
            db.execute("""
                CREATE OR REPLACE TABLE dim_date AS
                SELECT DISTINCT CAST(replace(order_date, '-', '') AS INTEGER) AS date_key,
                       CAST(order_date AS DATE) AS calendar_date,
                       year(CAST(order_date AS DATE)) AS year,
                       month(CAST(order_date AS DATE)) AS month
                FROM source_shipments
            """)
            db.execute("""
                CREATE OR REPLACE TABLE dim_region AS
                SELECT DISTINCT region_id AS region_key, region AS region_name FROM source_shipments
            """)
            db.execute("""
                CREATE OR REPLACE TABLE dim_carrier AS
                SELECT DISTINCT carrier_id AS carrier_key, carrier AS carrier_name FROM source_shipments
            """)
            db.execute("""
                CREATE OR REPLACE TABLE fact_shipments AS
                SELECT shipment_id,
                       CAST(replace(order_date, '-', '') AS INTEGER) AS date_key,
                       region_id AS region_key,
                       carrier_id AS carrier_key,
                       CAST(promised_date AS DATE) AS promised_date,
                       CAST(delivered_date AS DATE) AS delivered_date,
                       CAST(delivered_date AS DATE) <= CAST(promised_date AS DATE) AS on_time,
                       CAST(shipping_cost_usd AS DECIMAL(14,2)) AS shipping_cost_usd,
                       CAST(returned AS BOOLEAN) AS returned
                FROM source_shipments
            """)
            source_count, source_cost = db.execute("""
                SELECT count(*), sum(CAST(shipping_cost_usd AS DECIMAL(14,2))) FROM source_shipments
            """).fetchone()
            fact_count, fact_cost, on_time_count, returns = db.execute("""
                SELECT count(*), sum(shipping_cost_usd), sum(CAST(on_time AS INTEGER)),
                       sum(CAST(returned AS INTEGER)) FROM fact_shipments
            """).fetchone()
            missing_keys = db.execute("""
                SELECT count(*) FROM fact_shipments f
                LEFT JOIN dim_date d USING (date_key)
                LEFT JOIN dim_region r USING (region_key)
                LEFT JOIN dim_carrier c USING (carrier_key)
                WHERE d.date_key IS NULL OR r.region_key IS NULL OR c.carrier_key IS NULL
            """).fetchone()[0]
            if source_count != fact_count or source_cost != fact_cost or missing_keys:
                raise ValueError("warehouse reconciliation failed")
            db.execute("COMMIT")
        except Exception:
            db.execute("ROLLBACK")
            raise
    return {
        "source_shipments": source_count,
        "fact_shipments": fact_count,
        "source_cost_usd": float(source_cost),
        "fact_cost_usd": float(fact_cost),
        "cost_difference_usd": float(source_cost - fact_cost),
        "on_time_pct": round(on_time_count * 100 / fact_count, 2),
        "returns": returns,
        "missing_dimension_keys": missing_keys,
    }


def export_powerbi(db_path: str | Path, output: str | Path) -> int:
    with duckdb.connect(str(db_path), read_only=True) as db:
        frame = db.execute("""
            SELECT f.shipment_id, d.calendar_date AS order_date, f.promised_date,
                   f.delivered_date, r.region_name AS region, c.carrier_name AS carrier,
                   f.shipping_cost_usd, f.on_time, f.returned
            FROM fact_shipments f
            JOIN dim_date d USING (date_key)
            JOIN dim_region r USING (region_key)
            JOIN dim_carrier c USING (carrier_key)
            ORDER BY f.shipment_id
        """).df()
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)
    return len(frame)


def export_source(path: str | Path, rows: list[dict]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=600)
    parser.add_argument("--db", type=Path, default=Path("artifacts/logistics.duckdb"))
    args = parser.parse_args()
    source = generate_shipments(args.count)
    export_source("data/shipments.csv", source)
    result = build_warehouse(args.db, source)
    extract_rows = export_powerbi(args.db, "artifacts/powerbi_shipments.csv")
    if extract_rows != result["fact_shipments"]:
        raise ValueError("Power BI extract row count mismatch")
    Path("artifacts/summary.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
