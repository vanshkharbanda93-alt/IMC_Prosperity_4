# Round 1 - Trading Groundwork

This folder contains the Round 1 analysis, manual trading notes, results, and representative submitted strategy for **IMC Prosperity 4**.

Round 1 introduced two algorithmic trading products:

- `ASH_COATED_OSMIUM`
- `INTARIAN_PEPPER_ROOT`

The main goal of this round was to understand the behaviour of each product from the provided market data and design simple product-specific trading strategies.

## Data Analysis

The notebook [`data_analysis.ipynb`](data_analysis.ipynb) contains exploratory analysis of the Round 1 market data.


## Representative Strategy

The representative submitted Round 1 strategy is implemented in:

```text
trader_round1.py
```

The strategy uses separate logic for the two Round 1 products.

### `ASH_COATED_OSMIUM`

For `ASH_COATED_OSMIUM`, the strategy treats the product as a local fair-value product with fair value around `10001`.

The strategy combines:

- active buying when the best ask is at or below fair value,
- active selling when the best bid is at or above fair value,
- passive market making around the current mid price,
- spread-dependent quote widths,
- simple inventory-aware sizing.

The strategy first takes favourable liquidity when the market price is attractive relative to fair value. After that, it places passive bid and ask orders using the remaining position capacity.

This matches the data analysis: `ASH_COATED_OSMIUM` mostly fluctuates around the `10000` region, has a common spread near `16`, and shows evidence of short-horizon mean reversion.

### `INTARIAN_PEPPER_ROOT`

For `INTARIAN_PEPPER_ROOT`, the strategy uses a dynamic fair value rather than a fixed one.

The data analysis showed that the product has a strong upward drift, with the mid price increasing by roughly `1000` over each provided day. To account for this, the strategy updates an internal fair-value estimate using the current mid price and a continuation term.

The strategy then adds a positive trend boost and quotes around this drifting reference price. Unlike `ASH_COATED_OSMIUM`, it does not actively take liquidity first; it mainly places passive bid and ask orders around the dynamic fair value using a shared order-building helper.

This makes the strategy more suitable for a product with a changing fair value than a static fair-value strategy.

## Manual Trading

Round 1 also included a manual trading component involving auction-style order submission.

Our submitted manual orders for this round were:

| Product | Order Type | Price | Volume |
|---|---:|---:|---:|
| `DRYLAND_FLAX` | Buy | `30` | `9999` |
| `EMBER_MUSHROOM` | Buy | `17` | `19999` |

The manual trading submission contributed `87,995` Xirecs to the Round 1 score.

## Round 1 Result

At the end of Round 1, our score breakdown was:

| Component | Score |
|---|---:|
| Algorithmic Challenge | `91,965` |
| Manual Challenge | `87,995` |
| Total / Overall Score | `179,961` |

Both the algorithmic and manual components contributed meaningfully to the final Round 1 score. The algorithmic strategy generated `91,965` Xirecs, while the manual trading submission added `87,995` Xirecs.

Note: we do not recall our exact positioning on the leaderboard for this round.

## Limitations

This strategy was designed for the Round 1 product behaviour and should not be interpreted as a general trading system.

Main limitations:

- The Osmium fair value is hard-coded around `10001`.
- The Root drift parameters are hand-tuned from observed behaviour.
- The strategy does not include a sophisticated risk model.
- The analysis is based on the provided Round 1 data and local testing environment.
- The approach is intentionally simple and competition-specific.

## Files

```text
round_1/
├── README.md
├── data_analysis.ipynb
├── trader_round1.py
└── data/
    ├── prices_round_1_day_-2.csv
    ├── prices_round_1_day_-1.csv
    ├── prices_round_1_day_0.csv
    ├── trades_round_1_day_-2.csv
    ├── trades_round_1_day_-1.csv
    └── trades_round_1_day_0.csv
```

## Manual Trading Rules

The manual trading part was separate from the algorithmic strategy. Instead of submitting Python code, teams submitted auction-style orders through the game interface.

The interface allowed teams to:

- choose an order type, such as buy or sell,
- enter a limit price,
- enter an order volume,
- submit the order before the auction closed.

For the manual products, the interface showed a stale order-book state. This meant that the displayed bids and asks were not necessarily live, so the task was to infer a sensible order from incomplete market information.

For `DRYLAND_FLAX`, the interface stated that any acquired units would be sold directly after the auction closed for `30` Xirecs per piece. Therefore, buying at `30` corresponded to the stated resale value, while any lower successful buy price would have created a positive margin.

The manual trading decision was therefore based on:

- the displayed stale order-book information,
- the stated post-auction resale rule,
- the chosen limit price,
- the chosen order volume,
- the risk that the submitted order may or may not be filled.

These manual rules were independent of the algorithmic trading code, but the resulting manual PnL contributed to the final Round 1 score.
