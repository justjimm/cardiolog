import sys, pandas as pd, numpy as np
path=sys.argv[1]
d=pd.read_csv(path, sep="\t", engine="python")
d.columns=[c.strip("<>").lower() for c in d.columns]
d["ts"]=pd.to_datetime(d["date"]+" "+d["time"], format="%Y.%m.%d %H:%M:%S")
d=d.set_index("ts").sort_index()[["open","high","low","close","tickvol","spread"]]
d["date"]=d.index.date; d["hm"]=d.index.hour*100+d.index.minute; d["dow"]=d.index.dayofweek
print(f"bars {len(d)}, {d.index.min()} .. {d.index.max()}, days {d.date.nunique()}")
fb=d.groupby("date").hm.first(); lb=d.groupby("date").hm.last()
print("first bar time of day (count):", fb.value_counts().head(4).to_dict(), " last bar:", lb.value_counts().head(4).to_dict())
print("bars per day:", d.groupby("date").size().describe()[["min","50%","max"]].to_dict())
# ---- spread (points, 1 point = 0.01 USD) ----
sp=d[d.spread>0]; print(f"spread recorded on {len(sp)} bars from {sp.index.min().date()}; mean {sp.spread.mean():.2f} pts = {100*(sp.spread*0.01/sp.close).mean():.3f}% of price; at first bar {100*(sp[sp.hm==sp.groupby('date').hm.transform('first')].spread*0.01/sp.close).mean():.3f}%")
print("spread % by hour (recorded bars):", (100*sp.spread*0.01/sp.close).groupby(sp.index.hour).mean().round(3).to_dict())
# cost model: Deriv target spread 0.14% + 0.02% slippage = 0.16% round trip (recorded spreads are lower; see above)
COST=float(sys.argv[2]) if len(sys.argv)>2 else 0.16
# ===================== helpers =====================
def stats(r, cost, label):
    r=pd.Series(r).dropna()-cost
    if len(r)==0: return f"{label}: n=0"
    n=len(r); m=r.mean(); t=m/(r.std()/np.sqrt(n)) if n>2 and r.std()>0 else np.nan
    g=r[r>0].sum(); l=-r[r<0].sum(); pf=g/l if l>0 else np.inf
    cum=r.cumsum(); dd=(cum-cum.cummax()).min()
    yrs=r.groupby(pd.DatetimeIndex(r.index).year).mean()
    ys=" ".join(f"{y}:{v:+.2f}" for y,v in yrs.items())
    return f"{label:<64} n={n:>4} win={100*(r>0).mean():>4.0f}% mean={m:+.3f}% t={t:5.2f} pf={pf:4.2f} tot={r.sum():+6.1f}% dd={dd:5.1f}% | by year {ys}"
def bracket(bars_after, entry, direction, target, stop, cap_bars):
    """walk up to cap_bars bars; return (ret%, how)"""
    w=bars_after.iloc[:cap_bars]
    for _,b in w.iterrows():
        ht=(b.high>=target) if direction>0 else (b.low<=target)
        hs=(b.low<=stop) if direction>0 else (b.high>=stop)
        if ht and hs: return 100*direction*(stop/entry-1),"both->stop"
        if hs: return 100*direction*(stop/entry-1),"stop"
        if ht: return 100*direction*(target/entry-1),"target"
    if len(w)==0: return np.nan,"none"
    return 100*direction*(w.close.iloc[-1]/entry-1),"time"
# ===================== OVERNIGHT GAPS =====================
days=sorted(d.date.unique()); bydate={dt:g for dt,g in d.groupby("date")}
rows=[]
for i in range(1,len(days)):
    g=bydate[days[i]]; p=bydate[days[i-1]]
    if len(g)<30: continue
    prev_close=p.close.iloc[-1]; o=g.open.iloc[0]
    gap=100*(o/prev_close-1)
    e2=g.iloc[1].open if len(g)>1 else o   # entry at second bar (13:35, Deriv's stated open)
    rows.append(dict(date=pd.Timestamp(days[i]), dow=g.dow.iloc[0], prev_close=prev_close, open=o, open2=e2, gap=gap, gapdays=(days[i]-days[i-1]).days,
                     close=g.close.iloc[-1], h=g.high.max(), l=g.low.min(),
                     c30=g.close.iloc[min(5,len(g)-1)], c60=g.close.iloc[min(11,len(g)-1)], c120=g.close.iloc[min(23,len(g)-1)],
                     filled=(g.low.min()<=prev_close) if gap>0 else (g.high.max()>=prev_close),
                     fill30=(g.low.iloc[:6].min()<=prev_close) if gap>0 else (g.high.iloc[:6].max()>=prev_close),
                     fill60=(g.low.iloc[:12].min()<=prev_close) if gap>0 else (g.high.iloc[:12].max()>=prev_close),
                     rng1h=100*(g.high.iloc[:12].max()-g.low.iloc[:12].min())/o, idx=i))
