from pathlib import Path
import json
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

BASE = Path(__file__).resolve().parent
DATA = BASE / "data"

DAY_LENGTH = 1_000_000

CHART_COLORS = {
    "mid": "#8FD3FF",
    "bid": "#0068B7",
    "ask": "#C98F8F",
    "buy": "#FF3333",
    "sell": "#72E69A",
    "pnl": "#8FD3FF",
    "position": "#8FD3FF",
}

st.set_page_config(page_title="Prosperity Dashboard", layout="wide")

st.markdown(
    """
    <style>
    .block-container {
        max-width: 99vw;
        padding-left: 1.25rem;
        padding-right: 1.25rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data
def load_data():
    market = pd.read_csv(DATA / "submission_market.csv")
    fills = pd.read_csv(DATA / "submission_fills.csv")
    market_all = pd.read_csv(DATA / "market_all_days.csv")

    public_trades_path = DATA / "public_trades_all_days.csv"
    if public_trades_path.exists():
        public_trades = pd.read_csv(public_trades_path)
    else:
        public_trades = pd.DataFrame()

    summary_path = DATA / "summary.json"
    summary = {}
    if summary_path.exists():
        with open(summary_path, "r") as f:
            summary = json.load(f)

    return market, fills, market_all, public_trades, summary


def add_midprice(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if "mid_price" in out.columns:
        out["mid"] = out["mid_price"]
    elif {"bid_price_1", "ask_price_1"}.issubset(out.columns):
        out["mid"] = (out["bid_price_1"] + out["ask_price_1"]) / 2
    return out


def add_spread(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if {"ask_price_1", "bid_price_1"}.issubset(out.columns):
        out["spread"] = out["ask_price_1"] - out["bid_price_1"]
    return out


def sanitize_market_for_plot(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    price_cols = [
        "bid_price_1", "bid_price_2", "bid_price_3",
        "ask_price_1", "ask_price_2", "ask_price_3",
        "mid_price", "mid",
    ]
    for col in price_cols:
        if col in out.columns:
            out.loc[out[col] <= 0, col] = pd.NA

    if {"bid_price_1", "ask_price_1"}.issubset(out.columns):
        valid_top = out["bid_price_1"].notna() & out["ask_price_1"].notna()

        if "mid_price" in out.columns:
            missing_mid = out["mid_price"].isna() & valid_top
            out.loc[missing_mid, "mid_price"] = (
                out.loc[missing_mid, "bid_price_1"] + out.loc[missing_mid, "ask_price_1"]
            ) / 2
            out.loc[~valid_top, "mid_price"] = pd.NA

        if "mid" in out.columns:
            missing_mid = out["mid"].isna() & valid_top
            out.loc[missing_mid, "mid"] = (
                out.loc[missing_mid, "bid_price_1"] + out.loc[missing_mid, "ask_price_1"]
            ) / 2
            out.loc[~valid_top, "mid"] = pd.NA

        out["spread"] = out["ask_price_1"] - out["bid_price_1"]
        out.loc[~valid_top, "spread"] = pd.NA

    return out


def clean_market_rows(df: pd.DataFrame) -> pd.DataFrame:
    out = sanitize_market_for_plot(df)
    if "timestamp" in out.columns:
        out = out[out["timestamp"].notna()].copy()
    return out


def format_day_label(day) -> str:
    try:
        day_float = float(day)
        if day_float.is_integer():
            return f"Day {int(day_float)}"
    except Exception:
        pass
    return f"Day {day}"


def add_local_day_x(
    df: pd.DataFrame,
    source_col: str | None = None,
    out_col: str = "plot_timestamp",
) -> pd.DataFrame:
    """
    Create a local 0 -> 1M x-axis for an already-filtered single-day dataframe.

    Handles both:
    - local timestamps: every day already runs 0 -> 1M
    - global block timestamps: Day -2 = 0 -> 1M, Day -1 = 1M -> 2M, Day 0 = 2M -> 3M

    After this transform, every day is displayed on the same 0 -> 1M x-scale.
    """
    out = df.copy()

    if out.empty:
        out[out_col] = pd.Series(dtype="float64")
        return out

    if source_col is None:
        if "timestamp" in out.columns:
            source_col = "timestamp"
        elif "time_index" in out.columns:
            source_col = "time_index"
        else:
            out[out_col] = pd.NA
            return out

    x = pd.to_numeric(out[source_col], errors="coerce")
    valid_x = x.dropna()

    if valid_x.empty:
        out[out_col] = pd.NA
        return out

    min_x = float(valid_x.min())
    max_x = float(valid_x.max())

    if 0 <= min_x and max_x <= DAY_LENGTH:
        local_x = x
    else:
        block_start = float((min_x // DAY_LENGTH) * DAY_LENGTH)
        local_x = x - block_start

        local_valid = local_x.dropna()
        if not local_valid.empty:
            if local_valid.min() < -1 or local_valid.max() > DAY_LENGTH * 1.05:
                local_x = x - min_x

    out[out_col] = pd.to_numeric(local_x, errors="coerce").astype("float64")
    return out


def get_fill_product_column(fills: pd.DataFrame) -> str:
    if "product" in fills.columns:
        return "product"
    if "symbol" in fills.columns:
        return "symbol"
    raise KeyError("Could not find product column in fills file.")


def get_public_product_column(public_trades: pd.DataFrame) -> str:
    if "product" in public_trades.columns:
        return "product"
    if "symbol" in public_trades.columns:
        return "symbol"
    return ""


def compute_fill_stats(product_fills: pd.DataFrame) -> pd.DataFrame:
    if product_fills.empty:
        return pd.DataFrame()

    return (
        product_fills.groupby("side")
        .agg(
            fills=("quantity", "count"),
            total_qty=("quantity", "sum"),
            avg_price=("price", "mean"),
        )
        .reset_index()
    )


def compute_spread_by_day(product_market: pd.DataFrame) -> pd.DataFrame:
    market = clean_market_rows(add_spread(product_market))

    if market.empty or "spread" not in market.columns:
        return pd.DataFrame()

    market = market.dropna(subset=["spread"]).copy()
    if market.empty:
        return pd.DataFrame()

    if "day" in market.columns and market["day"].notna().any():
        group_cols = ["day"]
    else:
        market["day"] = "selected data"
        group_cols = ["day"]

    spread_stats = (
        market.groupby(group_cols, sort=True)
        .agg(
            snapshots=("spread", "count"),
            median_spread=("spread", "median"),
            mean_spread=("spread", "mean"),
            min_spread=("spread", "min"),
            max_spread=("spread", "max"),
        )
        .reset_index()
    )

    return spread_stats


def compute_analysis(product_fills: pd.DataFrame, product_market: pd.DataFrame) -> pd.DataFrame:
    if product_fills.empty or product_market.empty:
        return pd.DataFrame()

    fills = product_fills.copy().sort_values("time_index")
    market = add_midprice(clean_market_rows(product_market.copy())).sort_values("time_index")

    if "mid" not in market.columns:
        return pd.DataFrame()

    market_now = market[["time_index", "mid"]].dropna().copy()
    market_now = market_now.rename(columns={"mid": "mid_at_or_before_fill"})

    market_next = market[["time_index", "mid"]].dropna().copy()
    market_next = market_next.rename(columns={"mid": "mid_after_fill"})

    merged = pd.merge_asof(
        fills,
        market_now,
        on="time_index",
        direction="backward",
        allow_exact_matches=True,
    )

    merged = pd.merge_asof(
        merged.sort_values("time_index"),
        market_next.sort_values("time_index"),
        on="time_index",
        direction="forward",
        allow_exact_matches=False,
    )

    merged = merged.dropna(subset=["mid_at_or_before_fill", "mid_after_fill"]).copy()

    def calc_markout(row):
        side = str(row["side"]).upper()
        if side == "BUY":
            return row["mid_after_fill"] - row["price"]
        if side == "SELL":
            return row["price"] - row["mid_after_fill"]
        return 0.0

    merged["markout"] = merged.apply(calc_markout, axis=1)
    merged["markout_sign"] = merged["markout"].apply(lambda x: "Positive" if x > 0 else "Negative")

    return merged


def build_combined_price_chart(product_market: pd.DataFrame, product_fills: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    market = clean_market_rows(product_market.copy()).sort_values("time_index")

    if not market.empty:
        if "bid_price_1" in market.columns:
            fig.add_trace(go.Scatter(
                x=market["time_index"],
                y=market["bid_price_1"],
                mode="lines",
                name="Best bid",
                line=dict(width=0.55, color=CHART_COLORS["bid"]),
                opacity=0.35,
                connectgaps=False,
            ))

        if "ask_price_1" in market.columns:
            fig.add_trace(go.Scatter(
                x=market["time_index"],
                y=market["ask_price_1"],
                mode="lines",
                name="Best ask",
                line=dict(width=0.55, color=CHART_COLORS["ask"]),
                opacity=0.35,
                connectgaps=False,
            ))

        if "mid_price" in market.columns:
            fig.add_trace(go.Scatter(
                x=market["time_index"],
                y=market["mid_price"],
                mode="lines",
                name="Mid price",
                line=dict(width=1.35, color=CHART_COLORS["mid"]),
                opacity=0.95,
                connectgaps=False,
            ))

    if not product_fills.empty:
        buys = product_fills[product_fills["side"] == "BUY"]
        sells = product_fills[product_fills["side"] == "SELL"]

        if not buys.empty:
            fig.add_trace(go.Scatter(
                x=buys["time_index"],
                y=buys["price"],
                mode="markers",
                name="Your buys",
                marker=dict(
                    symbol="triangle-up",
                    size=6,
                    color=CHART_COLORS["buy"],
                    opacity=0.78,
                ),
            ))

        if not sells.empty:
            fig.add_trace(go.Scatter(
                x=sells["time_index"],
                y=sells["price"],
                mode="markers",
                name="Your sells",
                marker=dict(
                    symbol="triangle-down",
                    size=6,
                    color=CHART_COLORS["sell"],
                    opacity=0.78,
                ),
            ))

    fig.update_layout(
        height=620,
        margin=dict(l=25, r=25, t=60, b=55),
        legend=dict(orientation="h", y=1.08, x=0),
        hovermode="x unified",
    )
    return fig


def build_day_panel_price_chart(product_market: pd.DataFrame, product_fills: pd.DataFrame) -> go.Figure:
    """Plot days side by side with equal 0->1M x-width and consistent colors."""
    market = clean_market_rows(product_market.copy())

    if market.empty:
        return go.Figure()

    if "day" not in market.columns or not market["day"].notna().any():
        return build_combined_price_chart(product_market, product_fills)

    days = sorted(market["day"].dropna().unique())
    if not days:
        return go.Figure()

    fig = make_subplots(
        rows=1,
        cols=len(days),
        shared_yaxes=True,
        horizontal_spacing=0.035,
        subplot_titles=[format_day_label(day) for day in days],
    )

    for col, day in enumerate(days, start=1):
        day_market = market[market["day"] == day].copy()
        day_market = add_local_day_x(day_market).sort_values("plot_timestamp")

        if "bid_price_1" in day_market.columns:
            fig.add_trace(
                go.Scatter(
                    x=day_market["plot_timestamp"],
                    y=day_market["bid_price_1"],
                    mode="lines",
                    name="Best bid",
                    line=dict(width=0.55, color=CHART_COLORS["bid"]),
                    opacity=0.35,
                    showlegend=(col == 1),
                    connectgaps=False,
                ),
                row=1,
                col=col,
            )

        if "ask_price_1" in day_market.columns:
            fig.add_trace(
                go.Scatter(
                    x=day_market["plot_timestamp"],
                    y=day_market["ask_price_1"],
                    mode="lines",
                    name="Best ask",
                    line=dict(width=0.55, color=CHART_COLORS["ask"]),
                    opacity=0.35,
                    showlegend=(col == 1),
                    connectgaps=False,
                ),
                row=1,
                col=col,
            )

        if "mid_price" in day_market.columns:
            fig.add_trace(
                go.Scatter(
                    x=day_market["plot_timestamp"],
                    y=day_market["mid_price"],
                    mode="lines",
                    name="Mid price",
                    line=dict(width=1.45, color=CHART_COLORS["mid"]),
                    opacity=0.95,
                    showlegend=(col == 1),
                    connectgaps=False,
                ),
                row=1,
                col=col,
            )

        if not product_fills.empty and "day" in product_fills.columns:
            day_fills = product_fills[product_fills["day"] == day].copy()
            day_fills = add_local_day_x(day_fills).sort_values("plot_timestamp")

            buys = day_fills[day_fills["side"] == "BUY"]
            sells = day_fills[day_fills["side"] == "SELL"]

            if not buys.empty:
                fig.add_trace(
                    go.Scatter(
                        x=buys["plot_timestamp"],
                        y=buys["price"],
                        mode="markers",
                        name="Your buys",
                        marker=dict(
                            symbol="triangle-up",
                            size=6,
                            color=CHART_COLORS["buy"],
                            opacity=0.78,
                        ),
                        showlegend=(col == 1),
                    ),
                    row=1,
                    col=col,
                )

            if not sells.empty:
                fig.add_trace(
                    go.Scatter(
                        x=sells["plot_timestamp"],
                        y=sells["price"],
                        mode="markers",
                        name="Your sells",
                        marker=dict(
                            symbol="triangle-down",
                            size=6,
                            color=CHART_COLORS["sell"],
                            opacity=0.78,
                        ),
                        showlegend=(col == 1),
                    ),
                    row=1,
                    col=col,
                )

        fig.update_xaxes(
            title_text="timestamp",
            range=[0, DAY_LENGTH],
            row=1,
            col=col,
        )

    fig.update_yaxes(title_text="price", row=1, col=1)
    fig.update_layout(
        autosize=True,
        height=620,
        margin=dict(l=25, r=25, t=85, b=60),
        legend=dict(orientation="h", y=1.12, x=0),
        hovermode="x unified",
    )
    return fig


def build_day_stacked_price_chart(product_market: pd.DataFrame, product_fills: pd.DataFrame) -> go.Figure:
    """Plot each day vertically with local 0->1M timestamp and consistent colors."""
    market = clean_market_rows(product_market.copy())

    if market.empty:
        return go.Figure()

    if "day" not in market.columns or not market["day"].notna().any():
        return build_combined_price_chart(product_market, product_fills)

    days = sorted(market["day"].dropna().unique())
    if not days:
        return go.Figure()

    fig = make_subplots(
        rows=len(days),
        cols=1,
        shared_xaxes=False,
        shared_yaxes=False,
        vertical_spacing=0.055,
        subplot_titles=[format_day_label(day) for day in days],
    )

    for row, day in enumerate(days, start=1):
        day_market = market[market["day"] == day].copy()
        day_market = add_local_day_x(day_market).sort_values("plot_timestamp")

        if "bid_price_1" in day_market.columns:
            fig.add_trace(
                go.Scatter(
                    x=day_market["plot_timestamp"],
                    y=day_market["bid_price_1"],
                    mode="lines",
                    name="Best bid",
                    line=dict(width=0.55, color=CHART_COLORS["bid"]),
                    opacity=0.35,
                    showlegend=(row == 1),
                    connectgaps=False,
                ),
                row=row,
                col=1,
            )

        if "ask_price_1" in day_market.columns:
            fig.add_trace(
                go.Scatter(
                    x=day_market["plot_timestamp"],
                    y=day_market["ask_price_1"],
                    mode="lines",
                    name="Best ask",
                    line=dict(width=0.55, color=CHART_COLORS["ask"]),
                    opacity=0.35,
                    showlegend=(row == 1),
                    connectgaps=False,
                ),
                row=row,
                col=1,
            )

        if "mid_price" in day_market.columns:
            fig.add_trace(
                go.Scatter(
                    x=day_market["plot_timestamp"],
                    y=day_market["mid_price"],
                    mode="lines",
                    name="Mid price",
                    line=dict(width=1.45, color=CHART_COLORS["mid"]),
                    opacity=0.95,
                    showlegend=(row == 1),
                    connectgaps=False,
                ),
                row=row,
                col=1,
            )

        if not product_fills.empty and "day" in product_fills.columns:
            day_fills = product_fills[product_fills["day"] == day].copy()
            day_fills = add_local_day_x(day_fills).sort_values("plot_timestamp")

            buys = day_fills[day_fills["side"] == "BUY"]
            sells = day_fills[day_fills["side"] == "SELL"]

            if not buys.empty:
                fig.add_trace(
                    go.Scatter(
                        x=buys["plot_timestamp"],
                        y=buys["price"],
                        mode="markers",
                        name="Your buys",
                        marker=dict(
                            symbol="triangle-up",
                            size=6,
                            color=CHART_COLORS["buy"],
                            opacity=0.78,
                        ),
                        showlegend=(row == 1),
                    ),
                    row=row,
                    col=1,
                )

            if not sells.empty:
                fig.add_trace(
                    go.Scatter(
                        x=sells["plot_timestamp"],
                        y=sells["price"],
                        mode="markers",
                        name="Your sells",
                        marker=dict(
                            symbol="triangle-down",
                            size=6,
                            color=CHART_COLORS["sell"],
                            opacity=0.78,
                        ),
                        showlegend=(row == 1),
                    ),
                    row=row,
                    col=1,
                )

        fig.update_xaxes(
            title_text=("timestamp" if row == len(days) else ""),
            range=[0, DAY_LENGTH],
            showticklabels=True,
            row=row,
            col=1,
        )
        fig.update_yaxes(title_text="price", row=row, col=1)

    fig.update_layout(
        autosize=True,
        height=max(950, 390 * len(days)),
        margin=dict(l=25, r=25, t=85, b=65),
        legend=dict(orientation="h", y=1.035, x=0),
        hovermode="x unified",
    )
    return fig


def build_spread_histogram_by_day(product_market: pd.DataFrame) -> go.Figure:
    market = clean_market_rows(add_spread(product_market))

    if market.empty or "spread" not in market.columns:
        return go.Figure()

    market = market.dropna(subset=["spread"]).copy()
    if market.empty:
        return go.Figure()

    if "day" not in market.columns or not market["day"].notna().any():
        fig = px.histogram(market, x="spread", nbins=30)
        fig.update_layout(height=360, margin=dict(l=20, r=20, t=30, b=30))
        return fig

    days = sorted(market["day"].dropna().unique())
    fig = make_subplots(
        rows=1,
        cols=len(days),
        shared_yaxes=True,
        horizontal_spacing=0.025,
        subplot_titles=[format_day_label(day) for day in days],
    )

    for col, day in enumerate(days, start=1):
        day_market = market[market["day"] == day]
        fig.add_trace(
            go.Histogram(
                x=day_market["spread"],
                nbinsx=30,
                name=f"Day {day}",
                showlegend=False,
            ),
            row=1,
            col=col,
        )
        fig.update_xaxes(title_text="spread", row=1, col=col)

    fig.update_yaxes(title_text="count", row=1, col=1)
    fig.update_layout(
        height=360,
        bargap=0.05,
        margin=dict(l=20, r=20, t=60, b=30),
    )
    return fig


def build_combined_pnl_chart(product_market: pd.DataFrame) -> go.Figure:
    market = clean_market_rows(product_market.copy())
    fig = go.Figure()

    if not market.empty and "pnl" in market.columns:
        market = market.dropna(subset=["pnl"]).sort_values("time_index")
        if not market.empty:
            fig.add_trace(go.Scatter(
                x=market["time_index"],
                y=market["pnl"],
                mode="lines",
                name="Visible PnL",
                line=dict(width=1.15, color=CHART_COLORS["pnl"]),
                connectgaps=False,
            ))

    fig.update_layout(
        height=500,
        margin=dict(l=25, r=25, t=55, b=55),
        legend=dict(orientation="h", y=1.08, x=0),
        hovermode="x unified",
    )
    return fig


def build_day_panel_pnl_chart(product_market: pd.DataFrame) -> go.Figure:
    market = clean_market_rows(product_market.copy())

    if market.empty or "pnl" not in market.columns:
        return go.Figure()

    market = market.dropna(subset=["pnl"]).copy()
    if market.empty:
        return go.Figure()

    if "day" not in market.columns or not market["day"].notna().any():
        return build_combined_pnl_chart(market)

    days = sorted(market["day"].dropna().unique())
    if not days:
        return go.Figure()

    fig = make_subplots(
        rows=1,
        cols=len(days),
        shared_yaxes=True,
        horizontal_spacing=0.035,
        subplot_titles=[format_day_label(day) for day in days],
    )

    for col, day in enumerate(days, start=1):
        day_market = market[market["day"] == day].copy()
        day_market = add_local_day_x(day_market).sort_values("plot_timestamp")

        fig.add_trace(
            go.Scatter(
                x=day_market["plot_timestamp"],
                y=day_market["pnl"],
                mode="lines",
                name="Visible PnL",
                line=dict(width=1.15, color=CHART_COLORS["pnl"]),
                showlegend=(col == 1),
                connectgaps=False,
            ),
            row=1,
            col=col,
        )

        fig.update_xaxes(
            title_text="timestamp",
            range=[0, DAY_LENGTH],
            row=1,
            col=col,
        )

    fig.update_yaxes(title_text="PnL", row=1, col=1)
    fig.update_layout(
        autosize=True,
        height=520,
        margin=dict(l=25, r=25, t=80, b=60),
        legend=dict(orientation="h", y=1.12, x=0),
        hovermode="x unified",
    )
    return fig


def build_day_stacked_pnl_chart(product_market: pd.DataFrame) -> go.Figure:
    """Plot product PnL with one vertical panel per day and clean label spacing."""
    market = clean_market_rows(product_market.copy())

    if market.empty or "pnl" not in market.columns:
        return go.Figure()

    market = market.dropna(subset=["pnl"]).copy()
    if market.empty:
        return go.Figure()

    if "day" not in market.columns or not market["day"].notna().any():
        return build_combined_pnl_chart(market)

    days = sorted(market["day"].dropna().unique())
    if not days:
        return go.Figure()

    fig = make_subplots(
        rows=len(days),
        cols=1,
        shared_xaxes=False,
        shared_yaxes=False,
        vertical_spacing=0.07,
        subplot_titles=[format_day_label(day) for day in days],
    )

    for row, day in enumerate(days, start=1):
        day_market = market[market["day"] == day].copy()
        day_market = add_local_day_x(day_market).sort_values("plot_timestamp")

        fig.add_trace(
            go.Scatter(
                x=day_market["plot_timestamp"],
                y=day_market["pnl"],
                mode="lines",
                name="Visible PnL",
                line=dict(width=1.15, color=CHART_COLORS["pnl"]),
                showlegend=(row == 1),
                connectgaps=False,
            ),
            row=row,
            col=1,
        )

        fig.update_xaxes(
            title_text=("timestamp" if row == len(days) else ""),
            range=[0, DAY_LENGTH],
            showticklabels=True,
            row=row,
            col=1,
        )
        fig.update_yaxes(title_text="PnL", row=row, col=1)

    fig.update_layout(
        autosize=True,
        height=max(780, 340 * len(days)),
        margin=dict(l=25, r=25, t=85, b=65),
        legend=dict(orientation="h", y=1.035, x=0),
        hovermode="x unified",
    )
    return fig


def build_combined_position_chart(product_fills: pd.DataFrame) -> go.Figure:
    fig = go.Figure()

    if not product_fills.empty and "position_after_fill" in product_fills.columns:
        fills_for_plot = product_fills.dropna(subset=["position_after_fill"]).sort_values("time_index")
        if not fills_for_plot.empty:
            fig.add_trace(go.Scatter(
                x=fills_for_plot["time_index"],
                y=fills_for_plot["position_after_fill"],
                mode="lines+markers",
                name="Position after fill",
                line=dict(width=1.0, color=CHART_COLORS["position"], shape="hv"),
                marker=dict(size=4, color=CHART_COLORS["position"], opacity=0.9),
                connectgaps=False,
            ))

    fig.update_layout(
        height=500,
        margin=dict(l=25, r=25, t=55, b=55),
        hovermode="x unified",
    )
    return fig


def build_day_panel_position_chart(product_fills: pd.DataFrame) -> go.Figure:
    """
    Plot position separately per day using local 0->1M timestamp.

    This prevents fake day-to-day connections and fixes the case where Day -1/Day 0
    disappear because their raw timestamps are global blocks like 1M->2M or 2M->3M.
    """
    if product_fills.empty or "position_after_fill" not in product_fills.columns:
        return go.Figure()

    fills_for_plot = product_fills.dropna(subset=["position_after_fill"]).copy()
    if fills_for_plot.empty:
        return go.Figure()

    if "day" not in fills_for_plot.columns or not fills_for_plot["day"].notna().any():
        return build_combined_position_chart(fills_for_plot)

    days = sorted(fills_for_plot["day"].dropna().unique())
    if not days:
        return go.Figure()

    fig = make_subplots(
        rows=1,
        cols=len(days),
        shared_yaxes=True,
        horizontal_spacing=0.045,
        subplot_titles=[format_day_label(day) for day in days],
    )

    for col, day in enumerate(days, start=1):
        day_fills = fills_for_plot[fills_for_plot["day"] == day].copy()
        day_fills = add_local_day_x(day_fills).sort_values("plot_timestamp")

        if not day_fills.empty:
            fig.add_trace(
                go.Scatter(
                    x=day_fills["plot_timestamp"],
                    y=day_fills["position_after_fill"],
                    mode="lines+markers",
                    name="Position after fill",
                    line=dict(width=1.1, color=CHART_COLORS["position"], shape="hv"),
                    marker=dict(size=4, color=CHART_COLORS["position"], opacity=0.9),
                    showlegend=False,
                    connectgaps=False,
                ),
                row=1,
                col=col,
            )

        fig.update_xaxes(
            title_text="timestamp",
            range=[0, DAY_LENGTH],
            showticklabels=True,
            row=1,
            col=col,
        )

    fig.update_yaxes(title_text="position", row=1, col=1)
    fig.update_layout(
        autosize=True,
        height=580,
        margin=dict(l=25, r=25, t=75, b=65),
        hovermode="x unified",
    )
    return fig


def last_non_null_value(df: pd.DataFrame, col: str, default=0.0):
    if df.empty or col not in df.columns:
        return default
    vals = df[col].dropna()
    if vals.empty:
        return default
    return vals.iloc[-1]


market, fills, market_all, public_trades, summary = load_data()

round_number = summary.get("round", "?")
st.title(f"IMC Prosperity Round {round_number} Dashboard")

log_name = summary.get("log_file", "Unknown log")

if "recent_logs" not in st.session_state:
    st.session_state["recent_logs"] = []

recent_logs = st.session_state["recent_logs"]
if log_name not in recent_logs:
    recent_logs.insert(0, log_name)
    st.session_state["recent_logs"] = recent_logs[:3]

st.caption(f"Current log: {log_name}")
st.caption("Recent logs: " + " | ".join(st.session_state["recent_logs"]))

products = sorted(market["symbol"].dropna().unique())
product = st.sidebar.selectbox("Product", products)

show_all_days = st.sidebar.checkbox("Use full public price context", value=False)

chart_layout = st.sidebar.radio(
    "Day layout for price/PnL charts",
    ["Stack days vertically", "Show days side by side"],
    index=0,
)

source_market = market_all if show_all_days else market
source_market = add_spread(source_market)
product_market = source_market[source_market["symbol"] == product].sort_values("time_index").copy()

fill_product_col = get_fill_product_column(fills)
product_fills = fills[fills[fill_product_col] == product].sort_values("time_index").copy()

if not product_fills.empty:
    product_fills = product_fills.copy()

    signed_qty = product_fills["quantity"].where(
        product_fills["side"].eq("BUY"),
        -product_fills["quantity"],
    )
    signed_cash = -(product_fills["price"] * signed_qty)

    product_fills["signed_qty"] = signed_qty
    product_fills["signed_cash"] = signed_cash

    if "day" in product_fills.columns and product_fills["day"].notna().any():
        sort_cols = [c for c in ["day", "timestamp", "time_index"] if c in product_fills.columns]
        product_fills = product_fills.sort_values(sort_cols).copy()
        product_fills["position_after_fill"] = product_fills.groupby("day", sort=False)["signed_qty"].cumsum()
        product_fills["cash_after_fill"] = product_fills.groupby("day", sort=False)["signed_cash"].cumsum()
    else:
        product_fills = product_fills.sort_values("time_index").copy()
        product_fills["position_after_fill"] = product_fills["signed_qty"].cumsum()
        product_fills["cash_after_fill"] = product_fills["signed_cash"].cumsum()

analysis_df = compute_analysis(product_fills, product_market)

st.subheader(f"{product} summary")
col1, col2, col3 = st.columns(3)

last_pnl = last_non_null_value(product_market, "pnl", 0.0)

col1.metric("Snapshots", len(clean_market_rows(product_market)))
col2.metric("Submission fills", len(product_fills))
col3.metric("Last visible PnL", f"{last_pnl:.2f}")

spread_by_day = compute_spread_by_day(product_market)

if not spread_by_day.empty:
    st.subheader("Median spread by day")

    metric_cols = st.columns(len(spread_by_day))
    for i, (_, row) in enumerate(spread_by_day.iterrows()):
        day_value = row["day"]
        day_label = format_day_label(day_value)
        metric_cols[i].metric(f"{day_label} median spread", f"{row['median_spread']:.2f}")

    spread_table = spread_by_day.copy()
    for col in ["median_spread", "mean_spread", "min_spread", "max_spread"]:
        if col in spread_table.columns:
            spread_table[col] = spread_table[col].round(2)

    st.dataframe(spread_table, width="stretch", hide_index=True)
else:
    st.info("No spread data available for this product.")

st.subheader("Price and your fills")

if chart_layout == "Stack days vertically":
    fig_mid = build_day_stacked_price_chart(product_market, product_fills)
elif chart_layout == "Show days side by side":
    fig_mid = build_day_panel_price_chart(product_market, product_fills)
else:
    fig_mid = build_combined_price_chart(product_market, product_fills)

st.plotly_chart(fig_mid, width="stretch", key="price_fills_chart")

st.subheader("Spread histograms by day")
fig_spread = build_spread_histogram_by_day(product_market)
st.plotly_chart(fig_spread, width="stretch", key="spread_histogram_chart")

st.subheader("Visible PnL path")

clean_product_market = clean_market_rows(product_market)

if not clean_product_market.empty and "pnl" in clean_product_market.columns:
    if chart_layout == "Stack days vertically":
        fig_pnl = build_day_stacked_pnl_chart(product_market)
    elif chart_layout == "Show days side by side":
        fig_pnl = build_day_panel_pnl_chart(product_market)
    else:
        fig_pnl = build_combined_pnl_chart(product_market)

    st.plotly_chart(fig_pnl, width="stretch", key="visible_pnl_chart")
else:
    st.info("No market data available.")

st.subheader("Position path from your fills")

if not product_fills.empty:
    fig_pos = build_day_panel_position_chart(product_fills)
    st.plotly_chart(fig_pos, width="stretch", key="position_path_chart")
else:
    st.info("No submission fills for this product in the selected log.")

st.subheader("Extra diagnostics")
col_c, col_d = st.columns(2)

with col_c:
    st.subheader("Drawdown from visible PnL")

    clean_product_market = clean_market_rows(product_market)

    if not clean_product_market.empty and "pnl" in clean_product_market.columns:
        dd = clean_product_market[["time_index", "pnl"]].copy().sort_values("time_index")
        dd = dd.dropna(subset=["pnl"])

        if not dd.empty:
            dd["running_max"] = dd["pnl"].cummax()
            dd["drawdown"] = dd["pnl"] - dd["running_max"]

            fig_dd = px.line(dd, x="time_index", y="drawdown")
            fig_dd.update_layout(height=420, margin=dict(l=20, r=20, t=35, b=35))

            st.plotly_chart(fig_dd, width="stretch", key="drawdown_chart")
        else:
            st.info("No PnL data available.")
    else:
        st.info("No PnL data available.")

with col_d:
    st.subheader("Position histogram")

    if not product_fills.empty:
        fig_hist = px.histogram(product_fills, x="position_after_fill")
        fig_hist.update_layout(height=420, margin=dict(l=20, r=20, t=35, b=35))
        st.plotly_chart(fig_hist, width="stretch", key="position_histogram_chart")
    else:
        st.info("No fills, so no position histogram.")

if not product_fills.empty:
    st.subheader("Your fills table")

    fill_cols = [
        c
        for c in [
            "day",
            "timestamp",
            "side",
            "price",
            "quantity",
            "position_after_fill",
            "cash_after_fill",
        ]
        if c in product_fills.columns
    ]

    st.dataframe(product_fills[fill_cols], width="stretch")

    st.subheader("Buy vs Sell Stats")
    side_stats = compute_fill_stats(product_fills)
    st.dataframe(side_stats, width="stretch")