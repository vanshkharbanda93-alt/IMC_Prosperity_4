import ast
import json
import io
import re
from pathlib import Path

import pandas as pd


# ============================================================
# CHANGE ONLY THIS BLOCK WHEN YOU WANT TO USE A DIFFERENT LOG
# ============================================================

BASE = Path(__file__).resolve().parent
DATA_DIR = BASE / "data"
DATA_DIR.mkdir(exist_ok=True)

# Example: if files are prices_round_3_day_*.csv, use ROUND_NUMBER = 3
ROUND_NUMBER = 1

# Change this filename whenever you run a new backtest / IMC log
#SUBMISSION_LOG = BASE.parent / "ROUND_4" / "logs" / "545123_round4_submission.log"
SUBMISSION_LOG = BASE / "logs" / "round1_original_all.log"

# Folder containing prices_round_<ROUND_NUMBER>_day_*.csv and trades_round_<ROUND_NUMBER>_day_*.csv
PRICE_DIR = BASE.parent / "ROUND_1"

# Adds blank rows between days so Plotly does not draw fake connecting lines
ADD_DAY_GAPS = True

# PnL handling for submission logs:
# - "preserve" keeps the PnL exactly as written in the backtester log.
#   Use this when logs were generated with --merge-pnl.
# - "accumulate" should only be used for logs where PnL resets each day.
# The dashboard previously double-counted PnL because it accumulated logs that
# were already cumulative.
PNL_MODE = "preserve"

# ============================================================


EMPTY_FILLS_COLUMNS = ["day", "timestamp", "time_index", "product", "side", "price", "quantity"]


