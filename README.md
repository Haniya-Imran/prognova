# Prognova

**See what sold. Know what's next.** Sales EDA, an interactive Plotly dashboard and a **backtested 3-month sales forecast** in one workspace — built on more than a million real retail transactions. No login: open it and use it.

Built by **Haniya Imran**.

---

## What it does

| Step | Module | What you get |
|---|---|---|
| A | **Data Hub** | Real demo dataset opens automatically; upload your own CSV; automatic column detection with manual override; raw and cleaned previews |
| B | **Data Quality & Preparation** | Missing values, duplicates, type checks, date parsing, outlier inspection, frequency detection, and a numbered log of every cleaning rule with rows affected |
| C | **EDA Studio** | Descriptive stats (line and order level), distributions, daily/weekly/monthly trends, MoM and YoY growth, seasonality index, weekday and hour patterns, volatility, top/bottom products and regions, correlation, returns |
| D | **Sales Analytics + Plotly Dashboard** | KPI cards (gross/net revenue, orders, units, AOV, growth vs previous period and vs last year, best product, top region/category/store), date/product/region/category/store filters, click-to-drill bars, year-vs-year lines, heatmap, Pareto curve, returns |
| E | **Forecasting Lab** | 8 candidate models, rolling-origin backtesting, automatic selection, next 3 calendar months with 80% and 95% ranges, actual-vs-predicted validation, segment forecasts |
| F | **Business Insights** | Data-driven findings, each with its evidence, a suggested action and the assumption behind it |
| G | **Reports** | HTML reports (EDA, dashboard, forecast) and CSVs (forecast, backtest, model comparison, monthly sales, dashboard trend) |

## Architecture — Sales Intelligence Workspace

```
Data Hub → Data Quality & Preparation → EDA Studio → Sales Analytics Engine
        → Interactive Plotly Dashboard → Forecasting Lab → Business Insights & Reports
```

- **Engine (`backend/salesiq/`)** — pure Python, no web code. One sub-package per module: `datahub`, `quality`, `eda`, `analytics`, `forecasting`, `insights`, `reports`. Each stage only consumes the canonical sales table produced by `quality.prepare`.
- **API (`backend/app/`)** — FastAPI, served by Vercel at `/api` on the same domain as the site. A *workspace* per dataset lives in memory with cached EDA, an LRU cache of dashboard views and cached forecasts. Forecasts run inside the request (≈1–4 s), which is safe on serverless where the next request may reach a different instance.
- **Serverless-safe uploads** — upload ids are a hash of the file, and the browser keeps the file (IndexedDB) and its mapping. If an instance restarted and forgot the upload, the app silently re-sends it and retries (tested by restarting the API mid-session).
- **Lean dependencies** — only FastAPI, pandas and NumPy (~125 MB installed). Holt / Holt-Winters smoothing is implemented in NumPy (`forecasting/ets.py`, tested) and the cleaned sample is stored as a compressed NumPy archive, so SciPy, statsmodels and pyarrow are not needed and the function stays under Vercel's 250 MB limit.
- **Frontend (`frontend/`)** — React + TypeScript + Vite, dark 3D "night observatory" design system. Plotly for charts; three.js (react-three-fiber) for the landing scene, whose teal towers are the 24 real monthly totals and amber towers the real forecast. The workspace bundle (with Plotly) is lazy-loaded so the landing page stays light. All API calls go through `src/lib/api.ts`.

```
sales-studio/
├── api/index.py             Vercel entry point (imports backend/app)
├── backend/
│   ├── app/                 FastAPI: config, errors, schemas, api/*, services/{workspace,jobs}
│   ├── salesiq/             engine: datahub, quality, eda, analytics, forecasting, insights, reports
│   ├── data/processed/      cleaned sample (.npz) + cleaning log, shipped with the API
│   ├── tests/               pytest: data, analytics, forecasting, API
│   └── requirements*.txt
├── data/raw/online_retail_ii.csv.gz   the downloaded dataset (unchanged)
├── frontend/
│   ├── src/{landing,workspace,components,lib,state}
│   └── e2e/                 browser flows: full journey, restart recovery, screenshots
├── scripts/prepare_sample.py
├── requirements.txt         Python deps for the Vercel function
├── vercel.json              one project: static site + /api function
└── .env.example
```

## Dataset

**Online Retail II** — UCI Machine Learning Repository.
Chen, D. (2012). *Online Retail II* [Dataset]. https://doi.org/10.24432/C5CG6D · https://archive.ics.uci.edu/dataset/502/online+retail+ii
**License:** Creative Commons Attribution 4.0 (CC BY 4.0).

All transactions of a UK-based online giftware retailer (many customers are wholesalers), 1 Dec 2009 – 9 Dec 2011: 1,067,371 rows, 43 countries, ~5,300 stock codes.

