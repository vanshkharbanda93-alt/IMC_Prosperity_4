# Improved Round 1 Strategies

This folder contains post-competition experiments based on our original Round 1 submission. The aim was to test small, interpretable improvements rather than rewrite the full strategy.


##  Variant `ASH_COATED_OSMIUM`

The main retained variant is:

```text
trader_osmium_variant.py
```

This keeps the `INTARIAN_PEPPER_ROOT` logic unchanged and modifies only the `ASH_COATED_OSMIUM` strategy.

The Osmium change uses an inventory-adjusted fair value:

```python
fair_value = 10000 - position / 12
```

If the position is long, the effective fair value is lowered, making it less willing to buy and more willing to sell. If the position is short, the effective fair value is raised, making it more willing to buy back and less willing to sell more. 

## Results

| Matching mode | Strategy | Osmium PnL | Pepper Root PnL | Total PnL |
|---|---|---:|---:|---:|
| `all` | Original | 40,102 | 236,797 | 276,899 |
| `all` | Osmium variant | 55,156 | 236,797 | 291,953 |
| `worse` | Original | 37,005 | 236,665 | 273,670 |
| `worse` | Osmium variant | 55,019 | 236,665 | 291,684 |
| `none` | Original | 6,978 | 236,294 | 243,272 |
| `none` | Osmium variant | 12,400 | 236,294 | 248,694 |

Here `all`, `none` and `worse` are the three matching assumptions of the backtester:

- `all`: passive orders can be filled when historical trades occur at or through our quote.
- `worse`: passive orders are filled only when historical trades move strictly through our quote.
- `none`: passive matching against historical trades is disabled.

The `worse` mode is the main robustness check because it removes the most optimistic exact-price passive fills.

We also briefly tested a Wall Mid version for Osmium, where the fixed price of 10000 was replaced by Wall Mid. It improved over the original strategy but underperformed the simpler fixed-anchor inventory-skew variant, so it was not retained as the main improved strategy.


## Variant `INTARIAN_PEPPER_ROOT`

The second retained experiment is:

```text
trader_pepperroot_variant.py
```

This variant keeps the original long bias in Pepper Root, but adds a small spread-capture layer. Since Pepper Root had a stable upward drift, the goal was not to replace the original buy-and-hold idea, but to test whether the strategy could occasionally sell small quantities at wide spreads and then buy back quickly. The detailed analysis for this idea has been presented in the `pepper_root_spread_analysis.ipynb`.

## Pepper Root Results

| Matching mode | Strategy            | Pepper Root PnL | Total PnL |
| ------------- | ------------------- | --------------: | --------: |
| `all`         | Original            |         236,797 |   276,899 |
| `all`         | Pepper Root variant |         238,276 |   278,378 |
| `worse`       | Original            |         236,665 |   273,670 |
| `worse`       | Pepper Root variant |         238,166 |   275,171 |
| `none`        | Original            |         236,294 |   243,272 |
| `none`        | Pepper Root variant |         225,433 |   232,410 |

The Pepper Root variant improves under both `all` and `worse`, with a Root improvement of `+1,479` and `+1,501` respectively. The `worse` result is the most important robustness check because it uses stricter passive-fill assumptions.

The variant performs worse under `none`, which is expected because this strategy relies on passive spread-capture fills.

## Combined Improvement Estimate

Combining the retained Osmium variant with the retained Pepper Root variant would give an estimated total PnL of:

| Matching mode | Original total PnL | Estimated combined PnL | Estimated improvement |
|---|---:|---:|---:|
| `all` | 276,899 | 293,432 | +16,533 |
| `worse` | 273,670 | 293,185 | +19,515 |


