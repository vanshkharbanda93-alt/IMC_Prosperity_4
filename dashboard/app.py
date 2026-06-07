from pathlib import Path
import json
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

BASE = Path(__file__).resolve().parent
DATA = BASE / "data"

st.set_page_config(page_title="Prosperity Dashboard", layout="wide")


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


def clean_market_rows(df: pd.DataFrame) -> pd.DataFrame:
    """Remove artificial gap rows before doing stats/histograms."""
    out = df.copy()
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
    market = product_market.copy()

    if not market.empty:
        if "mid_price" in market.columns:
            fig.add_trace(go.Scatter(
                x=market["time_index"],
                y=market["mid_price"],
                mode="lines",
                name="Mid price",
                line=dict(width=0.8),
            ))

        if "bid_price_1" in market.columns:
            fig.add_trace(go.Scatter(
                x=market["time_index"],
                y=market["bid_price_1"],
                mode="lines",
                name="Best bid",
                opacity=0.45,
                line=dict(width=0.8),
            ))

        if "ask_price_1" in market.columns:
            fig.add_trace(go.Scatter(
                x=market["time_index"],
                y=market["ask_price_1"],
                mode="lines",
                name="Best ask",
                opacity=0.45,
                line=dict(width=0.8),
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
                marker_symbol="triangle-up",
                marker_size=7,
            ))

        if not sells.empty:
            fig.add_trace(go.Scatter(
                x=sells["time_index"],
                y=sells["price"],
                mode="markers",
                name="Your sells",
                marker_symbol="triangle-down",
                marker_size=7,
            ))

    fig.update_layout(height=520, margin=dict(l=20, r=20, t=30, b=30))
    return fig


def build_day_panel_price_chart(product_market: pd.DataFrame, product_fills: pd.DataFrame) -> go.Figure:
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
        horizontal_spacing=0.015,
        subplot_titles=[format_day_label(day) for day in days],
    )

    for col, day in enumerate(days, start=1):
        day_market = market[market["day"] == day].sort_values("timestamp")

        if "mid_price" in day_market.columns:
            fig.add_trace(
                go.Scatter(
                    x=day_market["timestamp"],
                    y=day_market["mid_price"],
                    mode="lines",
                    name="Mid price",
                    line=dict(width=0.8),
                    showlegend=(col == 1),
                ),
                row=1,
                col=col,
            )

        if "bid_price_1" in day_market.columns:
            fig.add_trace(
                go.Scatter(
                    x=day_market["timestamp"],
                    y=day_market["bid_price_1"],
                    mode="lines",
                    name="Best bid",
                    opacity=0.45,
                    line=dict(width=0.8),
                    showlegend=(col == 1),
                ),
                row=1,
                col=col,
            )

        if "ask_price_1" in day_market.columns:
            fig.add_trace(
                go.Scatter(
                    x=day_market["timestamp"],
                    y=day_market["ask_price_1"],
                    mode="lines",
                    name="Best ask",
                    opacity=0.45,
                    line=dict(width=0.8),
                    showlegend=(col == 1),
                ),
                row=1,
                col=col,
            )

        if not product_fills.empty and "day" in product_fills.columns:
            day_fills = product_fills[product_fills["day"] == day].copy()
            buys = day_fills[day_fills["side"] == "BUY"]
            sells = day_fills[day_fills["side"] == "SELL"]

            if not buys.empty:
                fig.add_trace(
                    go.Scatter(
                        x=buys["timestamp"],
                        y=buys["price"],
                        mode="markers",
                        name="Your buys",
                        marker_symbol="triangle-up",
                        marker_size=7,
                        showlegend=(col == 1),
                    ),
                    row=1,
                    col=col,
                )

            if not sells.empty:
                fig.add_trace(
                    go.Scatter(
                        x=sells["timestamp"],
                        y=sells["price"],
                        mode="markers",
                        name="Your sells",
                        marker_symbol="triangle-down",
                        marker_size=7,
                        showlegend=(col == 1),
                    ),
                    row=1,
                    col=col,
                )

        fig.update_xaxes(title_text="timestamp", row=1, col=col)

    fig.update_layout(
        height=520,
        margin=dict(l=20, r=20, t=60, b=30),
        legend=dict(orientation="h", y=1.12, x=0),
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
                line=dict(width=0.9),
            ))

    fig.update_layout(height=420, margin=dict(l=20, r=20, t=30, b=30))
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
        horizontal_spacing=0.015,
        subplot_titles=[format_day_label(day) for day in days],
    )

    for col, day in enumerate(days, start=1):
        day_market = market[market["day"] == day].sort_values("timestamp")
        fig.add_trace(
            go.Scatter(
                x=day_market["timestamp"],
                y=day_market["pnl"],
                mode="lines",
                name="Visible PnL",
                line=dict(width=0.9),
                showlegend=(col == 1),
            ),
            row=1,
            col=col,
        )
        fig.update_xaxes(title_text="timestamp", row=1, col=col)

    fig.update_yaxes(title_text="PnL", row=1, col=1)
    fig.update_layout(
        height=420,
        margin=dict(l=20, r=20, t=60, b=30),
        legend=dict(orientation="h", y=1.12, x=0),
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
                line=dict(width=0.9),
                marker=dict(size=5),
            ))

    fig.update_layout(height=420, margin=dict(l=20, r=20, t=30, b=30))
    return fig


