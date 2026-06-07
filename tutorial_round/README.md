# Tutorial Round

This folder contains the tutorial-round analysis and representative trading strategy for **IMC Prosperity 4**.

The tutorial round was mainly used to understand the competition interface, set up the local workflow, inspect the market data, and test simple strategy ideas before the main competitive rounds. For this round we mainly relied on the official simulator provided by IMC to test our strategies,

## Products

The tutorial round contained two products:

- `EMERALDS`
- `TOMATOES`

## Files

```text
tutorial_round/
├── README.md
├── data_analysis.ipynb
├── trader_tutorial.py
└── data/
    ├── prices_round_0_day_-1.csv
    ├── prices_round_0_day_-2.csv
    ├── trades_round_0_day_-1.csv
    └── trades_round_0_day_-2.csv
```

## Data Analysis

The notebook [`data_analysis.ipynb`](data_analysis.ipynb) contains exploratory analysis of the tutorial-round data.


## Representative Strategy

The representative tutorial strategy is implemented in:

```text
trader_tutorial.py
```

The strategy uses different logic for the two products.

### `EMERALDS`

For `EMERALDS`, the strategy uses a fixed fair value of approximately `10000`.

The strategy combines:

- passive market making around fair value to capture the spread,
- weak inventory control,
- simple position management to avoid becoming too long or too short,
- active taking when the market price is favourable relative to the fixed fair value.


### `TOMATOES`

For `TOMATOES`, the strategy uses a dynamic fair value based on recent mid-price history.

The fair-value estimate combines:

- the current mid price as the starting reference price,
- a short rolling history of recent mid prices,
- a broader recent-move signal to account for short-term direction,
- a short-horizon mean-reversion correction,
- passive market making around the adjusted fair value,
- position-limit-aware order sizing.