def make_time_index(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    if df.empty or "timestamp" not in df.columns:
        return df

    df["timestamp"] = pd.to_numeric(df["timestamp"], errors="coerce")

    if "day" in df.columns:
        df["day"] = pd.to_numeric(df["day"], errors="coerce")
        base_day = df["day"].dropna().min()

        if pd.isna(base_day):
            df["time_index"] = df["timestamp"]
        else:
            df["time_index"] = (df["day"].fillna(base_day) - base_day) * 1_000_000 + df["timestamp"]
    else:
        df["time_index"] = df["timestamp"]

    # Important: keep market and fills time_index as the same dtype for merge_asof in app.py.
    df["time_index"] = pd.to_numeric(df["time_index"], errors="coerce").astype("float64")

    return df


def add_market_features(market: pd.DataFrame) -> pd.DataFrame:
    """Add simple order-book features used by the dashboard."""
    if market.empty:
        return market

    market = market.copy()

    if {"ask_price_1", "bid_price_1"}.issubset(market.columns):
        market["spread"] = market["ask_price_1"] - market["bid_price_1"]

    return market



def sanitize_order_book_prices(market: pd.DataFrame) -> pd.DataFrame:
    """Convert impossible/missing price values to NA and recompute spread safely.

    Some backtester/activity logs encode missing mid prices as 0 when one side
    of the book is empty. If plotted directly, these create misleading vertical
    lines down to zero.
    """
    if market.empty:
        return market

    market = market.copy()
    price_cols = [
        "bid_price_1", "bid_price_2", "bid_price_3",
        "ask_price_1", "ask_price_2", "ask_price_3",
        "mid_price",
    ]

    for col in price_cols:
        if col in market.columns:
            market.loc[market[col] <= 0, col] = pd.NA

    if {"bid_price_1", "ask_price_1"}.issubset(market.columns):
        valid_top = market["bid_price_1"].notna() & market["ask_price_1"].notna()

        if "mid_price" in market.columns:
            missing_mid = market["mid_price"].isna() & valid_top
            market.loc[missing_mid, "mid_price"] = (
                market.loc[missing_mid, "bid_price_1"] + market.loc[missing_mid, "ask_price_1"]
            ) / 2
            market.loc[~valid_top, "mid_price"] = pd.NA

        market["spread"] = market["ask_price_1"] - market["bid_price_1"]
        market.loc[~valid_top, "spread"] = pd.NA

    return market

def accumulate_pnl_across_days(market: pd.DataFrame) -> pd.DataFrame:
    if market.empty or "pnl" not in market.columns or "day" not in market.columns:
        return market

    market = market.copy()
    market["day_pnl"] = market["pnl"]

    groups = market.groupby("symbol", sort=False) if "symbol" in market.columns else [("ALL", market)]
    fixed_parts = []

    for _, group in groups:
        group = group.sort_values(["day", "timestamp"]).copy()
        offset = 0.0

        for day in sorted(group["day"].dropna().unique()):
            mask = group["day"] == day
            group.loc[mask, "pnl"] = group.loc[mask, "day_pnl"] + offset

            day_values = group.loc[mask, "day_pnl"].dropna()
            if not day_values.empty:
                offset += float(day_values.iloc[-1])

        fixed_parts.append(group)

    return pd.concat(fixed_parts, ignore_index=True) if fixed_parts else market


def add_day_gap_rows(market: pd.DataFrame) -> pd.DataFrame:
    if market.empty or "day" not in market.columns or "symbol" not in market.columns or "time_index" not in market.columns:
        return market

    parts = []

    for _, group in market.groupby("symbol", sort=False):
        group = group.sort_values(["day", "timestamp"]).copy()
        days = sorted(group["day"].dropna().unique())

        for i, day in enumerate(days):
            day_part = group[group["day"] == day].copy()
            parts.append(day_part)

            if i == len(days) - 1 or day_part.empty:
                continue

            last_row = day_part.iloc[-1].copy()
            gap_row = last_row.copy()

            gap_row["timestamp"] = pd.NA
            gap_row["time_index"] = float(last_row["time_index"]) + 1.0
            gap_row["is_gap"] = True

            break_cols = [
                "bid_price_1", "bid_price_2", "bid_price_3",
                "ask_price_1", "ask_price_2", "ask_price_3",
                "bid_volume_1", "bid_volume_2", "bid_volume_3",
                "ask_volume_1", "ask_volume_2", "ask_volume_3",
                "mid_price", "spread", "pnl", "day_pnl",
            ]

            for col in break_cols:
                if col in gap_row.index:
                    gap_row[col] = pd.NA

            parts.append(pd.DataFrame([gap_row]))

    if not parts:
        return market

    out = pd.concat(parts, ignore_index=True)

    if "is_gap" not in out.columns:
        out["is_gap"] = False
    else:
        out["is_gap"] = out["is_gap"].fillna(False)

    out["time_index"] = pd.to_numeric(out["time_index"], errors="coerce").astype("float64")

    return out.sort_values(["symbol", "time_index"]).reset_index(drop=True)


def normalize_market(market: pd.DataFrame) -> pd.DataFrame:
    if market.empty:
        return market

    market = market.copy()
    market = market.rename(columns={
        "product": "symbol",
        "profit_and_loss": "pnl",
    })

    numeric_cols = [
        "day", "timestamp",
        "bid_price_1", "bid_volume_1",
        "bid_price_2", "bid_volume_2",
        "bid_price_3", "bid_volume_3",
        "ask_price_1", "ask_volume_1",
        "ask_price_2", "ask_volume_2",
        "ask_price_3", "ask_volume_3",
        "mid_price", "pnl", "spread",
    ]

    for col in numeric_cols:
        if col in market.columns:
            market[col] = pd.to_numeric(market[col], errors="coerce")

    market = sanitize_order_book_prices(market)
    market = add_market_features(market)
    market = make_time_index(market)

    # Important: preserve PnL from backtester logs by default.
    # If the log was produced with --merge-pnl, the PnL is already cumulative
    # across days. Accumulating again will double-count later days in the dashboard.
    if PNL_MODE == "accumulate":
        market = accumulate_pnl_across_days(market)
    elif "pnl" in market.columns:
        market = market.copy()
        market["day_pnl"] = market["pnl"]

    if ADD_DAY_GAPS:
        market = add_day_gap_rows(market)

    return market


def infer_fill_side(row) -> str:
    side = str(row.get("side", "")).upper()
    if side in {"BUY", "SELL"}:
        return side

    buyer = str(row.get("buyer", "")).upper()
    seller = str(row.get("seller", "")).upper()

    if buyer.startswith("SUBMISSION"):
        return "BUY"
    if seller.startswith("SUBMISSION"):
        return "SELL"

    return "MARKET"


def attach_fill_day(fills: pd.DataFrame, market: pd.DataFrame) -> pd.DataFrame:
    fills = fills.copy()

    if fills.empty:
        return fills

    if "day" in fills.columns and fills["day"].notna().any():
        return fills

    if market.empty or "day" not in market.columns or "timestamp" not in market.columns:
        fills["day"] = pd.NA
        return fills

    clean_market = market[market["timestamp"].notna()].copy()
    day_lookup = clean_market[["timestamp", "day"]].dropna().drop_duplicates()

    if day_lookup.empty:
        fills["day"] = pd.NA
        return fills

    unique_day_count = day_lookup.groupby("timestamp")["day"].nunique()
    safe_timestamps = unique_day_count[unique_day_count == 1].index
    safe_lookup = day_lookup[day_lookup["timestamp"].isin(safe_timestamps)].drop_duplicates("timestamp")

    fills = fills.merge(safe_lookup, on="timestamp", how="left")

    if fills["day"].isna().any():
        first_day = clean_market["day"].dropna().min()
        fills["day"] = fills["day"].fillna(first_day)

    return fills


def empty_fills_df() -> pd.DataFrame:
    fills = pd.DataFrame(columns=EMPTY_FILLS_COLUMNS)
    fills["time_index"] = fills["time_index"].astype("float64")
    return fills


def normalize_fills(trades, market: pd.DataFrame) -> pd.DataFrame:
    fills = pd.DataFrame(trades)

    if fills.empty:
        return empty_fills_df()

    fills = fills.rename(columns={
        "symbol": "product",
        "qty": "quantity",
    })

    for col in ["day", "timestamp", "price", "quantity"]:
        if col in fills.columns:
            fills[col] = pd.to_numeric(fills[col], errors="coerce")

    fills["side"] = fills.apply(infer_fill_side, axis=1)
    fills = fills[fills["side"].isin(["BUY", "SELL"])].copy()

    if fills.empty:
        return empty_fills_df()

    fills["quantity"] = fills["quantity"].abs()
    fills = attach_fill_day(fills, market)
    fills = make_time_index(fills)

    for col in EMPTY_FILLS_COLUMNS:
        if col not in fills.columns:
            fills[col] = pd.NA

    fills = fills[EMPTY_FILLS_COLUMNS].sort_values(["time_index", "product", "side"]).reset_index(drop=True)
    fills["time_index"] = pd.to_numeric(fills["time_index"], errors="coerce").astype("float64")

    return fills


def parse_trade_history(raw_trade_history):
    if raw_trade_history is None:
        return []

    if isinstance(raw_trade_history, list):
        return raw_trade_history

    if not isinstance(raw_trade_history, str):
        return []

    text = raw_trade_history.strip()

    if not text:
        return []

    start = text.find("[")
    end = text.rfind("]")

    if start != -1 and end != -1 and end > start:
        text = text[start:end + 1]

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    try:
        return ast.literal_eval(text)
    except Exception:
        pass

    print("WARNING: Could not parse Trade History. Dashboard will show market/PnL but no fills.")
    return []


def load_json_submission_log(text: str):
    obj = json.loads(text)

    activities = obj.get("activitiesLog") or obj.get("activities_log")
    trade_history = obj.get("tradeHistory") or obj.get("trade_history") or []

    if activities is None:
        raise ValueError("JSON log does not contain activitiesLog.")

    if isinstance(activities, str):
        market = pd.read_csv(io.StringIO(activities), sep=";")
    else:
        market = pd.DataFrame(activities)

    market = normalize_market(market)
    trades = parse_trade_history(trade_history)
    fills = normalize_fills(trades, market)

    return market, fills, "json"


def extract_section(text: str, start_marker: str, end_marker: str | None = None) -> str:
    lower = text.lower()
    start = lower.find(start_marker.lower())

    if start == -1:
        raise ValueError(f"Could not find section marker: {start_marker}")

    start += len(start_marker)

    if end_marker is None:
        return text[start:].strip()

    end = lower.find(end_marker.lower(), start)

    if end == -1:
        return text[start:].strip()

    return text[start:end].strip()


def load_sectioned_submission_log(text: str):
    activities_text = extract_section(text, "Activities log:", "Trade History:")
    trades_text = extract_section(text, "Trade History:", None)

    if not activities_text:
        raise ValueError("Activities log section is empty.")

    market = pd.read_csv(io.StringIO(activities_text), sep=";")
    market = normalize_market(market)

    trades = parse_trade_history(trades_text)
    fills = normalize_fills(trades, market)

    return market, fills, "sectioned"


def load_submission_log(path: Path):
    text = path.read_text()

    try:
        return load_json_submission_log(text)
    except Exception:
        pass

    return load_sectioned_submission_log(text)


def parse_day_from_filename(path: Path):
    match = re.search(r"day_(-?\d+)", path.stem)

    if match:
        return int(match.group(1))

    return None


def load_price_csvs(paths):
    dfs = []

    for path in paths:
        df = pd.read_csv(path, sep=";")
        day = parse_day_from_filename(path)

        if day is not None and "day" not in df.columns:
            df["day"] = day

        dfs.append(df)

    if not dfs:
        return pd.DataFrame()

    market = pd.concat(dfs, ignore_index=True)
    return normalize_market(market)


def load_trade_csvs(paths):
    dfs = []

    for path in paths:
        df = pd.read_csv(path, sep=";")
        day = parse_day_from_filename(path)

        if day is not None and "day" not in df.columns:
            df["day"] = day

        dfs.append(df)

    if not dfs:
        return pd.DataFrame()

    trades = pd.concat(dfs, ignore_index=True)
    trades = trades.rename(columns={
        "symbol": "product",
        "quantity": "qty",
    })

    trades = make_time_index(trades)
    trades["time_index"] = pd.to_numeric(trades["time_index"], errors="coerce").astype("float64")

    return trades


def force_time_index_float(*dfs: pd.DataFrame) -> None:
    for df in dfs:
        if df is not None and not df.empty and "time_index" in df.columns:
            df["time_index"] = pd.to_numeric(df["time_index"], errors="coerce").astype("float64")


def main():
    price_paths = sorted(PRICE_DIR.glob(f"prices_round_{ROUND_NUMBER}_day_*.csv"))
    trade_paths = sorted(PRICE_DIR.glob(f"trades_round_{ROUND_NUMBER}_day_*.csv"))

    log_format = "none"

    if SUBMISSION_LOG.exists():
        market, fills, log_format = load_submission_log(SUBMISSION_LOG)
    else:
        print(f"WARNING: Log file not found: {SUBMISSION_LOG}")
        market = load_price_csvs(price_paths)
        fills = empty_fills_df()

    full_market = load_price_csvs(price_paths) if price_paths else market.copy()
    public_trades = load_trade_csvs(trade_paths) if trade_paths else pd.DataFrame()

    # Force dtype before saving so app.py reads both market and fills time_index as float.
    force_time_index_float(market, fills, full_market, public_trades)

    market.to_csv(DATA_DIR / "submission_market.csv", index=False)
    fills.to_csv(DATA_DIR / "submission_fills.csv", index=False)
    full_market.to_csv(DATA_DIR / "market_all_days.csv", index=False)

    public_trades_path = DATA_DIR / "public_trades_all_days.csv"

    if not public_trades.empty:
        public_trades.to_csv(public_trades_path, index=False)
    elif public_trades_path.exists():
        public_trades_path.unlink()

    total_cumulative_pnl = 0.0

    if not market.empty and {"symbol", "pnl"}.issubset(market.columns):
        clean_market = market[market["pnl"].notna()].copy()

        if not clean_market.empty:
            total_cumulative_pnl = float(
                clean_market.sort_values("time_index").groupby("symbol")["pnl"].last().sum()
            )

    summary = {
        "round": ROUND_NUMBER,
        "log_file": SUBMISSION_LOG.name,
        "log_path": str(SUBMISSION_LOG),
        "log_format": log_format,
        "pnl_mode": PNL_MODE,
        "price_dir": str(PRICE_DIR),
        "submission_market_rows": int(len(market)),
        "submission_fill_rows": int(len(fills)),
        "all_market_rows": int(len(full_market)),
        "public_trade_rows": int(len(public_trades)) if not public_trades.empty else 0,
        "total_cumulative_pnl": total_cumulative_pnl,
    }

    pd.Series(summary).to_json(DATA_DIR / "summary.json", indent=2)
    print(summary)


if __name__ == "__main__":
    main()
