"""Render a static Power BI design preview from the exported warehouse rows."""

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


summary = json.loads(Path("artifacts/summary.json").read_text(encoding="utf-8"))
frame = pd.read_csv("artifacts/powerbi_shipments.csv")
frame["on_time"] = frame["on_time"].astype(str).str.lower().eq("true")
by_region = frame.groupby("region")["on_time"].mean().mul(100).sort_values()
by_carrier = frame.groupby("carrier")["shipping_cost_usd"].sum().sort_values()
fig = plt.figure(figsize=(13, 7), facecolor="#101827")
fig.text(.06, .92, "LOGISTICS | PERFORMANCE", color="#2dd4bf", fontsize=14, weight="bold")
fig.text(.06, .84, "Delivery operations overview", color="white", fontsize=28, weight="bold")
cards = (
    (.06, f"{summary['fact_shipments']:,}", "Shipments", "white"),
    (.27, f"{summary['on_time_pct']:.1f}%", "On-time rate", "#2dd4bf"),
    (.50, f"${summary['fact_cost_usd']:,.0f}", "Shipping cost", "white"),
    (.78, str(summary["returns"]), "Returns", "#fb7185"),
)
for x, value, label, color in cards:
    fig.text(x, .71, value, color=color, fontsize=27, weight="bold")
    fig.text(x, .66, label, color="#9eb1c7", fontsize=10)
for pos, title, values, color, formatter in (
    ([.12, .16, .34, .38], "On-time rate by region", by_region, "#2dd4bf", lambda v: f"{v:.1f}%"),
    ([.60, .16, .34, .38], "Cost by carrier", by_carrier, "#60a5fa", lambda v: f"${v:,.0f}"),
):
    ax = fig.add_axes(pos, facecolor="#1b2940")
    bars = ax.barh(values.index, values.values, color=color, height=.58)
    ax.bar_label(bars, labels=[formatter(v) for v in values.values], padding=5, color="white", fontsize=9)
    ax.set_xlim(0, max(values.values) * 1.24)
    ax.set_title(title, loc="left", color="white", fontsize=13, weight="bold", pad=15)
    ax.tick_params(axis="y", colors="#d8e5f1", length=0)
    ax.tick_params(axis="x", bottom=False, labelbottom=False)
    for spine in ax.spines.values():
        spine.set_visible(False)
fig.text(.06, .07, "Synthetic shipments • reconciled warehouse • Power BI-ready extract", color="#8197ae", fontsize=9)
out = Path("assets/logistics-preview.png")
out.parent.mkdir(exist_ok=True)
fig.savefig(out, dpi=150, facecolor=fig.get_facecolor())
plt.close(fig)
print(out)
