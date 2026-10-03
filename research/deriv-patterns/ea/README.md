# BrentFadeEA for Deriv MT5

One Expert Advisor, two tested Brent patterns, three risk sets.

| Set file | Notional / equity | Weekend trade size | Drawdown halt | Backtest year 1 / year 2 (haircut) | Worst drawdown | Who it is for |
| --- | --- | --- | --- | --- | --- | --- |
| `BrentFade_Recommended.set` | 2.0x | 50% | 35% | +23% / +123% | -25% | Default. One losing year in sixteen |
| `BrentFade_Mid.set` | 3.5x | 75% | 55% | +44% / +294% | -45% | Midpoint between the two |
| `BrentFade_Aggressive.set` | 5.0x | 100% | 75% | +65% / +537% | -65% | Ceiling. One losing year in nine; 7x and 10x reach -80% and -93% drawdowns, which is ruin |

"Haircut" caps every backtest win at 3% and charges 0.05% extra slippage per trade. Year 1 is Oct 2024 to Oct 2025 (a normal oil year); year 2 is Oct 2025 to Oct 2026 (a crisis year). Plan on year 1.

## What it trades

1. Early-session fade. At 03:00 GMT it compares the price with the 00:00 GMT H1 open. If the move exceeds 0.5% it sells after a rise or buys after a drop, with a 2% disaster stop, and closes at 13:00 GMT. One decision per day, Monday to Friday. (04:00 to 14:00 Lagos time.)
2. Weekend gap fade. Two minutes after Monday 00:00 GMT it compares the price with Friday's last H1 close. If the gap is at least 0.3% it trades against it with take-profit at Friday's close, no stop, and a time exit at 20:50 GMT Monday. (01:00 entry, 21:50 exit Lagos time.)

Sizing: lots = equity x LeverageMultiple / (contract size x price), rounded down to the volume step. The weekend trade is scaled by WeekendSizeFactor. A drawdown halt stops new entries when equity falls the set percentage below its peak; reset it by deleting the global variable named in the log (Tools > Global Variables) or by re-attaching the EA.

## Install

1. In MT5: File > Open Data Folder > MQL5 > Experts. Copy `BrentFadeEA.mq5` there. Copy the three `.set` files to MQL5 > Presets.
2. Open MetaEditor (F4), open the file, press F7 to compile. It should compile with 0 errors; report any warning text back if not.
3. Open a UK Brent Oil chart (any timeframe; the EA reads H1 bars itself). Drag the EA onto it. In the inputs tab press Load and pick a set. Enable Algo Trading.
4. Keep the terminal running at 03:00 and 13:00 GMT and on Monday 00:00 to 21:00 GMT. A VPS is the practical answer; Deriv offers one from inside MT5.

## Server time

All rules are in GMT. Live, the EA measures the server's offset from GMT itself. In the Strategy Tester it assumes the server clock is GMT, which is what Deriv's MT5 server uses; if your tester results show decisions at the wrong hour, set GMTOffsetOverrideHours to the server's offset.

## Backtest in the Strategy Tester

Symbol UK Brent Oil, timeframe H1, model "Every tick based on real ticks", period 2024.10.03 to today, load a set, deposit in USD. The EA opens at most one early-fade position per day and one weekend position per Monday. Expect about 85 early-fade trades and 50 weekend trades per year.

## Not implemented on purpose

No trailing stop, no averaging, no news filter, no martingale. Each of those was either untested or tested and found to hurt (any stop tighter than 2% on the early fade removes the edge; any stop at all on the weekend fade removes it).