G=pd.DataFrame(rows).set_index("date")
atr=(100*(G.h-G.l)/G.open).rolling(20).mean().shift(1); G["gatr"]=G.gap.abs()/atr
print(f"\n=================== OVERNIGHT GAPS (Deriv feed), {len(G)} days ===================")
print(f"mean |gap| {G.gap.abs().mean():.2f}%, up {100*(G.gap>0).mean():.0f}%, fill by close {100*G.filled.mean():.0f}%, within 30 min {100*G.fill30.mean():.0f}%, within 1h {100*G.fill60.mean():.0f}%; first-hour range {G.rng1h.mean():.2f}%")
print("fill rate by |gap| bucket (30min / 1h / close):")
for lo,hi in [(0,0.5),(0.5,1),(1,2),(2,3),(3,5),(5,99)]:
    x=G[(G.gap.abs()>=lo)&(G.gap.abs()<hi)]; print(f"   [{lo},{hi}): n={len(x):>3}  {100*x.fill30.mean():>3.0f}% / {100*x.fill60.mean():>3.0f}% / {100*x.filled.mean():>3.0f}%")
print("\n--- simple fade / follow from the 13:35 open (second bar), by exit ---")
for col,lab in [("c30","30 min"),("c60","1 h"),("c120","2 h"),("close","close")]:
    r=-np.sign(G.gap)*100*(G[col]/G.open2-1)
    print(stats(r, COST, f"Fade, exit {lab}, all gaps")); print(stats(r[G.gap.abs()>=1], COST, f"  Fade, exit {lab}, |gap|>=1%")); print(stats(-r[G.gap.abs()>=1], COST, f"  Follow, exit {lab}, |gap|>=1%"))
print("\n--- fade by |gap|/ATR bucket, exit 1h ---")
r=-np.sign(G.gap)*100*(G.c60/G.open2-1)
for lo,hi in [(0,0.25),(0.25,0.5),(0.5,1),(1,10)]:
    x=r[(G.gatr>=lo)&(G.gatr<hi)]; print(stats(x, COST, f"  |gap|/ATR in [{lo},{hi})"))
print("\n--- BRACKET RULES from the 13:35 open (5-minute bars, stop counted first when both touched) ---")
for cap,capn in [(6,"30 min"),(12,"1 h"),(24,"2 h"),(78,"close")]:
    for mode in ["follow","fade"]:
        for tm,sm in [(1.0,0.5),(2.0,0.5),(0.5,1.0),(1.0,1.0)]:
            out=[]
            for dt,row in G.iterrows():
                g=bydate[dt.date()]
                if len(g)<3: continue
                dirn=np.sign(row.gap)*(1 if mode=="follow" else -1); entry=row.open2; gs=abs(row.open-row.prev_close)
                target=entry+dirn*tm*gs; stop=entry-dirn*sm*gs
                rr,how=bracket(g.iloc[1:], entry, dirn, target, stop, cap)
                out.append((dt,rr,how,row.gap))
            o=pd.DataFrame(out,columns=["t","r","how","gap"]).set_index("t")
            for lo in [0.0,1.0,2.0]:
                x=o[o.gap.abs()>=lo]
                if lo==0.0 or (tm,sm)==(1.0,0.5) or (tm,sm)==(0.5,1.0):
                    print(stats(x.r, COST, f"{mode:<6} cap {capn:<6} tgt {tm}x stop {sm}x |gap|>={lo}% (tgt {100*(x.how=='target').mean():.0f}% stop {100*x.how.str.contains('stop').mean():.0f}%)"))
