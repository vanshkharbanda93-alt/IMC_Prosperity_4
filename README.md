# IMC Prosperity 4 — Cosmic_Traders

This repository presents a curated, round-wise summary of our trading strategies, analysis workflow, and selected Python code developed during **IMC Prosperity 4**, a global algorithmic and manual trading competition hosted by IMC.

The goal of this repository is not to reproduce every experiment from the competition. Instead, it contains a polished reconstruction of the main ideas, tools, strategy iterations, and lessons learned from our participation.

## Competition Result

| Metric | Result |
|---|---:|
| Overall rank | #791 / 18,803 teams |
| Algorithmic rank | #1215 / 18,803 teams |
| Manual rank | #471 / 18,803 teams |
| Country rank (Italy) | #12 |
| Final score | 253,209 Xirecs |

This was a useful practical project for developing intuition around market making, fair-value estimation, position limits, inventory risk, backtesting, and fast strategy iteration under time pressure.

## Repository Structure

```text
IMC_Prosperity_4/
├── README.md
├── assets/
│   ├── leaderboard.png
│   └── dashboard_overview.png
├── tutorial_round/
│   └── README.md
├── round_1/
│   ├── README.md
│   └── trader_round1.py
├── round_2/
│   ├── README.md
│   └── trader_round2.py
├── round_3/
│   ├── README.md
│   └── trader_round3.py
├── round_4/
│   ├── README.md
│   └── trader_round4.py
├── round_5/
│   ├── README.md
│   └── trader_round5.py
├── dashboard/
│   ├── README.md
│   └── app.py
├── scripts/
│   └── README.md
└── requirements.txt
```

## Analysis Workflow
Early analysis was done using notebooks and scripts. As the competition progressed, we switched to a dashboard-driven workflow because it was faster for strategy iteration.

The dashboard was used to inspect product-level PnL, inventory paths, fills, spread behaviour, markouts, and comparisons between strategy versions. This helped us understand not only whether a strategy made money, but also why it made or lost money.

## Dashboard Note
Parts of the dashboard implementation were AI-assisted, mainly for scaffolding the Streamlit/Plotly interface. The important contribution was deciding which trading diagnostics were useful, adapting the dashboard to Prosperity logs, and using it to analyse strategy behaviour across rounds.

## External References

This project benefited from the public IMC Prosperity community ecosystem.
- [Ctrl-Alt-DefeatTheMarket](https://github.com/MarkBrezina/Ctrl-Alt-DefeatTheMarket)  
  Used as a reference for basic trading strategy concepts, terminology, and general Prosperity-style thinking.

- [imc-prosperity-4-backtester](https://github.com/nabayansaha/imc-prosperity-4-backtester)  
  Used as the local backtesting framework for testing strategy variants before submission.

## Disclaimer
This repository is an independent project based on our participation in IMC Prosperity 4. It is not affiliated with, endorsed by, or maintained by IMC.
