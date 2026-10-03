import pandas as pd, numpy as np, sys
from lib import *
name=sys.argv[1]; COST=float(sys.argv[2])
dd=pd.read_csv(f"{name}_daily.csv", index_col=0, parse_dates=True); dd.index=pd.to_datetime(dd.index, utc=True)
dd["next_intra"]=dd.intra.shift(-1); dd["next_gap"]=dd.gap.shift(-1); dd["next_cc"]=dd.cc.shift(-1)
dd["r2"]=dd.cc.rolling(2).sum(); dd["r3"]=dd.cc.rolling(3).sum(); dd["r5"]=dd.cc.rolling(5).sum()
dd["clv"]=(dd.Close-dd.Low)/(dd.High-dd.Low)  # close location in range
dd["ma10"]=dd.Close.rolling(10).mean(); dd["ma50"]=dd.Close.rolling(50).mean()
dd["dn_streak"]=(dd.cc<0).astype(int).groupby((dd.cc>=0).cumsum()).cumsum()
dd["up_streak"]=(dd.cc>0).astype(int).groupby((dd.cc<=0).cumsum()).cumsum()
print(f"=== {name.upper()} daily conditional patterns (next-day outcome, cost {COST}) ===")
def row(label, m, col):
    x=dd.loc[m, col].dropna()
    print(fmt(stats(x, COST, f"{label} -> next {col}")))
for k in [2,3,4]:
    row(f"{k}+ down days", dd.dn_streak>=k, "next_cc"); row(f"{k}+ down days", dd.dn_streak>=k, "next_gap"); row(f"{k}+ down days", dd.dn_streak>=k, "next_intra")
for k in [3,4,5]:
    row(f"{k}+ up days", dd.up_streak>=k, "next_cc"); row(f"{k}+ up days (short)", dd.up_streak>=k, "next_cc")
for thr in [-5,-8]:
    row(f"3-day return < {thr}%", dd.r3<thr, "next_cc"); row(f"3-day return < {thr}%", dd.r3<thr, "next_gap"); row(f"3-day return < {thr}%", dd.r3<thr, "next_intra")
for thr in [5,8]:
    row(f"3-day return > {thr}%", dd.r3>thr, "next_cc")
row("close in bottom 20% of range", dd.clv<0.2, "next_cc"); row("close in bottom 20% of range", dd.clv<0.2, "next_gap"); row("close in bottom 20% of range", dd.clv<0.2, "next_intra")
row("close in top 20% of range", dd.clv>0.8, "next_cc"); row("close in top 20% of range", dd.clv>0.8, "next_gap"); row("close in top 20% of range", dd.clv>0.8, "next_intra")
row("close > MA10 & MA50 (trend)", (dd.Close>dd.ma10)&(dd.Close>dd.ma50), "next_cc"); row("close > MA10 & MA50", (dd.Close>dd.ma10)&(dd.Close>dd.ma50), "next_gap"); row("close > MA10 & MA50", (dd.Close>dd.ma10)&(dd.Close>dd.ma50), "next_intra")
row("close < MA10 & < MA50", (dd.Close<dd.ma10)&(dd.Close<dd.ma50), "next_cc"); row("close < MA10 & < MA50", (dd.Close<dd.ma10)&(dd.Close<dd.ma50), "next_gap")
row("close < MA10 but > MA50 (dip in uptrend)", (dd.Close<dd.ma10)&(dd.Close>dd.ma50), "next_cc"); row("dip in uptrend", (dd.Close<dd.ma10)&(dd.Close>dd.ma50), "next_gap"); row("dip in uptrend", (dd.Close<dd.ma10)&(dd.Close>dd.ma50), "next_intra")
row("gap down >2% AND closes up (reversal day)", (dd.gap<-2)&(dd.intra>0), "next_cc")
row("gap up >2% AND closes down", (dd.gap>2)&(dd.intra<0), "next_cc")
# weekly: Friday close -> Monday close ; Monday open->close given Friday down
fri=dd[dd.dow==4]; mon=dd[dd.dow==0]
m=mon.copy(); m["fri_cc"]=[fri.cc[fri.index<t].iloc[-1] if (fri.index<t).any() else np.nan for t in m.index]
print(fmt(stats(m.intra[m.fri_cc<0], COST, "Monday intraday long after down Friday"))); print(fmt(stats(m.intra[m.fri_cc>0], COST, "Monday intraday long after up Friday")))
print(fmt(stats(m.gap[m.fri_cc<0], COST, "Weekend hold after down Friday"))); print(fmt(stats(m.gap[m.fri_cc>0], COST, "Weekend hold after up Friday")))
print(fmt(stats(m.gap[m.fri_cc<-2], COST, "Weekend hold after Friday < -2%")))
# "Thursday short" and "Monday long" by quarter
for lab,ser in [("Monday intraday long", mon.intra), ("Thursday intraday short", -dd[dd.dow==3].intra), ("Overnight into Wed", dd[dd.dow==2].gap)]:
    q=(ser-COST).groupby(ser.index.tz_convert(None).to_period("Q")).mean().round(2)
    print(lab, "quarterly:", q.to_dict(), "pos", int((q>0).sum()),"/",len(q))
