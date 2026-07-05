# Round 2 Post-Competition Review

## Competition-Specific Review

### Extra Market-Access Bid

Round 2 introduced an extra market-access mechanism. Teams submitted a bid, and accepted teams received additional market access in exchange for paying the bid amount.

Our submitted bid was:

```python
def bid(self):
    return 5000
```

At the time, we chose this value based on the expected benefit of receiving the additional market-share component and the performance of our Round 1 algorithm.

In hindsight, this bid was likely much higher than necessary. Public post-competition writeups suggest that much smaller bids could have cleared. Une Baguette Fromage reported that the median bid was `50`, while another public retrospective reported bidding `151` and noted that even `100` would have been enough.

This suggests that our `5000` bid was probably far above the clearing threshold. The decision was made under uncertainty, but a better approach would have treated the bid more explicitly as an incomplete-information auction:

```text
expected value of extra access
minus bid cost
minus risk from overpaying
```

The lesson is not that bidding was obviously wrong during the round. The lesson is that our bid calibration could have been more systematic.

### Extra Access Was Not Automatically Valuable

During the competition, we interpreted additional market access mainly as a possible source of extra fills and therefore extra PnL.

However, some other public writeups argued that extra access could also be harmful. More access may mean more quotes and more competition, but not necessarily proportionally more profitable trades. It could also reduce empty-book opportunities and compress passive market-making edge.

So the correct question was not simply:

```text
How much extra PnL can we make from more access?
```

but rather:

```text
Does extra access improve net edge after accounting for competition,
spread compression, and bid cost?
```

This was an important Round 2 hindsight point. More access is not automatically valuable if it changes the market environment in a way that weakens the edge.


### Log-Mining for Market Behaviour

During the competition, we mostly used logs to evaluate our own strategy:

- PnL,
- positions,
- fills,
- inventory paths,
- and backtest results.

This was useful, but incomplete. Some stronger post-competition analyses treated logs as a research object in their own right. They looked for repeated bot behavior, recurring takers, timestamp-level trade patterns, repeated trade sizes, and simulator-specific microstructure effects.

One interesting finding was that in Round 2, some takers appeared to repeat across consecutive days at the same timestamp, with the same side and size.

For example:

```text
Day -2, timestamp t:
    buyer takes 8 units of Osmium

Day -1, timestamp t:
    buyer takes 8 units of Osmium again
```

This suggests a possible prediction:

```text
Day 0, timestamp t:
    a similar buyer may appear again
```

This kind of edge can only be discovered by analyzing the market trade logs carefully. It is not visible from final PnL alone.

---

## General Learnings

The biggest general lesson from Round 2 is that our analysis was too strategy-centric and not market-behavior-centric enough.

We mainly asked:

```text
How did our strategy perform?
```

But we should also have asked:

```text
What are the market bots repeatedly doing?
Can their behavior be predicted?
Are the product parameters stable across rounds?
Are our assumptions still valid on the new data?
```

---

## Public Writeups Referenced

This review was informed by public post-competition writeups, especially:

- Une Baguette Fromage's IMC Prosperity 4 writeup.
- Leo-Hawking's IMC Prosperity 4 review.

These were used only as retrospective comparison points. The purpose is to document what we learned after the round, not to claim that these ideas were part of our original Round 2 submission.
