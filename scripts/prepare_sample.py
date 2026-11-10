"""Rebuild data/processed/* from data/raw/online_retail_ii.csv.gz.

Run from the repo root:  python scripts/prepare_sample.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from salesiq.datahub.sample import build_prepared, processed_path  # noqa: E402

if __name__ == "__main__":
    p = build_prepared()
    print(f"Wrote {processed_path()} with {len(p.sales):,} sales lines and {len(p.returns):,} returns.")
