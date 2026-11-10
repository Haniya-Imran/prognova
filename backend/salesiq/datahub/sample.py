"""The built-in demo dataset: UCI Online Retail II (real, CC BY 4.0)."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from ..schema import CleaningOptions, ColumnMapping
from .frame_store import load_frame, save_frame

SAMPLE_ID = "online-retail-ii"

SAMPLE_META = {
    "id": SAMPLE_ID,
    "name": "Online Retail II (UCI)",
    "description": (
        "All transactions of a UK-based, registered non-store online retailer selling "
        "unique all-occasion giftware, 1 Dec 2009 to 9 Dec 2011. Many customers are wholesalers."
    ),
    "source_url": "https://archive.ics.uci.edu/dataset/502/online+retail+ii",
    "citation": "Chen, D. (2012). Online Retail II [Dataset]. UCI Machine Learning Repository. https://doi.org/10.24432/C5CG6D",
    "license": "Creative Commons Attribution 4.0 International (CC BY 4.0)",
    "currency": "GBP",
    "limitations": [
        "Covers about two years, so yearly seasonality is seen only twice.",
        "December 2011 is partial (1-9 Dec); forecasts start after the last complete month.",
        "No product category column exists, so category KPIs and filters are not shown for this dataset.",
        "Revenue is sales value (quantity x unit price). There is no cost data, so profit is not calculated.",
        "Country is the customer's country; about 9 in 10 sales are to the United Kingdom.",
        "About 1 in 5 lines has no customer ID, so customer counts cover identified customers only.",
    ],
}

SAMPLE_MAPPING = ColumnMapping(
    date="invoice_date", quantity="quantity", unit_price="price", order_id="invoice",
    product="stock_code", region="country", customer="customer_id",
)

SAMPLE_OPTIONS = CleaningOptions(
    drop_duplicates=True,
    separate_returns=True,
    cancellation_prefix="C",
    non_merchandise_codes=["POST", "DOT", "M", "C2", "D", "S", "B", "BANK CHARGES", "AMAZONFEE",
                           "PADS", "CRUK", "ADJUST", "ADJUST2"],
    non_merchandise_prefixes=["TEST", "GIFT_"],
)


def data_dir() -> Path:
    return Path(__file__).resolve().parents[3] / "data"


def processed_dir() -> Path:
    """Cleaned sample shipped with the API (lives inside backend/ so serverless bundles include it)."""
    return Path(__file__).resolve().parents[2] / "data" / "processed"


def raw_path() -> Path:
    return data_dir() / "raw" / "online_retail_ii.csv.gz"


def processed_path() -> Path:
    return processed_dir() / "online_retail_ii_sales.npz"


def load_raw() -> pd.DataFrame:
    return pd.read_csv(raw_path(), dtype=str)


def product_names(raw: pd.DataFrame) -> dict[str, str]:
    """Most frequent description per stock code (descriptions vary slightly between invoices)."""
    d = raw[["stock_code", "description"]].dropna()
    d = d[d["description"].str.strip() != ""]
    top = (d.groupby(["stock_code", "description"]).size().reset_index(name="n")
           .sort_values("n", ascending=False).drop_duplicates("stock_code"))
    return dict(zip(top["stock_code"], top["description"].str.strip().str.title()))


def _label_products(prepared, names: dict[str, str]) -> None:
    """Show product names instead of stock codes; keep codes when two codes share a name."""
    all_codes = pd.Series(pd.concat([prepared.sales["product"].astype(str),
                                     prepared.returns["product"].astype(str)]).unique())
    labels_all = all_codes.map(lambda c: names.get(c, c))
    counts = pd.DataFrame({"c": all_codes, "l": labels_all}).groupby("l")["c"].nunique()
    clash = set(counts[counts > 1].index)
    lookup = {c: (f"{l} ({c})" if l in clash else l) for c, l in zip(all_codes, labels_all)}
    for frame in (prepared.sales, prepared.returns):
        if "product" not in frame or frame.empty:
            continue
        frame["product"] = pd.Categorical(frame["product"].astype(str).map(lookup))


def build_prepared():
    """Clean the raw file once and cache the result as compressed NumPy + JSON."""
    import json
    from ..quality.prepare import prepare

    raw = load_raw()
    prepared = prepare(raw, SAMPLE_MAPPING, SAMPLE_OPTIONS)
    _label_products(prepared, product_names(raw))
    out = processed_path()
    out.parent.mkdir(parents=True, exist_ok=True)
    save_frame(prepared.sales, out)
    save_frame(prepared.returns, out.with_name("online_retail_ii_returns.npz"))
    meta = {"steps": prepared.steps, "quality": prepared.quality, "available": prepared.available,
            "has_time_of_day": prepared.has_time_of_day,
            "raw_columns": list(raw.columns), "raw_preview": raw.head(20).fillna("").to_dict("records")}
    out.with_name("online_retail_ii_meta.json").write_text(json.dumps(meta, default=str, indent=1))
    return prepared


def load_prepared():
    """Load the cached clean sample, building it on first use."""
    import json
    from ..quality.prepare import PreparedData

    out = processed_path()
    meta_path = out.with_name("online_retail_ii_meta.json")
    if not (out.exists() and meta_path.exists()):
        prepared = build_prepared()
        meta = json.loads(meta_path.read_text())
        return prepared, meta
    meta = json.loads(meta_path.read_text())
    sales = load_frame(out)
    returns = load_frame(out.with_name("online_retail_ii_returns.npz"))
    prepared = PreparedData(sales=sales, returns=returns, steps=meta["steps"], quality=meta["quality"],
                            available=meta["available"], has_time_of_day=meta["has_time_of_day"])
    return prepared, meta
