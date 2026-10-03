import pandas as pd, numpy as np, json
from lib import *
COST=0.03
h=load("brent","1h"); h=h[h.index>=START-pd.Timedelta(days=10)]
h["date"]=h.index.date; h["hour"]=h.index.hour; h["dow"]=h.index.dayofweek
d=h[(h.hour<=20)&(h.dow<=4)]
sess=pd.read_csv("brent_sessions.csv", index_col=0, parse_dates=True); sess.index=pd.to_datetime(sess.index,utc=True)
e=100*(sess.c3/sess.open-1)
def run(thr=0.5, exit_h=12, stop=None, side=None):
    out=[]
    for t,row in sess.iterrows():
        m=e.get(t)
        if m is None or np.isnan(m) or abs(m)<=thr: continue
        pos=-np.sign(m)
        if side=="short" and pos>0: continue
        if side=="long" and pos<0: continue
        g=d[(d.date==t.date())&(d.hour>=3)&(d.hour<=exit_h)]
        if len(g)==0: continue
        entry=row.c3; exitpx=g.Close.iloc[-1]; r=100*pos*(exitpx/entry-1); hit=False
        if stop is not None:
            # stop check on hourly highs/lows (bars after 03:00 close)
            if pos>0 and (g.Low<=entry*(1-stop/100)).any(): r=-stop; hit=True
            if pos<0 and (g.High>=entry*(1+stop/100)).any(): r=-stop; hit=True
        out.append((t,r,pos,m,hit))
    o=pd.DataFrame(out,columns=["t","r","pos","sig","stop"]).set_index("t"); return o
print("=== FADE 00:00-03:00 move: stops (exit 13:00) ===")
for stop in [None,0.5,0.75,1.0,1.5,2.0]:
    o=run(0.5,12,stop); print(fmt(stats(o.r,COST,f"thr 0.5, exit 13:00, stop={stop}")), f"  stopped={100*o.stop.mean():.0f}%")
for stop in [None,1.0,1.5]:
    o=run(0.5,20,stop); print(fmt(stats(o.r,COST,f"thr 0.5, exit 21:00, stop={stop}")), f"  stopped={100*o.stop.mean():.0f}%")
o=run(0.5,12,None); o["net"]=o.r-COST
print("trade distribution (net %):", o.net.describe().round(2).to_dict())
print("by month:"); mo=o.net.groupby(o.index.tz_convert(None).to_period("M")).agg(["count","sum","mean"]).round(2); print(mo.to_string())
print("longs:", fmt(stats(o[o.pos>0].r,COST,"long side")), "\nshorts:", fmt(stats(o[o.pos<0].r,COST,"short side")))
# equity curve export (monthly cumulative)
o["cum"]=o.net.cumsum(); o[["net","cum","pos","sig"]].to_csv("brent_fade_trades.csv")
mo_cum=o.net.groupby(o.index.tz_convert(None).to_period("M")).sum().cumsum().round(2)
print("monthly cum:", mo_cum.to_dict())
json.dump({str(k):float(v) for k,v in mo_cum.items()}, open("brent_fade_cum.json","w"))
# WEEKEND gap fade with fill target: equity + stop variants
wk=sess[(sess.dow==0)&(sess.gapdays==3)].copy()
rows=[]
for t,row in wk.iterrows():
    s=-np.sign(row.gap); 
    if s==0: continue
    g=d[d.date==t.date()]
    r=None
    for stop in [None]:
        pass
    r=100*(row.prev_close/row.open-1)*s if row.filled else 100*(row.close/row.open-1)*s
    rows.append((t,r,row.gap))
w=pd.DataFrame(rows,columns=["t","r","gap"]).set_index("t"); w["net"]=w.r-COST
print("\n=== WEEKEND GAP FADE to fill: by month ===")
print(w.net.groupby(w.index.tz_convert(None).to_period("Q")).agg(["count","sum","mean"]).round(2).to_string())
w.to_csv("brent_weekend_trades.csv")
# stop variants for weekend fade (stop at 1% / 1.5% adverse)
for stop in [0.75,1.0,1.5,2.0]:
    rr=[]
    for t,row in wk.iterrows():
        s=-np.sign(row.gap)
        if s==0: continue
        g=d[d.date==t.date()].sort_index()
        r=None
        for tt,b in g.iterrows():
            adverse = 100*(b.High/row.open-1) if s<0 else 100*(row.open/b.Low-1)
            filled = (b.Low<=row.prev_close) if s<0 else (b.High>=row.prev_close)
            if adverse>=stop and filled: r=-stop; break   # conservative
            if adverse>=stop: r=-stop; break
            if filled: r=100*(row.prev_close/row.open-1)*s; break
        if r is None: r=100*(g.Close.iloc[-1]/row.open-1)*s
        rr.append((t,r))
    x=pd.DataFrame(rr,columns=["t","r"]).set_index("t").r
    print(fmt(stats(x,COST,f"Weekend fade to fill, stop {stop}% (conservative)")))
