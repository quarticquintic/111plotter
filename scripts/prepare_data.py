"""
prepare_data.py

Reads all monthly NHS 111 Mental Health CSVs from data/raw/, aggregates
service-level rows up to the 7 NHS England regions, computes derived
metrics, and writes a single tidy JSON file to data/processed/ for the
Quarto/Leaflet front end to consume.

Usage:
    python scripts/prepare_data.py
"""

import glob
import json
import re
from pathlib import Path

import pandas as pd

from population_lookup import get_nhs_region_population

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

RAW_DATA_DIR = Path(__file__).parent.parent / "data" / "raw"
OUTPUT_PATH = Path(__file__).parent.parent / "data" / "processed" / "nhs111_tidy.json"

MONTH_NUMBER = {
    "January": 1, "February": 2, "March": 3, "April": 4,
    "May": 5, "June": 6, "July": 7, "August": 8,
    "September": 9, "October": 10, "November": 11, "December": 12,
}

# Raw metric IDs that are additive counts -> aggregate with sum()
COUNT_METRICS = {
    "A01": "calls_received",
    "A02": "calls_ivr_routed",
    "A03": "calls_answered",
    "B01": "calls_answered_within_60s",
    "B02": "calls_abandoned",
    "B03": "calls_abandoned_30s_or_less",
    "B04": "calls_abandoned_30_to_60s",
    "B05": "calls_abandoned_after_60s",
    "B09": "total_time_abandoned_calls_seconds",
}

# Raw metric IDs that are NOT additive -> aggregate with mean()
AVERAGE_METRICS = {
    "B06": "avg_total_time_to_answer_seconds",
    "B07": "call_answer_time_95th_centile_seconds",
}

# Human-readable labels + units for every metric that ends up in the
# tidy output (raw + derived). Used by the front end for dropdown labels.
METRIC_LABELS = {
    "calls_received": {"label": "Calls received", "unit": "count"},
    "calls_ivr_routed": {"label": "Calls routed through IVR", "unit": "count"},
    "calls_answered": {"label": "Calls answered", "unit": "count"},
    "calls_answered_within_60s": {"label": "Calls answered within 60 seconds", "unit": "count"},
    "calls_abandoned": {"label": "Calls abandoned", "unit": "count"},
    "calls_abandoned_30s_or_less": {"label": "Calls abandoned in 30 seconds or less", "unit": "count"},
    "calls_abandoned_30_to_60s": {"label": "Calls abandoned in 30-60 seconds", "unit": "count"},
    "calls_abandoned_after_60s": {"label": "Calls abandoned after 60 seconds", "unit": "count"},
    "total_time_abandoned_calls_seconds": {"label": "Total time of abandoned calls", "unit": "seconds"},
    "avg_total_time_to_answer_seconds": {"label": "Avg. total time to answer (region mean)", "unit": "seconds"},
    "call_answer_time_95th_centile_seconds": {"label": "95th centile call answer time (region mean)", "unit": "seconds"},
    # Derived metrics
    "answer_rate_pct": {"label": "Answer rate", "unit": "%"},
    "abandonment_rate_pct": {"label": "Abandonment rate", "unit": "%"},
    "answered_within_60s_pct": {"label": "% of answered calls answered within 60s", "unit": "%"},
    "calls_received_per_100k": {"label": "Calls received per 100,000 population", "unit": "per 100k"},
}


# ---------------------------------------------------------------------------
# Load
# ---------------------------------------------------------------------------

