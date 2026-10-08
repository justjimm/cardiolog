import pandas as pd, numpy as np, sys
from lib import *
name=sys.argv[1]; COST=0.01; label=sys.argv[2]
h=load(name,"1h"); h=h[h.index>=START-pd.Timedelta(days=10)]
ny=h.index.tz_convert("America/New_York"); h["hour"]=ny.hour; h["dow"]=ny.dayofweek
h["tdate"]=(ny+pd.Timedelta(hours=7)).date; h["ret"]=100*(h.Close/h.Open-1)
h=h[h.hour!=17]   # CME/Deriv daily break
g=h.groupby("tdate")
S=pd.DataFrame({"open":g.Open.first(),"close":g.Close.last(),"high":g.High.max(),"low":g.Low.min(),"nbars":g.size()})
S.index=pd.to_datetime(S.index).tz_localize("UTC"); S["dow"]=S.index.dayofweek
def px(hour, col):
    x=h[h.hour==hour].groupby("tdate")[col].first(); x.index=pd.to_datetime(x.index).tz_localize("UTC"); return x
S["o18"]=px(18,"Open"); S["o02"]=px(2,"Open"); S["o09"]=px(9,"Open"); S["c15"]=px(15,"Close"); S["o10"]=px(10,"Open"); S["c16"]=px(16,"Close")
S["prev_c15"]=S.c15.shift(1); S["prev_close"]=S.close.shift(1)
S["prev_date"]=pd.Series(S.index,index=S.index).shift(1); S["gapdays"]=(S.index-S.prev_date).dt.days
S=S[(S.nbars>=18)&(S.index>=START)]
S["wk_gap"]=100*(S.o18/S.prev_close-1)          # Deriv weekend/overnight gap at 18:00 ET reopen vs previous 16:xx close
S["on"]=100*(S.o09/S.prev_c15-1)                 # cash close 16:00 ET -> 09:00 ET next day (Deriv index tradeable)
S["asia"]=100*(S.o02/S.o18-1); S["europe"]=100*(S.o09/S.o02-1); S["us"]=100*(S.c15/S.o09-1); S["post"]=100*(S.c16/S.c15-1)
S["filled"]=((S.wk_gap>0)&(S.low<=S.prev_close))|((S.wk_gap<0)&(S.high>=S.prev_close))
print(f"=== {label} (proxy {name.upper()} futures), {len(S)} sessions {S.index.min().date()}..{S.index.max().date()}, cost {COST}% round trip, swap-free ===")
wk=S[S.gapdays>=3]; wd=S[S.gapdays==1]
print(f"Weekend reopen gap (Fri close -> Sun 18:00 ET): n={len(wk)} mean={wk.wk_gap.mean():.3f}% |gap|={wk.wk_gap.abs().mean():.3f}% up={100*(wk.wk_gap>0).mean():.0f}% filled by Mon close={100*wk.filled.mean():.0f}%")
print(f"Weeknight break gap (17:00->18:00 ET): |gap| mean={wd.wk_gap.abs().mean():.3f}%")
print(fmt(stats(wk.wk_gap, COST, "WEEKEND hold long (Fri close -> Sun reopen)")))
print(fmt(stats(100*(wk.o09/wk.prev_close-1), COST, "WEEKEND hold long to Monday 09:00 ET")))
print(fmt(stats(100*(wk.c15/wk.prev_close-1), COST, "WEEKEND hold long to Monday 16:00 ET close")))
for col,lab in [("o09","Mon 09:00"),("c15","Mon 16:00")]:
    r=-np.sign(wk.wk_gap)*100*(wk[col]/wk.o18-1)
    print(fmt(stats(r, COST, f"Fade weekend reopen gap at Sun 18:00, exit {lab}")))
    print(fmt(stats(r[wk.wk_gap.abs()>0.3], COST, f"  |gap|>0.3%")))
    print(fmt(stats(-r, COST, f"Follow weekend reopen gap, exit {lab}")))
def fade_fill(w):
    out={}
    for t,row in w.iterrows():
        s=-np.sign(row.wk_gap)
        if s==0 or np.isnan(s): continue
        out[t]=100*(row.prev_close/row.o18-1)*s if row.filled else 100*(row.close/row.o18-1)*s
    return pd.Series(out)
print(fmt(stats(fade_fill(wk), COST, "Fade weekend gap, target=fill else Mon close")))
print(fmt(stats(fade_fill(wk[wk.wk_gap.abs()>0.3]), COST, "Fade weekend gap |gap|>0.3%, target=fill")))
print("\n--- OVERNIGHT vs SESSIONS (every trading day) ---")
print(fmt(stats(S.on, COST, "Overnight hold long: 16:00 ET close -> 09:00 ET")))
print(fmt(stats(S.asia, COST, "Asia 18:00 -> 02:00 ET long")))
print(fmt(stats(S.europe, COST, "Europe 02:00 -> 09:00 ET long")))
print(fmt(stats(S.us, COST, "US cash 09:00 -> 16:00 ET long")))
print(fmt(stats(S.post, COST, "Post-close 16:00 -> 17:00 ET long")))
for dw,nm in enumerate("Mon Tue Wed Thu Fri".split()):
    x=S[S.dow==dw]
    print(fmt(stats(x.on, COST, f"  overnight into {nm}")), "\n", fmt(stats(x.us, COST, f"  US cash {nm}")))
print("\n--- Overnight conditional on prior US cash session ---")
for thr in [-1,-2]:
    print(fmt(stats(S.on[S.us.shift(1)<thr], COST, f"Overnight long after US session < {thr}%")))
for thr in [1,2]:
    print(fmt(stats(S.on[S.us.shift(1)>thr], COST, f"Overnight long after US session > +{thr}%")))
print(fmt(stats(-np.sign(S.on)*S.us, COST, "Fade overnight move at 09:00, exit 16:00")))
print(fmt(stats((-np.sign(S.on)*S.us)[S.on.abs()>0.5], COST, "  |overnight|>0.5%")))
print(fmt(stats((np.sign(S.on)*S.us)[S.on.abs()>0.5], COST, "Follow overnight move |>0.5%| at 09:00, exit 16:00")))
print(fmt(stats((np.sign(S.on)*S.us)[S.on.abs()>1.0], COST, "Follow overnight move |>1%| at 09:00, exit 16:00")))
print("\n--- HOURLY (NY time) winsorised mean, win%, IS/OOS ---")
hh=h[h.index>=START].copy()
def wins(x): return x.clip(lower=x.quantile(0.05), upper=x.quantile(0.95)).mean()
tab=hh.groupby("hour").ret.agg(n="size", mean="mean", wmean=wins, win=lambda x:100*(x>0).mean()).round(4)
tab["t"]=(hh.groupby("hour").ret.mean()/(hh.groupby("hour").ret.std()/np.sqrt(hh.groupby("hour").ret.size()))).round(2)
tab["IS"]=hh[hh.index<SPLIT].groupby("hour").ret.mean().round(4); tab["OOS"]=hh[hh.index>=SPLIT].groupby("hour").ret.mean().round(4)
print(tab.to_string()); tab.to_csv(f"{name}_hourly.csv")
# first-hour ORB on 09:00 bar? (cash opens 09:30 so use 09:00-10:00 bar as "first hour") skip; gap-follow handled separately
S.to_csv(f"{name}_sessions.csv")
