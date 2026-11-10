"""Sales Intelligence Workspace engine.

The package mirrors the workspace pipeline. Each stage only consumes the
output of the stage before it:

    datahub   -> read a CSV safely, detect and validate columns
    quality   -> quality report, cleaning rules, canonical sales table
    eda       -> descriptive, time-based and dimensional exploration
    analytics -> KPIs, filters and the interactive dashboard payload
    forecasting -> candidate models, rolling-origin backtests, 3-month forecast
    insights  -> data-driven observations and recommendations
    reports   -> downloadable CSV and HTML reports

Nothing in this package knows about HTTP. The FastAPI app in ``app`` wraps it.
"""

__version__ = "1.0.0"
