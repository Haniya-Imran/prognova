"""EDA + KPI + dashboard tests."""
import pandas as pd
import pytest

from salesiq.analytics.dashboard import dashboard, dimension_values
from salesiq.analytics.filters import Filters, apply
from salesiq.analytics.kpis import base_kpis, kpis
from salesiq.datahub.ingest import read_csv_bytes
from salesiq.datahub.sample import load_prepared
from salesiq.eda.explore import run_eda
from salesiq.quality.prepare import prepare
from salesiq.schema import ColumnMapping


@pytest.fixture(scope="module")
def sample():
    p, meta = load_prepared()
    return p, meta


def _tiny(tiny_csv):
    m = ColumnMapping(date="Order Date", quantity="Qty", unit_price="Unit Price", order_id="Order ID",
                      product="Product", region="Region")
    return prepare(read_csv_bytes(tiny_csv).frame, m)


def test_kpi_calculations(tiny_csv):
    p = _tiny(tiny_csv)
    k = base_kpis(p.sales, p.returns)
    assert k["gross_revenue"] == pytest.approx(80)
    assert k["returns_value"] == pytest.approx(50)
    assert k["net_revenue"] == pytest.approx(30)
    assert k["orders"] == 2
    assert k["avg_order_value"] == pytest.approx(40)
    assert k["units"] == 4


def test_kpi_missing_columns_are_none():
    csv = "date,sales\n2024-01-01,10\n2024-01-02,5\n".encode()
    p = prepare(read_csv_bytes(csv).frame, ColumnMapping(date="date", revenue="sales"))
    k = base_kpis(p.sales, p.returns)
    assert k["orders"] is None and k["avg_order_value"] is None and k["units"] is None


def test_filter_correctness(sample):
    p, _ = sample
    f = Filters(start="2011-03-01", end="2011-03-31", region=["France"])
    s = apply(p.sales, f)
    assert set(s["region"].astype(str)) == {"France"}
    assert s["day"].min() >= pd.Timestamp("2011-03-01") and s["day"].max() <= pd.Timestamp("2011-03-31")
    expected = p.sales[(p.sales["region"] == "France") & (p.sales["day"].between("2011-03-01", "2011-03-31"))]["revenue"].sum()
    assert kpis(p.sales, p.returns, f)["current"]["gross_revenue"] == pytest.approx(expected)


def test_growth_vs_previous_period(sample):
    p, _ = sample
    k = kpis(p.sales, p.returns, Filters(start="2011-11-01", end="2011-11-30"))
    assert k["previous_period"]["start"] == "2011-10-02"  # 30 days immediately before
    prev = p.sales[p.sales["day"].between("2011-10-02", "2011-10-31")]["revenue"].sum()
    cur = p.sales[p.sales["day"].between("2011-11-01", "2011-11-30")]["revenue"].sum()
    assert k["growth"]["gross_revenue"]["vs_previous_period_pct"] == pytest.approx((cur / prev - 1) * 100)


def test_dashboard_chart_data_sums_to_kpi(sample):
    p, _ = sample
    f = Filters(start="2010-06-01", end="2010-08-31", region=["Germany"])
    d = dashboard(p.sales, p.returns, f, "week", p.has_time_of_day)
    assert sum(d["trend"]["revenue"]) == pytest.approx(d["kpis"]["current"]["gross_revenue"], rel=1e-6)
    assert d["regions"][0]["name"] == "Germany" and len(d["regions"]) == 1
    hm = sum(sum(r) for r in d["heatmap"]["z"])
    assert hm == pytest.approx(d["kpis"]["current"]["gross_revenue"], rel=1e-6)


def test_empty_filter_result(sample):
    p, _ = sample
    d = dashboard(p.sales, p.returns, Filters(region=["Atlantis"]), None, p.has_time_of_day)
    assert d["empty"] is True and d["kpis"]["current"]["gross_revenue"] == 0


def test_dimension_search(sample):
    p, _ = sample
    vals = dimension_values(p.sales, "product", "cakestand", 5)
    assert vals and all("cakestand" in v["value"].lower() for v in vals)


def test_eda_outputs(sample):
    p, meta = sample
    e = run_eda(p.sales, p.returns, p.quality, meta["raw_columns"], p.has_time_of_day)
    months = e["time"]["monthly"]
    assert months[0]["month"] == "2009-12" and months[-1]["month"] == "2011-12"
    assert months[-1]["complete"] is False  # December 2011 is partial
    assert sum(m["revenue"] for m in months) == pytest.approx(p.sales["revenue"].sum(), rel=1e-6)
    nov10 = next(m for m in months if m["month"] == "2010-11")
    oct10 = next(m for m in months if m["month"] == "2010-10")
    assert nov10["mom_pct"] == pytest.approx((nov10["revenue"] / oct10["revenue"] - 1) * 100, abs=0.01)
    assert e["dimensions"]["category"] is None  # no category column in this dataset
    assert e["overview"]["clean_rows"] == len(p.sales)