# ===================== INTRADAY GAPS (bar-to-bar, same day) =====================
print("\n=================== INTRADAY GAPS: open of a 5-min bar vs previous bar's close, same day ===================")
d["prev_close"]=d.groupby("date").close.shift(1); d["ig"]=100*(d.open/d.prev_close-1)
d["rng"]=100*(d.high-d.low)/d.open; d["atr5"]=d.rng.rolling(78).mean().shift(1)
ig=d.dropna(subset=["ig"])
print(f"bars {len(ig)}: |intraday gap| mean {ig.ig.abs().mean():.3f}%, median {ig.ig.abs().median():.3f}%; share >0.2%: {100*(ig.ig.abs()>0.2).mean():.1f}%, >0.5%: {100*(ig.ig.abs()>0.5).mean():.2f}%, >1%: {100*(ig.ig.abs()>1).mean():.2f}%")
big=ig[ig.ig.abs()>0.5]; print("when do >0.5% intraday gaps occur (GMT hour: count):", big.index.hour.value_counts().sort_index().to_dict())
print("   by 5-min slot, top 8:", big.hm.value_counts().head(8).to_dict())
# forward returns after an intraday gap: enter at the gap bar's open (immediate) or at its close (5 min later)
for k in [1,3,6,12]:
    d[f"f{k}_o"]=100*(d.groupby("date").close.shift(-(k-1))/d.open-1)      # from this bar's open to close k bars later (k-1 bars ahead)
    d[f"f{k}_c"]=100*(d.groupby("date").close.shift(-k)/d.close-1)        # from this bar's close to close k bars later
ig=d.dropna(subset=["ig"])
for thr in [0.3,0.5,1.0]:
    x=ig[ig.ig.abs()>=thr]
    print(f"\n--- intraday gaps |gap|>={thr}% : n={len(x)} ---")
    for k in [1,3,6,12]:
        print(stats(-np.sign(x.ig)*x[f"f{k}_o"], COST, f"  Fade at gap-bar OPEN, exit after {k} bar(s) ({5*k} min)"))
        print(stats(-np.sign(x.ig)*x[f"f{k}_c"], COST, f"  Fade at gap-bar CLOSE, exit {k} bar(s) later"))
    print(stats(np.sign(x.ig)*x["f6_c"], COST, f"  Follow at gap-bar CLOSE, exit 6 bars later"))
    # excluding the first 30 minutes of the day
    y=x[x.hm>=1405]
    print(stats(-np.sign(y.ig)*y["f6_c"], COST, f"  Fade at CLOSE, 6 bars, excluding first 30 min (n={len(y)})"))
    print(stats(-np.sign(y.ig)*y["f3_o"], COST, f"  Fade at OPEN, 3 bars, excluding first 30 min (n={len(y)})"))
# relative to 5-min ATR
x=ig[(ig.ig.abs()>=3*ig.atr5)&(ig.ig.abs()>=0.3)]
print(f"\n--- intraday gaps >= 3x the rolling 5-min range and >=0.3%: n={len(x)} ---")
for k in [1,3,6,12]: print(stats(-np.sign(x.ig)*x[f"f{k}_c"], COST, f"  Fade at CLOSE, exit {k} bars later"))
# intraday gap fill within N bars
def filled_within(row_idx, n):
    pass
ig2=ig[ig.ig.abs()>=0.5].copy()
res={}
for n in [3,6,12]:
    hit=[]
    for t,row in ig2.iterrows():
        g=bydate[row.date]; pos=g.index.get_loc(t); w=g.iloc[pos:pos+n]
        hit.append((w.low.min()<=row.prev_close) if row.ig>0 else (w.high.max()>=row.prev_close))
    res[n]=100*np.mean(hit)
print("intraday gaps >=0.5%: filled (prior bar close touched) within 3 / 6 / 12 bars:", {k:round(v) for k,v in res.items()})
# bracket on intraday gaps >=0.5%, entry at gap-bar close, cap 6 and 12 bars
print("\n--- bracket rules on intraday gaps >=0.5%, entry at the gap bar's close ---")
for cap in [6,12]:
    for mode in ["follow","fade"]:
        for tm,sm in [(1.0,0.5),(0.5,1.0),(1.0,1.0)]:
            out=[]
            for t,row in ig2.iterrows():
                g=bydate[row.date]; pos=g.index.get_loc(t); after=g.iloc[pos+1:]
                if len(after)<2: continue
                dirn=np.sign(row.ig)*(1 if mode=="follow" else -1); entry=row.close; gs=abs(row.open-row.prev_close)
                rr,how=bracket(after, entry, dirn, entry+dirn*tm*gs, entry-dirn*sm*gs, cap); out.append((t,rr,how))
            o=pd.DataFrame(out,columns=["t","r","how"]).set_index("t")
            print(stats(o.r, COST, f"{mode:<6} cap {5*cap:>2} min tgt {tm}x stop {sm}x (tgt {100*(o.how=='target').mean():.0f}% stop {100*o.how.str.contains('stop').mean():.0f}%)"))