The UCI site was not reachable from the build environment, so the file was taken from two independent public GitHub copies; both were identical (same 1,067,371 rows matching UCI's documented count, same totals and date range). SHA-256 of the stored file: `d1623242899a72146ffc7008965d24f2cd6284451485cf94d99b29847c4786cb`.

**Limitations:** about two years of history (yearly seasonality seen twice); December 2011 is partial; no category column; no cost data, so **revenue is not profit**; ~86% of revenue is UK; ~22% of lines have no customer ID.

### Cleaning decisions (sample)

| Rule | Rows |
|---|---|
| Exact duplicate rows removed | 12,133 |
| Non-product lines removed (postage, fees, bank charges, manual adjustments, gift vouchers, test codes) | 5,918 |
| Returns / cancellations (invoice starting "C" or negative quantity) moved to a **returns** table | 21,683 |
| Zero-price lines dropped | 2,684 |
| Missing customer ID labelled "Unknown" (sale still counts) | 234,249 |
| **Clean sales lines** | **1,024,953** |

Large lines are flagged by an IQR rule but **kept** — they are genuine wholesale orders. The largest (an £168k order) was cancelled the same day; it sits in returns, so **net revenue** cancels it.

## Forecasting method

- **Target:** net revenue (default), gross revenue or units, per **calendar month**.
- **Series:** only complete months are used (Dec 2011 is excluded), so the forecast is **Dec 2011, Jan 2012, Feb 2012**. Daily models forecast every day and add the days into those calendar months.
- **Candidates:** naive, seasonal naive, 3-month moving average (baselines); seasonal naive × recent growth; Holt damped trend; Holt-Winters 12-month (needs 24 months per window — excluded here, with the reason shown); daily Holt-Winters with weekly season; dynamic harmonic regression (trend + day-of-week + yearly Fourier terms). SARIMA and Prophet are listed with reasons for not being used.
- **Backtest:** rolling origin — train on all months up to the origin, forecast the next 3, move one month, repeat (7 windows on the sample). No random splits; a test checks that changing future data does not change past forecasts.
- **Selection:** lowest WAPE across all backtest months. MAE, RMSE, sMAPE, bias and MAPE are also reported (MAPE is hidden when actuals are near zero).
- **Ranges:** 80% and 95% ranges from the selected model's own backtest errors at each horizon. The app reports how often real months fell inside the 80% range in the backtest and warns when ranges look optimistic.

**Sample result (net revenue):** the seasonal naive model won (WAPE 10.6% over 7 windows); harmonic regression came second (12.2%), the growth-adjusted version third (14.2%), Holt damped 24.1%, daily Holt-Winters 34.3%. Forecast: Dec 2011 £1.16M, Jan 2012 £0.58M, Feb 2012 £0.50M — **£2.24M total (80% range £1.81M–£2.66M)**. These are estimates, not guarantees.

## Run locally

```bash
# Backend
cd backend
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload --port 8000              # API docs at http://localhost:8000/api/docs

# Frontend (new terminal) — Vite proxies /api to localhost:8000
cd frontend
npm install
npm run dev                                            # http://localhost:5173
```

Rebuild the cleaned sample from the raw file: `python scripts/prepare_sample.py`.

## Tests

```bash
cd backend && pytest -q                 # 36 tests: data, EDA/KPIs/filters, forecasting, API
cd frontend && npx tsc -b && npm run build
node e2e/flow.mjs path/to/sales.csv out_dir       # full journey in a real browser (backend + `npm run preview` running)
node e2e/recovery.mjs path/to/sales.csv "<restart command>"   # upload survives an API restart
```

## API

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | Liveness (also `/health`) |
| GET | `/api/docs` | Interactive API documentation |
| GET | `/api/datasets/sample` | Open the demo dataset |
| POST | `/api/datasets/upload` | Upload CSV (multipart `file`) → detected mapping + preview |
| POST | `/api/datasets/{id}/quality-check` | Quality report for a mapping, before cleaning |
| POST | `/api/datasets/{id}/prepare` | Confirm mapping + cleaning options |
| GET | `/api/datasets/{id}` | Profile, cleaning log, quality |
| GET | `/api/datasets/{id}/rows` | Page through cleaned sales or returns |
| DELETE | `/api/datasets/{id}` | Reset |
| GET | `/api/analytics/{id}/eda` | Full EDA (cached) |
| POST | `/api/analytics/{id}/dashboard` | KPIs + chart data for filters |
| GET | `/api/analytics/{id}/dimensions/{dim}?q=` | Filter options |
| POST | `/api/forecast/{id}/run` | Start a forecast job |
| GET | `/api/forecast/jobs/{job_id}` | Job status + result |
| GET | `/api/insights/{id}` | Business insights |
| GET | `/api/reports/{id}/{eda\|dashboard\|forecast}.html` | HTML reports |
| GET | `/api/reports/{id}/{forecast\|backtest\|models\|monthly\|dashboard}.csv` | CSV exports |

Errors always look like `{"error": {"code", "message", "details"}}`.

## Deployment (one Vercel project)

Frontend **and** backend deploy together to Vercel from the repo root:

- `vercel.json` builds the site from `frontend/` into `frontend/dist`, and serves `api/index.py` (FastAPI) as a Python function. `/api/*` goes to the function; every other path goes to the single-page app.
- Python 3.12 (`.python-version`), deps from root `requirements.txt`. Raw data, tests and the frontend source are excluded from the function bundle.
- No environment variables are required (same-origin, so no CORS setup). Optional: `MAX_UPLOAD_MB` (default 4 — Vercel caps request bodies at 4.5 MB), `MAX_UPLOAD_ROWS`, `WORKSPACE_TTL_MINUTES`.

Steps: push the repo to GitHub → Vercel → *Add New Project* → import the repo → keep the root directory as `/` → Deploy.

## Data handling and security

- Uploaded files are validated (extension, size, binary/zip detection), parsed as plain text and **never executed**. On the server they are kept **only in memory**, expire after 90 minutes of inactivity, and are dropped on restart or reset. The browser keeps a copy in its own IndexedDB so it can re-send the file after a restart; *Reset analysis* deletes it.
- No secrets are needed. `.env` files are git-ignored; see `.env.example`.
- The site and API share one origin. CORS is only opened for origins listed in `ALLOWED_ORIGINS` (local dev by default).
