# Round 3 - Gloves Off

Round 3 introduced `VELVETFRUIT_EXTRACT` vouchers, which behaved like call options on `VELVETFRUIT_EXTRACT`. Our algorithmic strategy combined simple delta-one trading with  Black-Scholes / implied-volatility-based voucher pricing.

This round also had a manual bidding challenge. We did alright in the manual round, but the algorithmic submission did not perform the way we expected.

## Contents

- `data_analysis.ipynb`: exploratory analysis of the Round 3 products.
- `original_submission/`: the algorithmic strategy submitted during the competition.
- `manual_analysis/ornamental_biopods_manual_analysis.nb`: Mathematica notebook used to explore the manual challenge with expected-PnL heatmaps.

## Actual Round 3 Result

| Component | Result |
|---|---:|
| Algorithmic challenge | -814 |
| Manual round | 68,029 |
| Combined Round 3 result | 67,215 |

The algorithmic result was disappointing because the strategy performed well on the IMC simulator. During Round 3, we were still mostly using the IMC simulator as our main feedback loop. We had not yet made the local backtester part of our normal process, and we only looked at the detailed product-level logs properly later, during Round 4.


## Algorithmic Strategy Overview

The submitted algorithmic strategy had three main parts:

1. `HYDROGEL_PACK`: passive market making around a stable fair-value estimate.
2. `VELVETFRUIT_EXTRACT`: trading around a fair value based on microprice and exponential moving averages.
3. `VEV_*` vouchers: Black-Scholes pricing using `VELVETFRUIT_EXTRACT` as the underlying and an implied-volatility smile across selected strikes.

The voucher strategy focused on the middle strikes:

- `VEV_5000`
- `VEV_5100`
- `VEV_5200`
- `VEV_5300`

The idea was to compare vouchers in implied-volatility space rather than raw price space, then trade vouchers that looked cheap or expensive relative to a fitted smile.

## Post-Competition Backtest

During Round 4, we tested the Round 3 strategy with the local backtester and compared the results under different trade-matching assumptions.

| Match-trades mode | Total PnL |
|---|---:|
| `all` | 3,154 |
| `worse` | 2,861 |
| `none` | 3,324 |

The local backtests were positive, but the product breakdown changed the interpretation. Most of the PnL came from the delta-one products, while the vouchers lost money across all three trade-matching modes.

| Match-trades mode | Delta-one PnL | Voucher PnL | Total PnL |
|---|---:|---:|---:|
| `all` | 4,069 | -915 | 3,154 |
| `worse` | 3,777 | -915 | 2,861 |
| `none` | 4,286 | -962 | 3,324 |

This was the main thing we missed during the round: the full strategy looked acceptable, but the options component was not helping. The delta-one trades were covering up losses from the vouchers.

## What Went Wrong

The strategy ended up being too dependent on the IMC simulator and was overfit to the signals that worked there.

In hindsight, the main issue was that the fair-value estimates for the delta-one products were also too tuned to the simulator. Since the voucher model used VFE as the underlying, errors in the VFE fair value carried through into the option prices, implied-volatility estimates, smile fit, and final trading signals.

At this point in the competition, we were still relying mostly on IMC simulator feedback and had not yet made local backtesting and detailed log review part of our workflow. If we had done that during Round 3, we likely would have seen earlier that the strategy was fitting the simulator better than it was producing a robust trading edge.

## Manual Challenge

The manual challenge asked teams to submit two bids for Ornamental Bio-Pods. Each counterparty had a hidden reserve price between 670 and 920 XIRECs, and any pods we bought could later be sold for 920 XIRECs.

We treated this as a problem with two parts. First, we had to choose bids that made sense mathematically: bidding higher made it more likely that we would buy, but left less profit per pod. Second, we had to think about what other teams were likely to submit, because our second bid was penalized if it was below the average second bid submitted by all teams.

If we ignore this penalty, the natural baseline is:

$$
b_1 \approx 753.33, \qquad b_2 \approx 836.67.
$$

So `b2 ≈ 837` was a useful starting point. If we expected the average second bid across all teams to be higher than that, then it made sense to move our second bid upward.

We explored this in `manual_analysis/ornamental_biopods_manual_analysis.nb`, a Mathematica notebook that plots expected-PnL heatmaps over the possible `(b1, b2)` values. The notebook was mainly used as a visual aid. It helped us see how the best region moved when we changed our assumption about the average second bid submitted by all teams.

We checked scenarios where the average second bid was around 830, 850, and 870. Our initial higher-average scenario pointed toward bids around `(770, 870)`. However, after looking at a similar challenge from the previous year, we expected many teams to bid closer to the no-penalty baseline, with second bids closer to the low-to-mid 830s. Based on that, we adjusted our final bid downward.

In hindsight, the actual average second bid was about 859, so our initial `(770, 870)` estimate was closer to the right idea. We moved away from it because we expected people to bid more like they did in the previous year's similar challenge. This year, teams bid more aggressively, so lowering our bid ended up hurting us.


## Link to Round 4 Review

Since Round 4 used the same products as Round 3, the post-competition review for this round is in Round 4. In Round 4, we revised  our strategy.
The submitted Round 4 strategy performed much better on the available historical backtests, including when replayed on Round 3 data:

| Strategy | Data | `all` | `worse` | `none` |
|---|---|---:|---:|---:|
| Round 3 strategy | Round 3 | 3,154 | 2,861 | 3,324 |
| Round 4 strategy | Round 3 | 27,997 | 28,331 | 27,368 |
| Round 4 strategy | Round 4 | 28,882 | 29,356 | 27,686 |

Therefore, we continue wth post-competition-review of Round 3 and 4 together when we talk about our strategy in Round 4.