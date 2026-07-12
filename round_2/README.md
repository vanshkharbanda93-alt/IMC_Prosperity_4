# Round 2 -- Growing Your Outpost

This folder contains the Round 2 strategy notes, representative submitted trader, manual optimization script, and result summary for **IMC Prosperity 4**.

Round 2 was an important checkpoint in the competition. After this round, IMC reset the leaderboards, and only teams with a cumulative total of more than `200,000` Xirecs advanced to Round 3.

This made Round 2 strategically different from a normal scoring round. The goal was not only to maximize expected PnL, but also to manage risk carefully enough to qualify for the next stage.

## Round Context

Round 2 had three main components:

1. A qualification requirement of more than `200,000` cumulative Xirecs.
2. An algorithmic trading round using the same products as Round 1 and a game-theoretic aspect for extra market share.
3. A manual trading round with a game-theoretic optimization problem.

The algorithmic products were:

- `ASH_COATED_OSMIUM`
- `INTARIAN_PEPPER_ROOT`

Because these were the same products as Round 1, the algorithmic strategy could build directly on the previous round's observations. We tested more adaptive strategy variants, but the additional PnL observed in the simulator was limited. Since more adaptive variants also increased the risk of overfitting, we decided to keep the submitted strategy relatively simple and robust.

## Algorithmic Strategy

The representative submitted Round 2 strategy is implemented in:

```text
trader_round2.py
```

The strategy keeps the same product universe as Round 1, but refines the product-specific logic.

### `ASH_COATED_OSMIUM`

For `ASH_COATED_OSMIUM`, the strategy treats the product as a local fair-value / market-making product.

Compared with Round 1, the fair value is no longer completely fixed. Instead, the trader maintains a slowly updated internal fair value using recent reference prices from the order book.

The strategy combines:

- slow fair-value estimation,
- passive market making around the estimated fair value,
- active buying when the ask is sufficiently cheap relative to fair value,
- active selling when the bid is sufficiently rich relative to fair value,
- inventory-aware quote sizing,
- position-limit-aware order placement.

This was intended to keep the Osmium logic simple while making it slightly more adaptive than the Round 1 version.

### `INTARIAN_PEPPER_ROOT`

For `INTARIAN_PEPPER_ROOT`, the strategy continues to treat the product as a strongly drifting product.

The strategy estimates a time-dependent fair value from a day-open reference level and a fixed drift rate. It then uses this trend estimate to guide quoting and inventory decisions.

The main idea was to build and maintain a long-biased position, because the product showed persistent upward movement in the previous round's data.

The strategy combines:

- a time-dependent drifting fair value,
- a long-biased target inventory,
- aggressive buying when the product is not too expensive relative to trend fair value,
- additional buying on cheap dips,
- limited selling only when the position is already high and the product appears rich,
- position-limit-aware order placement.

In simple terms, the Root strategy was designed to participate in the upward drift while avoiding unnecessary short exposure.

## Bid Function

Round 2 also included a bidding element that was active for an additional `20%` market-share component.

The submitted trader included a fixed bid function:

```python
def bid(self):
    return 5000
```

We chose a bid of `5000`  which was estimated based on the extra 20% market share we might get and our algorithm's performance in the previous round.

Here we planned to reuse a relatively simple and robust version of the same product logic for Round 2.

This was the amount we were willing to risk for the extra market-share opportunity. The bid was therefore not treated as a pure maximization problem. It was a risk-managed decision: high enough to participate meaningfully in the extra market-share mechanic, but not so high that it would endanger qualification if the algorithmic or manual components underperformed.


## Manual Trading

The Round 2 manual challenge was a combined game-theoretic and optimization problem.

The manual analysis is implemented in:

```text
manual_trader.py
```

The script models an allocation problem across three components:

- `Research`
- `Scale`
- `Speed`

The first two components directly affect the payoff formula, while the `Speed` component depends on how other teams allocate their own budgets. This makes the problem game-theoretic: the value of a given allocation depends not only on our own decision, but also on the expected distribution of competitor submissions.

## Manual Strategy Reasoning

A key strategic consideration was the Round 2 qualification rule.

Because scores would be reset after Round 2, many serious teams close to the `200,000` Xirec threshold did not necessarily need to maximize manual-round upside. Their main objective was likely to avoid a large negative result and safely qualify for Round 3.

Based on this, we expected many teams to play relatively safely in the manual round rather than take extreme risk.

The manual script therefore explored assumptions about the distribution of competitor behaviour. It considered groups such as:

- teams bidding very little,
- teams splitting their allocation in a simple way,
- teams choosing natural Schelling points,
- teams using more optimized allocations,
- teams over-allocating aggressively to the competitive component.

Using these assumptions, the script estimated the expected multiplier from the `Speed` allocation and searched for an allocation that maximized expected net PnL.

## Manual Trading Submission

Our final manual submission for Round 2 was:

| Component | Allocation |
|---|---:|
| `Research` | `14` |
| `Scale` | `41` |
| `Speed` | `45` |

The final allocation was chosen to balance expected payoff with the game-theoretic expectation that many teams would play relatively safely because of the qualification threshold and post-Round-2 leaderboard reset.

## Round 2 Result

At the end of Round 2, our cumulative total was approximately:

| Metric | Result |
|---|---:|
| Total Xirecs | `~481k` |
| Overall Rank | `343` |


## Files

```text
round_2/
├── README.md
├── trader_round2.py
├── manual_trader.py
└── data/
```