def load_all_months() -> pd.DataFrame:
    """Load every monthly CSV in data/raw/ into one long dataframe, with
    MONTH derived from the filename (not the date columns, which have an
    inconsistent format in at least one month)."""
    files = sorted(glob.glob(str(RAW_DATA_DIR / "nhs111_mh_*_2025.csv")))
    if not files:
        raise FileNotFoundError(f"No CSVs found in {RAW_DATA_DIR}")

    frames = []
    for f in files:
        match = re.search(r"nhs111_mh_([A-Za-z]+)_2025\.csv", Path(f).name)
        if not match:
            raise ValueError(f"Could not parse month from filename: {f}")
        month_name = match.group(1)
        month_num = MONTH_NUMBER[month_name]

        df = pd.read_csv(f, dtype={"METRIC_VALUE": str})
        df["MONTH"] = f"2025-{month_num:02d}"
        df["MONTH_LABEL"] = f"{month_name} 2025"
        frames.append(df)

    combined = pd.concat(frames, ignore_index=True)

    # "-" is NHS's suppression marker for small numbers; coerce to NaN
    combined["METRIC_VALUE"] = pd.to_numeric(combined["METRIC_VALUE"], errors="coerce")

    return combined


# ---------------------------------------------------------------------------
# Aggregate
# ---------------------------------------------------------------------------

def aggregate_to_region_month(df: pd.DataFrame) -> pd.DataFrame:
    """Collapse service-level rows to one row per (region, month, metric)."""
    records = []

    for (region, month, month_label), group in df.groupby(["REGION", "MONTH", "MONTH_LABEL"]):
        row = {"region": region, "month": month, "month_label": month_label}

        for metric_id, metric_key in COUNT_METRICS.items():
            vals = group.loc[group["METRIC_ID"] == metric_id, "METRIC_VALUE"]
            row[metric_key] = vals.sum(skipna=True)

        for metric_id, metric_key in AVERAGE_METRICS.items():
            vals = group.loc[group["METRIC_ID"] == metric_id, "METRIC_VALUE"]
            row[metric_key] = vals.mean(skipna=True)

        records.append(row)

    return pd.DataFrame(records)


# ---------------------------------------------------------------------------
# Derived metrics
# ---------------------------------------------------------------------------

def add_derived_metrics(agg: pd.DataFrame) -> pd.DataFrame:
    pop_lookup = get_nhs_region_population()
    agg = agg.copy()

    agg["answer_rate_pct"] = (agg["calls_answered"] / agg["calls_received"] * 100).round(2)
    agg["abandonment_rate_pct"] = (agg["calls_abandoned"] / agg["calls_received"] * 100).round(2)
    agg["answered_within_60s_pct"] = (
        agg["calls_answered_within_60s"] / agg["calls_answered"] * 100
    ).round(2)
    agg["population"] = agg["region"].map(pop_lookup)
    agg["calls_received_per_100k"] = (
        agg["calls_received"] / (agg["population"] / 100_000)
    ).round(1)

    return agg


# ---------------------------------------------------------------------------
# Reshape to long/tidy format for the front end
# ---------------------------------------------------------------------------

def to_tidy_records(agg: pd.DataFrame) -> list:
    metric_cols = [c for c in agg.columns if c in METRIC_LABELS]

    records = []
    for _, row in agg.iterrows():
        for metric_key in metric_cols:
            value = row[metric_key]
            if pd.isna(value):
                continue
            records.append({
                "region": row["region"],
                "month": row["month"],
                "month_label": row["month_label"],
                "metric": metric_key,
                "metric_label": METRIC_LABELS[metric_key]["label"],
                "unit": METRIC_LABELS[metric_key]["unit"],
                "value": float(value),
            })
    return records


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("Loading monthly CSVs...")
    raw = load_all_months()
    print(f"  loaded {len(raw):,} rows across {raw['MONTH'].nunique()} months")

    print("Aggregating to region/month level...")
    agg = aggregate_to_region_month(raw)
    print(f"  {len(agg)} region-month rows (expect 7 regions x 12 months = 84)")

    print("Computing derived metrics (rates + per-capita)...")
    agg = add_derived_metrics(agg)

    print("Reshaping to tidy long format...")
    tidy = to_tidy_records(agg)
    print(f"  {len(tidy):,} tidy records")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(tidy, f, indent=2)
    print(f"Wrote {OUTPUT_PATH}")

    # Quick sanity check printout
    metrics_present = sorted(set(r["metric"] for r in tidy))
    print("\nMetrics available in output:")
    for m in metrics_present:
        print(f"  - {m} ({METRIC_LABELS[m]['label']})")


if __name__ == "__main__":
    main()
