"""Backend API tests (FastAPI TestClient, no network)."""
import time

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _wait(job_id, timeout=120):
    t = time.time()
    while time.time() - t < timeout:
        j = client.get(f"/api/forecast/jobs/{job_id}").json()
        if j["status"] in ("done", "failed"):
            return j
        time.sleep(0.2)
    raise AssertionError("forecast job timed out")


def test_health():
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_sample_profile_and_rows():
    r = client.get("/api/datasets/sample")
    assert r.status_code == 200
    d = r.json()
    assert d["status"] == "ready" and d["rows"] == 1_024_953
    assert d["meta"]["license"].startswith("Creative Commons")
    rows = client.get("/api/datasets/online-retail-ii/rows?page=1&size=10").json()
    assert len(rows["rows"]) == 10 and rows["total"] == 1_024_953


def test_upload_map_prepare_dashboard_forecast(synthetic_csv):
    r = client.post("/api/datasets/upload", files={"file": ("shop.csv", synthetic_csv, "text/csv")})
    assert r.status_code == 200, r.text
    up = r.json()
    assert up["status"] == "needs_mapping"
    m = up["detection"]["mapping"]
    assert m["date"] == "date" and m["revenue"] == "revenue"
    ds = up["id"]
    # Analysis before mapping is refused clearly.
    assert client.get(f"/api/analytics/{ds}/eda").json()["error"]["code"] == "not_prepared"
    r = client.post(f"/api/datasets/{ds}/prepare", json={"mapping": m})
    assert r.status_code == 200 and r.json()["status"] == "ready"
    d = client.post(f"/api/analytics/{ds}/dashboard", json={"filters": {"region": ["East"]}}).json()
    assert d["regions"][0]["name"] == "East" and len(d["regions"]) == 1
    e = client.get(f"/api/analytics/{ds}/eda").json()
    assert e["overview"]["clean_rows"] > 0
    job = client.post(f"/api/forecast/{ds}/run", json={"target": "gross_revenue"}).json()
    res = _wait(job["job_id"])
    assert res["status"] == "done" and len(res["result"]["forecast"]) == 3
    csv = client.get(f"/api/reports/{ds}/forecast.csv?target=gross_revenue")
    assert csv.status_code == 200 and "lower_80" in csv.text
    html = client.get(f"/api/reports/{ds}/eda.html?target=gross_revenue")
    assert html.status_code == 200 and "<html" in html.text
    assert client.delete(f"/api/datasets/{ds}").json()["ok"] is True
    assert client.get(f"/api/datasets/{ds}").status_code == 404


def test_invalid_inputs():
    assert client.post("/api/datasets/upload", files={"file": ("x.exe", b"MZ", "application/octet-stream")}).status_code == 415
    assert client.post("/api/datasets/upload", files={"file": ("x.csv", b"", "text/csv")}).status_code == 422
    r = client.post("/api/analytics/online-retail-ii/dashboard", json={"filters": {"start": "2011-09-31"}})
    assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_request"
    r = client.post("/api/analytics/online-retail-ii/dashboard", json={"filters": {"start": "2011-05-01", "end": "2011-01-01"}})
    assert r.status_code == 422
    assert client.get("/api/datasets/doesnotexist").status_code == 404
    assert client.post("/api/forecast/online-retail-ii/run", json={"target": "profit"}).status_code == 422


def test_bad_mapping_rejected(tiny_csv):
    up = client.post("/api/datasets/upload", files={"file": ("t.csv", tiny_csv, "text/csv")}).json()
    r = client.post(f"/api/datasets/{up['id']}/prepare", json={"mapping": {"date": "Product"}})
    assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_mapping"


def test_sample_forecast_and_insights():
    job = client.post("/api/forecast/online-retail-ii/run", json={}).json()
    res = _wait(job["job_id"])
    assert res["status"] == "done"
    ins = client.get("/api/insights/online-retail-ii").json()["insights"]
    assert any(i["id"] == "forecast" for i in ins)
    assert client.get("/api/reports/online-retail-ii/dashboard.csv").status_code == 200


def test_too_short_history_reports_limitation():
    csv = "date,sales\n" + "\n".join(f"2024-0{m}-1{d},{100 + d}" for m in range(1, 4) for d in range(0, 9))
    up = client.post("/api/datasets/upload", files={"file": ("short.csv", csv.encode(), "text/csv")}).json()
    client.post(f"/api/datasets/{up['id']}/prepare", json={"mapping": {"date": "date", "revenue": "sales"}})
    res = _wait(client.post(f"/api/forecast/{up['id']}/run", json={"target": "gross_revenue"}).json()["job_id"])
    assert res["status"] == "failed" and res["error"]["code"] == "insufficient_history"
