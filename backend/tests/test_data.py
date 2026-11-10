"""Data Hub + Data Quality tests."""
import pandas as pd
import pytest

from salesiq.datahub.detect import detect_columns, detect_frequency, to_datetime, to_number, validate_mapping
from salesiq.datahub.ingest import IngestError, read_csv_bytes
from salesiq.datahub.sample import SAMPLE_MAPPING, SAMPLE_OPTIONS, load_prepared, raw_path
from salesiq.quality.prepare import prepare
from salesiq.schema import CleaningOptions, ColumnMapping


def test_sample_file_exists_and_matches_uci_row_count():
    assert raw_path().exists()
    raw = pd.read_csv(raw_path(), dtype=str, usecols=["invoice"])
    assert len(raw) == 1_067_371  # documented UCI instance count


def test_read_csv_semicolon_and_decimal_comma():
    r = read_csv_bytes("Datum;Umsatz\n01.02.2024;1.234,50\n02.02.2024;99,00\n".encode())
    assert r.delimiter == ";"
    assert to_number(r.frame["Umsatz"]).tolist() == [1234.5, 99.0]


def test_read_rejects_binary_and_empty():
    with pytest.raises(IngestError):
        read_csv_bytes(b"")
    with pytest.raises(IngestError):
        read_csv_bytes(b"PK\x03\x04rest-of-zip")


def test_detect_columns(tiny_csv):
    frame = read_csv_bytes(tiny_csv).frame
    m = detect_columns(frame)["mapping"]
    assert m["date"] == "Order Date"
    assert m["quantity"] == "Qty" and m["unit_price"] == "Unit Price"
    assert m["order_id"] == "Order ID" and m["product"] == "Product" and m["region"] == "Region"


def test_validate_mapping_requires_value_columns(tiny_csv):
    frame = read_csv_bytes(tiny_csv).frame
    errs = validate_mapping(frame, ColumnMapping(date="Order Date"))
    assert any("revenue" in e for e in errs)
    errs = validate_mapping(frame, ColumnMapping(date="Product", quantity="Qty", unit_price="Unit Price"))
    assert any("does not look like dates" in e for e in errs)


def test_date_parsing_day_first():
    s = to_datetime(pd.Series(["13/02/2024", "14/02/2024", "01/03/2024"]))
    assert s.dt.month.tolist() == [2, 2, 3]


def test_prepare_rules(tiny_csv):
    frame = read_csv_bytes(tiny_csv).frame
    mapping = ColumnMapping(date="Order Date", quantity="Qty", unit_price="Unit Price", order_id="Order ID",
                            product="Product", region="Region")
    p = prepare(frame, mapping, CleaningOptions())
    steps = {s["step"]: s["rows_affected"] for s in p.steps}
    assert steps["Removed exact duplicates"] == 1
    assert steps["Dropped rows without a valid date"] == 1
    assert steps["Separated returns / cancellations"] == 1
    assert steps["Dropped zero-value lines"] == 1
    assert len(p.sales) == 3 and len(p.returns) == 1
    assert p.sales["revenue"].sum() == pytest.approx(20 + 50 + 10)
    assert p.quality["duplicate_rows"] == 1


def test_missing_dimension_filled_not_dropped():
    csv = "date,sales,region\n2024-01-01,10,\n2024-01-02,5,East\n".encode()
    p = prepare(read_csv_bytes(csv).frame, ColumnMapping(date="date", revenue="sales", region="region"))
    assert len(p.sales) == 2
    assert "Unknown" in set(p.sales["region"].astype(str))


def test_frequency_detection():
    d = pd.Series(pd.date_range("2024-01-01", periods=10, freq="D"))
    assert detect_frequency(d)["frequency"] == "daily"
    m = pd.Series(pd.date_range("2024-01-01", periods=10, freq="MS"))
    assert detect_frequency(m)["frequency"] == "monthly"


def test_sample_cleaning_is_reproducible():
    p, meta = load_prepared()
    assert len(p.sales) == 1_024_953
    assert len(p.returns) == 21_683
    assert (p.sales["revenue"] > 0).all()
    assert p.sales["date"].min() == pd.Timestamp("2009-12-01 07:45:00")
    assert "POST" not in set(p.sales["product"].astype(str))
    steps = {s["step"]: s["rows_affected"] for s in p.steps}
    assert steps["Removed exact duplicates"] == 12_133


def test_monthly_aggregation_matches_raw_totals():
    p, _ = load_prepared()
    monthly = p.sales.groupby(p.sales["day"].dt.to_period("M"))["revenue"].sum()
    assert monthly.sum() == pytest.approx(p.sales["revenue"].sum())
    nov = p.sales[(p.sales["day"] >= "2011-11-01") & (p.sales["day"] <= "2011-11-30")]["revenue"].sum()
    assert monthly[pd.Period("2011-11", "M")] == pytest.approx(nov)