def build_day_panel_position_chart(product_fills: pd.DataFrame) -> go.Figure:
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
        horizontal_spacing=0.015,
        subplot_titles=[format_day_label(day) for day in days],
    )

    for col, day in enumerate(days, start=1):
        day_fills = fills_for_plot[fills_for_plot["day"] == day].sort_values("timestamp")
        fig.add_trace(
            go.Scatter(
                x=day_fills["timestamp"],
                y=day_fills["position_after_fill"],
                mode="lines+markers",
                name="Position after fill",
                line=dict(width=0.9),
                marker=dict(size=5),
                showlegend=(col == 1),
            ),
            row=1,
            col=col,
        )
        fig.update_xaxes(title_text="timestamp", row=1, col=col)

    fig.update_yaxes(title_text="position", row=1, col=1)
    fig.update_layout(
        height=420,
        margin=dict(l=20, r=20, t=60, b=30),
        legend=dict(orientation="h", y=1.12, x=0),
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
show_days_side_by_side = st.sidebar.checkbox("Show days side by side", value=True)

source_market = market_all if show_all_days else market
source_market = add_spread(source_market)
product_market = source_market[source_market["symbol"] == product].sort_values("time_index").copy()

fill_product_col = get_fill_product_column(fills)
product_fills = fills[fills[fill_product_col] == product].sort_values("time_index").copy()

if not product_fills.empty:
    signed_qty = product_fills["quantity"].where(product_fills["side"].eq("BUY"), -product_fills["quantity"])
    signed_cash = -(product_fills["price"] * signed_qty)

    product_fills["signed_qty"] = signed_qty
    product_fills["signed_cash"] = signed_cash
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
if show_days_side_by_side:
    fig_mid = build_day_panel_price_chart(product_market, product_fills)
else:
    fig_mid = build_combined_price_chart(product_market, product_fills)
st.plotly_chart(fig_mid, width="stretch", key="price_fills_chart")

st.subheader("Spread histograms by day")
fig_spread = build_spread_histogram_by_day(product_market)
st.plotly_chart(fig_spread, width="stretch", key="spread_histogram_chart")

st.subheader("Positive vs negative next-snapshot markout on price chart")
if not analysis_df.empty:
    positive_fills = analysis_df[analysis_df["markout"] > 0].copy()
    negative_fills = analysis_df[analysis_df["markout"] <= 0].copy()

    fig_quality = go.Figure()
    clean_product_market = clean_market_rows(product_market)

    if "mid_price" in clean_product_market.columns:
        fig_quality.add_trace(go.Scatter(
            x=clean_product_market["time_index"],
            y=clean_product_market["mid_price"],
            mode="lines",
            name="Mid price",
            line=dict(width=0.8),
        ))

    if not positive_fills.empty:
        fig_quality.add_trace(go.Scatter(
            x=positive_fills["time_index"],
            y=positive_fills["price"],
            mode="markers",
            name="Positive markout fills",
            marker_symbol="circle",
            marker_size=7,
        ))

    if not negative_fills.empty:
        fig_quality.add_trace(go.Scatter(
            x=negative_fills["time_index"],
            y=negative_fills["price"],
            mode="markers",
            name="Negative markout fills",
            marker_symbol="x",
            marker_size=7,
        ))

    st.plotly_chart(fig_quality, width="stretch", key="markout_price_chart")
else:
    st.info("Could not compute next-snapshot markout chart.")

st.subheader("Visible PnL path")
clean_product_market = clean_market_rows(product_market)
if not clean_product_market.empty and "pnl" in clean_product_market.columns:
    if show_days_side_by_side:
        fig_pnl = build_day_panel_pnl_chart(product_market)
    else:
        fig_pnl = build_combined_pnl_chart(product_market)
    st.plotly_chart(fig_pnl, width="stretch", key="visible_pnl_chart")
else:
    st.info("No market data available.")

st.subheader("Position path from your fills")
if not product_fills.empty:
    if show_days_side_by_side:
        fig_pos = build_day_panel_position_chart(product_fills)
    else:
        fig_pos = build_combined_position_chart(product_fills)
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
            st.plotly_chart(fig_dd, width="stretch", key="drawdown_chart")
        else:
            st.info("No PnL data available.")
    else:
        st.info("No PnL data available.")

with col_d:
    st.subheader("Position histogram")
    if not product_fills.empty:
        fig_hist = px.histogram(product_fills, x="position_after_fill")
        st.plotly_chart(fig_hist, width="stretch", key="position_histogram_chart")
    else:
        st.info("No fills, so no position histogram.")

if not product_fills.empty:
    st.subheader("Your fills table")
    fill_cols = [c for c in ["day", "timestamp", "side", "price", "quantity", "position_after_fill", "cash_after_fill"] if c in product_fills.columns]
    st.dataframe(product_fills[fill_cols], width="stretch")

    st.subheader("Buy vs Sell Stats")
    side_stats = compute_fill_stats(product_fills)
    st.dataframe(side_stats, width="stretch")

    st.subheader("Next-snapshot markout over time")
    if not analysis_df.empty:
        positive_fills = analysis_df[analysis_df["markout"] > 0].copy()
        negative_fills = analysis_df[analysis_df["markout"] <= 0].copy()

        fig_markout = go.Figure()

        if not positive_fills.empty:
            fig_markout.add_trace(go.Scatter(
                x=positive_fills["time_index"],
                y=positive_fills["markout"],
                mode="markers",
                name="Positive markout",
                marker_symbol="circle",
                marker_size=7,
            ))

        if not negative_fills.empty:
            fig_markout.add_trace(go.Scatter(
                x=negative_fills["time_index"],
                y=negative_fills["markout"],
                mode="markers",
                name="Negative markout",
                marker_symbol="x",
                marker_size=7,
            ))

        st.plotly_chart(fig_markout, width="stretch", key="markout_scatter_chart")

        display_cols = ["side", "price", "quantity", "mid_at_or_before_fill", "mid_after_fill", "markout", "markout_sign"]
        if "day" in analysis_df.columns:
            display_cols = ["day"] + display_cols
        if "timestamp" in analysis_df.columns:
            display_cols.insert(1 if "day" in analysis_df.columns else 0, "timestamp")

        st.dataframe(analysis_df[display_cols], width="stretch")
    else:
        st.info("Could not compute next-snapshot markout analysis.")
else:
    st.info("No fills available for fill table, side stats, or markout analysis.")

st.subheader("Public market trades")
if not public_trades.empty:
    public_product_col = get_public_product_column(public_trades)
    if public_product_col:
        public_product = public_trades[public_trades[public_product_col] == product].sort_values("time_index")
        if not public_product.empty:
            show_cols = [c for c in ["day", "timestamp", "price", "qty", "quantity"] if c in public_product.columns]
            st.dataframe(public_product[show_cols].head(100), width="stretch")
        else:
            st.info("No public trades for this product.")
    else:
        st.info("No usable product column in public trades file.")
else:
    st.info("No public trade file found.")
