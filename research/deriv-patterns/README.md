# Deriv pattern study: UK Brent oil, TQQQ, SPXS (3 Oct 2024 to 2 Oct 2026)

Research scripts and raw outputs behind the report "Brent, TQQQ & SPSXA Tradeable Patterns (Deriv)".
The report itself lives as a Claude doc; this folder keeps the code so the numbers can be re-run.

## What was tested

- Weekend gaps (Friday close to Monday open), overnight gaps, gap fade/follow/fill-target rules
- Day-of-week and hour-of-day drift, session blocks, opening-range breakouts, first-hour momentum,
  last-30-minute reversal, next-hour fade after large moves, multi-day conditional setups
- Everything is net of a Deriv cost model: Brent 0.03% round trip, TQQQ 0.16%, SPXS 6.6%, SPY 0.05%
- Every result is split into first year (in-sample) and second year (out-of-sample)

## Deriv facts used (read 3 Oct 2026)

| Instrument | Hours GMT | Target spread | Swap long / short (pts) | Leverage |
| --- | --- | --- | --- | --- |
| UK Brent Oil | Mon 00:00 to Fri 21:00 | 0.02% | -32.72 / -59.68 | 1:50 |
| TQQQ.US | Mon 13:35 to Fri 20:00 | 0.14% | -0.80 / -2.66 | 1:10 |
| SPXS.US | Mon 13:35 to Fri 20:00 | 6.51% | -1.10 / -3.30 | 1:10 |
| SPY.US | Mon 13:35 to Fri 20:00 | 0.03% | -4.40 / -15.40 | 1:10 |

Full ETF table: `outputs/deriv_etf_specs.json`.

## Files

| File | Purpose |
| --- | --- |
| `download.py` | Pulls daily, 1h, 30m and 5m bars from Yahoo Finance into `data/` (not committed) |
| `lib.py` | Shared stats: n, win rate, mean, t-stat, profit factor, drawdown, in/out-of-sample split |
| `brent.py` | Brent weekend gap, overnight gap, day-of-week, hourly, session blocks, range breakouts |
| `brent2.py` | Brent robustness: winsorised means, quarterly consistency, direction splits |
| `brent3.py` | Brent stop-loss variants, monthly equity of the early-session fade |
| `etf.py <name> <cost>` | ETF daily gaps, overnight vs intraday, hourly, first-hour momentum, ORB |
| `etf5m.py <name> <cost>` | ETF patterns from Deriv's 09:35 open on 5-minute data (last 60 sessions) |
| `tqqq2.py <name> <cost>` | Multi-day conditional setups (streaks, range position, moving averages) |
| `outputs/*.txt` | Raw printed results of each script |

## Re-run

```
pip install pandas numpy yfinance scipy
python3 download.py
python3 brent.py > outputs/brent_out.txt
python3 etf.py tqqq 0.16 > outputs/tqqq_out.txt
```

## Headline results

1. Brent early-session fade: if 00:00 to 03:00 GMT moves more than 0.5%, trade against it at 03:00, exit 13:00.
   171 trades, 56% win, +0.54% net per trade, positive in both years and in 8 of 9 quarters.
2. Brent weekend gap fade to fill: 83 trades, 76% win, +0.42% net, 69% of gaps fill by Monday close. No stop works.
3. TQQQ: no gap, opening-range or intraday pattern beats the 0.14% spread in both years. Weak day-of-week
   effects (Monday long, Thursday short, Tuesday close to Wednesday open) are consistent but low confidence.
4. SPXS is untradeable on Deriv at a 6.51% spread; use SPY.US or the US SP 500 index CFD instead.