G.to_csv("deriv_tqqq_gaps.csv")
# ===================== STOP SWEEP: what stop (if any) makes the overnight-gap trade workable? =====================
print("\n=================== STOP SWEEP on overnight gaps, entry 13:35, |gap|>=1% (also all gaps for the best rows) ===================")
hdr=f"{'mode':<6} {'cap':<6} {'target':<7} {'stop':<8} {'n':>4} {'win':>4} {'mean':>7} {'t':>6} {'stop%':>5}  by year"
print(hdr)
best=[]
for cap,capn in [(6,"30min"),(12,"1h"),(24,"2h"),(78,"close")]:
    for mode in ["follow","fade"]:
        for tm in [1.0,2.0,None]:
            for sm in [0.5,1.0,1.5,2.0,3.0,None]:
                out=[]
                for dt,row in G.iterrows():
                    if abs(row.gap)<1.0: continue
                    g=bydate[dt.date()]
                    if len(g)<3: continue
                    dirn=np.sign(row.gap)*(1 if mode=="follow" else -1); entry=row.open2; gs=abs(row.open-row.prev_close)
                    target=entry+dirn*(tm if tm else 99)*gs; stop=entry-dirn*(sm if sm else 99)*gs
                    rr,how=bracket(g.iloc[1:], entry, dirn, target, stop, cap); out.append((dt,rr,how))
                o=pd.DataFrame(out,columns=["t","r","how"]).set_index("t"); r=o.r.dropna()-COST
                n=len(r); m=r.mean(); t=m/(r.std()/np.sqrt(n)); yrs=r.groupby(pd.DatetimeIndex(r.index).year).mean()
                best.append((m,t,mode,capn,tm,sm,n,100*(r>0).mean(),100*o.how.str.contains('stop').mean(),yrs))
best.sort(key=lambda x:-x[0])
for m,t,mode,capn,tm,sm,n,win,sp_,yrs in best[:15]:
    print(f"{mode:<6} {capn:<6} {str(tm):<7} {str(sm):<8} {n:>4} {win:>3.0f}% {m:+.3f}% {t:6.2f} {sp_:4.0f}%  " + " ".join(f"{y}:{v:+.2f}" for y,v in yrs.items()))
print("... worst 5:")
for m,t,mode,capn,tm,sm,n,win,sp_,yrs in best[-5:]:
    print(f"{mode:<6} {capn:<6} {str(tm):<7} {str(sm):<8} {n:>4} {win:>3.0f}% {m:+.3f}% {t:6.2f} {sp_:4.0f}%  " + " ".join(f"{y}:{v:+.2f}" for y,v in yrs.items()))
# fixed-percent stops and ATR stops for the two best modes without target, exit at close and at 1h
print("\n--- fixed % stops, no target: follow vs fade, |gap|>=1% ---")
for cap,capn in [(12,"1h"),(78,"close")]:
    for mode in ["follow","fade"]:
        for sp_pct in [0.5,1.0,1.5,2.0,3.0,None]:
            out=[]
            for dt,row in G.iterrows():
                if abs(row.gap)<1.0: continue
                g=bydate[dt.date()]
                if len(g)<3: continue
                dirn=np.sign(row.gap)*(1 if mode=="follow" else -1); entry=row.open2
                stop=entry*(1-dirn*(sp_pct if sp_pct else 99)/100)
                rr,how=bracket(g.iloc[1:], entry, dirn, entry+dirn*99, stop, cap); out.append((dt,rr,how))
            o=pd.DataFrame(out,columns=["t","r","how"]).set_index("t")
            print(stats(o.r, COST, f"{mode:<6} cap {capn:<5} stop {str(sp_pct)+'%':<5} no target (stopped {100*o.how.str.contains('stop').mean():.0f}%)"))
