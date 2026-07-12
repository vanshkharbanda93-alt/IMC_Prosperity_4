# IMC Prosperity 4 — Cosmic Traders

This repository documents our participation in **IMC Prosperity 4**, a global algorithmic and manual trading competition hosted by IMC.

It is a round-by-round record of the strategies we tried, the analysis we did and the things we learned during the competition. It is not meant to include every experiment. The focus is on the main ideas, things that didnt work and how we could have done better.

> **Status:** this repository is still a work in progress. I am continuing to clean up the later rounds, add strategy notes, and expand the post-competition review.

## Competition Result

| Metric | Result |
|---|---:|
| Overall rank | #791 / 18,803 teams |
| Algorithmic rank | #1,215 / 18,803 teams |
| Manual rank | #471 / 18,803 teams |
| Country rank | #12 |
| Final score | 253,209 Xirecs |

This was a useful practical project for learning how to read order books, estimate fair prices, manage limits, build dashboards, test strategy ideas, and iterate quickly under time pressure.

## Repository Structure

The current repo is organized like this:

```text
IMC_Prosperity_4/
├── README.md
├── requirements.txt
├── assets/
├── dashboard/
│   ├── README.md
│   ├── app.py
│   ├── prepare_data.py
│   ├── requirements.txt
│   └── logs/
├── tutorial_round/
│   ├── README.md
│   ├── data/
│   ├── data_analysis.ipynb
│   └── trader_tutorial.py
├── round_1/
│   ├── README.md
│   ├── data/
│   ├── data_analysis.ipynb
│   ├── original_submission/
│   └── improved_strategies/
├── round_2/
│   ├── README.md
│   ├── data/
│   ├── trader_round2.py
│   ├── manual_trader.py
│   └── post_competition_review/
├── round_3/
│   ├── README.md
│   ├── data/
│   ├── data_analysis.ipynb
│   ├── original_strategy/
│   └── manual_round/
├── round_4/
│   └── README.md
└── round_5/
    └── README.md
```

Some folders are more complete than others. The tutorial round, Round 1, Round 2, and Round 3 already contain the main notes and cleaned-up materials. Round 4 and Round 5 are still being filled in.


## Round Overview

IMC Prosperity 4 was split into two phases. Rounds 1 and 2 made up Phase 1. To reach Phase 2, teams needed to cross **200,000 Xirecs** by the end of Round 2. After that, the leaderboard was reset, so Rounds 3 to 5 were effectively a fresh start for the teams that qualified.

Each round has its own folder with more detailed notes, notebooks, and selected code. The summaries here are only meant to explain what each challenge was about.

### Tutorial Round

The tutorial round introduced the basic Prosperity setup: reading order books, submitting orders, staying within position limits, and keeping trader state across timestamps. There was no separate manual challenge in this round.

### Round 1

The algorithmic challenge introduced `ASH_COATED_OSMIUM` and `INTARIAN_PEPPER_ROOT`. The main task was to understand their price behaviour from the historical order-book data and build simple trading logic around them.

The manual challenge was an auction-style problem involving `DRYLAND_FLAX` and `EMBER_MUSHROOM`. Teams had to decide what orders to place using the information given in the prompt and the stated resale rules.

### Round 2

Round 2 continued the first phase of the competition, where the main goal was not only to make PnL but also to safely cross the 200,000 Xirec qualification threshold for Phase 2. The algorithmic challenge also included a game-theoretic element, where teams could compete for extra market share.

The manual challenge was an allocation problem across `Research`, `Scale`, and `Speed`. The result depended partly on our own allocation and partly on what other teams were likely to do.

### Round 3

Round 3 introduced vouchers on `VELVETFRUIT_EXTRACT`. These behaved like options, so the round was about understanding the link between VFE and the voucher prices, and about how mistakes in the VFE price estimate could affect the voucher trades.

The manual challenge was the Ornamental Bio-Pods bidding problem. Teams submitted two bids, and the result depended on both reserve-price probabilities and the average second bid submitted by all teams.

### Round 4

Round 4 continued with `VELVETFRUIT_EXTRACT` and the vouchers, but now some bot identities were revealed in the trade data. This meant the challenge was not only about pricing the vouchers, but also about checking whether trades against certain bots contained useful information.

The manual challenge was based on `AETHER_CRYSTAL` options. Teams had to choose an options portfolio under the payoff and pricing rules given in the prompt.

### Round 5

The final round added more products and made the challenge more connected across products. Products such as `PEBBLES` and `MICROCHIP` made it important to think about relationships between related markets and about managing several positions at the same time.

The manual challenge involved trading multiple goods on the Ignith exchange using news-style information. The folder is still mostly a placeholder and will be cleaned up later.

## Dashboard

The `dashboard/` folder contains a Streamlit/Plotly dashboard used to inspect strategy behaviour. It parses Prosperity-style logs and csv fles and helps visualize PnL by product, price paths, spreads, fills, positions, and what happened after our trades.

The dashboard was useful from the earlier rounds onward. During Round 5, it became even more important because we had to look at the features of 50 products and performing data analysis for all of them individually was not possible.

## External References

This project benefited from public IMC Prosperity community resources.

- `Ctrl-Alt-DefeatTheMarket`: used as a community reference for Prosperity basics, starter-trader setup, market-making intuition, and general strategy-development ideas.
- `imc-prosperity-4-backtester`: used as the local backtesting framework once we started replaying strategy variants and comparing results under different fill assumptions.

## Disclaimer

This repository is an independent project based on our participation in IMC Prosperity 4. It is not affiliated with, endorsed by, or maintained by IMC.
