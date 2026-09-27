from pathlib import Path

import duckdb
import pytest

from logistics import build_warehouse, export_powerbi, generate_shipments


def test_fixture_is_repeatable_and_has_unique_shipments():
    first = generate_shipments(300, seed=11)
    assert first == generate_shipments(300, seed=11)
    assert len({row["shipment_id"] for row in first}) == 300
    assert all(row["shipping_cost_usd"] > 0 for row in first)


def test_warehouse_reconciles_counts_costs_and_timeliness(tmp_path: Path):
    rows = [
        {"shipment_id": "S1", "order_date": "2026-01-01", "promised_date": "2026-01-04", "delivered_date": "2026-01-03", "region_id": "N", "region": "North", "carrier_id": "C1", "carrier": "Swift", "shipping_cost_usd": 10.0, "returned": False},
        {"shipment_id": "S2", "order_date": "2026-01-01", "promised_date": "2026-01-04", "delivered_date": "2026-01-04", "region_id": "S", "region": "South", "carrier_id": "C1", "carrier": "Swift", "shipping_cost_usd": 20.0, "returned": True},
        {"shipment_id": "S3", "order_date": "2026-01-02", "promised_date": "2026-01-05", "delivered_date": "2026-01-07", "region_id": "N", "region": "North", "carrier_id": "C2", "carrier": "Parcel", "shipping_cost_usd": 30.0, "returned": False},
    ]
    db_path = tmp_path / "logistics.duckdb"
    first = build_warehouse(db_path, rows)
    assert first == build_warehouse(db_path, rows)
    assert first["source_shipments"] == first["fact_shipments"] == 3
    assert first["cost_difference_usd"] == 0
    assert first["on_time_pct"] == 66.67
    assert first["returns"] == 1
    output = tmp_path / "powerbi.csv"
    assert export_powerbi(db_path, output) == 3
    with duckdb.connect(str(db_path), read_only=True) as db:
        assert db.execute("select count(*) from fact_shipments where region_key is null or carrier_key is null").fetchone()[0] == 0


def test_duplicate_shipment_is_rejected(tmp_path: Path):
    rows = generate_shipments(3, seed=2)
    with pytest.raises(ValueError, match="shipment_id"):
        build_warehouse(tmp_path / "logistics.duckdb", rows + [rows[0]])
