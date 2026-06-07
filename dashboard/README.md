# Dashboard

This folder contains the dashboard workflow used to analyse strategy behaviour during **IMC Prosperity 4**.

During the competition, we initially used notebooks and scripts for analysis. As the rounds became more time-constrained, we switched to a dashboard-driven workflow because it made it faster to compare strategy versions, inspect product-level behaviour, and understand why a strategy made or lost money.

## Folder Contents

```text
dashboard/
├── README.md
├── app.py
├── prepare_data.py
├── requirements.txt
└── logs/
    └── round4_results.log
```

## Purpose

The dashboard was used for strategy diagnostics, especially for inspecting:

- product-level PnL,
- price paths across trading days,
- bid/ask spread behaviour,
- spread distributions,
- executed fills,
- fill timing,
- markouts after trades,
- visible PnL paths,
- comparison between strategy versions.

The goal was not only to check whether a strategy was profitable, but also to understand the source and stability of the PnL.

## Data Preparation

The dashboard uses `prepare_data.py` to convert raw Prosperity logs into cleaned dashboard-ready files. The preprocessing script was developed with AI assistance and then adapted to the Prosperity log format used in our analysis.

The script supports both single submission logs and multi-day local backtest logs. In particular, it can analyse three-day backtest outputs by combining day-level market data, constructing a continuous time index across days, and accumulating visible PnL across trading days.

The script parses:

- market/order-book snapshots,
- timestamps and trading days,
- bid/ask prices and volumes,
- mid prices and spreads,
- visible PnL,
- executed trades/fills,
- buy/sell side of our submission trades,
- public market/trade CSVs where available.

It then generates files inside:

```text
dashboard/data/
├── submission_market.csv
├── submission_fills.csv
├── market_all_days.csv
├── public_trades_all_days.csv
└── summary.json
```

The generated `data/` folder is used by `app.py` and does not need to be edited manually.

## Current Example Log

This public version includes one selected example log:

```text
dashboard/logs/round4_results.log
```

This log is included as a representative example so that the dashboard workflow can be demonstrated without adding the full raw competition archive.

## How to Run

From the `dashboard/` folder, install the dashboard dependencies:

```bash
pip install -r requirements.txt
```

Then prepare the data:

```bash
python prepare_data.py
```

Finally, run the dashboard:

```bash
streamlit run app.py
```

The dashboard should open locally at:

```text
http://localhost:8501
```

## Configuration

To analyse a different log, edit the configuration block at the top of `prepare_data.py`.

For the current public example log, the path should be:

```python
SUBMISSION_LOG = BASE / "logs" / "round4_results.log"
```

If the log is stored somewhere else, update the path accordingly.

For multi-day local backtest analysis, the preprocessing script can also load price and trade CSV files matching the Prosperity naming pattern:

```text
prices_round_<ROUND_NUMBER>_day_*.csv
trades_round_<ROUND_NUMBER>_day_*.csv
```

The preprocessing script is intentionally simple and was designed for quick competition analysis rather than as a fully general production parser.

## Dashboard Overview

The dashboard view includes diagnostics such as spread histograms, markout overlays, and visible PnL paths.

The overview screenshot is stored in:

```text
../assets/dashboard_overview.png
```

## How We Used the Dashboard

The dashboard helped us compare strategy versions more quickly than static notebooks. In particular, it was useful for:

- identifying products with stable versus unstable PnL,
- checking whether a strategy was taking excessive inventory risk,
- inspecting whether fills were followed by favourable or adverse price moves,
- comparing behaviour across different trading days,
- deciding which products or signals to keep in later strategy versions.

This made the analysis more practical during the competition, where strategy iteration speed was important.

## AI-Assisted Development Note

Parts of the dashboard implementation were AI-assisted, including the Streamlit/Plotly interface and parts of the `prepare_data.py` preprocessing script.

The AI assistance was mainly used for scaffolding, parsing utilities, and accelerating implementation under competition time pressure. The choice of diagnostics, interpretation of the outputs, strategy analysis, and trading decisions were performed by the team.

## Limitations

This dashboard was built as a practical competition tool. It was useful for fast iteration and post-round analysis, but it is not intended to be a production-grade trading analytics system.

In particular:

- it expects Prosperity-style logs,
- some paths are configured manually,
- generated `data/` files depend on the selected log,
- the dashboard should be interpreted as a diagnostic tool rather than a complete backtesting engine.