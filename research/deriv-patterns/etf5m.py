import pandas as pd, numpy as np, sys
from lib import *
name=sys.argv[1]; COST=float(sys.argv[2])
m=load(name,"5m"); ny=m.index.tz_convert("America/New_York"); m["t"]=ny.hour*100+ny.minute; m["date"]=ny.date
reg=m[(m.t>=930)&(m.t<1600)]
days=reg.groupby("date")
S=pd.DataFrame({"o930":days.Open.first(),"c1600":days.Close.last()})
def at(t, col="Open"):
    x=reg[reg.t==t].groupby("date")[col].first(); return x
S["o935"]=at(935); S["o945"]=at(945); S["o1000"]=at(1000); S["c1030"]=at(1030); S["o1530"]=at(1530); S["o1555"]=at(1555)
S["prev_close"]=S.c1600.shift(1)
S=S.dropna(subset=["prev_close","o935"])
S.index=pd.DatetimeIndex(pd.to_datetime(S.index)).tz_localize("UTC")
S["gap930"]=100*(S.o930/S.prev_close-1); S["gap935"]=100*(S.o935/S.prev_close-1); S["first5"]=100*(S.o935/S.o930-1)
S["r935_1600"]=100*(S.c1600/S.o935-1); S["r935_1030"]=100*(S.c1030/S.o935-1); S["r1000_1600"]=100*(S.c1600/S.o1000-1)
print(f"=== {name.upper()} 5-minute, n={len(S)} days {S.index.min().date()}..{S.index.max().date()} (Deriv open = 09:35 NY) ===")
print(f"first 5 min move: mean={S.first5.mean():.3f}% |mean|={S.first5.abs().mean():.3f}%  corr(gap930, first5)={S.gap930.corr(S.first5):.2f}  corr(first5, rest)={S.first5.corr(S.r935_1600):.2f}")
print(fmt(stats(-np.sign(S.gap935)*S.r935_1600, COST, "Fade gap from 09:35 to close")))
print(fmt(stats(np.sign(S.gap935)*S.r935_1600, COST, "Follow gap from 09:35 to close")))
print(fmt(stats(-np.sign(S.gap935)*S.r935_1030, COST, "Fade gap 09:35 -> 10:30")))
print(fmt(stats(np.sign(S.first5)*S.r935_1600, COST, "Follow first-5-min direction 09:35->close")))
print(fmt(stats(np.sign(S.first5)*S.r935_1030, COST, "Follow first-5-min direction 09:35->10:30")))
print(fmt(stats(-np.sign(S.first5)*S.r935_1030, COST, "Fade first-5-min direction 09:35->10:30")))
# ORB 15 and 30 min on 5m closes
for orb_end in [945,1000,1030]:
    rows=[]
    for dt,g in reg.groupby("date"):
        g=g.sort_index(); rng=g[g.t<orb_end]
        if len(rng)<3: continue
        hi,lo=rng.High.max(),rng.Low.min(); after=g[g.t>=orb_end]
        pos=0
        for t,b in after.iterrows():
            if b.Close>hi: pos=1;entry=b.Close;break
            if b.Close<lo: pos=-1;entry=b.Close;break
        if pos==0: continue
        rows.append((pd.Timestamp(dt).tz_localize("UTC"), pos*100*(g.Close.iloc[-1]/entry-1)))
    r=pd.Series(dict(rows)); print(fmt(stats(r, COST, f"ORB 09:30-{orb_end} breakout on 5m close, exit close")))
print(fmt(stats(100*(S.c1600/S.o1530-1)*np.sign(S.o1530/S.o935-1), COST, "Last 30 min follow day")))
