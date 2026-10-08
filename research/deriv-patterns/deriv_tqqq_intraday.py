import sys, pandas as pd, numpy as np
path=sys.argv[1]
d=pd.read_csv(path, sep="\t", engine="python"); d.columns=[c.strip("<>").lower() for c in d.columns]
d["ts"]=pd.to_datetime(d["date"]+" "+d["time"], format="%Y.%m.%d %H:%M:%S"); d=d.set_index("ts").sort_index()
d["date"]=d.index.date; d["hm"]=d.index.hour*100+d.index.minute
d["prev_close"]=d.groupby("date").close.shift(1)
d["gap_usd"]=(d.open-d.prev_close).round(2); d["gap_ticks"]=(d.gap_usd/0.01).round().astype("Int64"); d["gap_pct"]=100*(d.open/d.prev_close-1)
g=d.dropna(subset=["prev_close"]).copy()
nz=g[g.gap_ticks!=0]
print(f"bar transitions within a day: {len(g)}; with open != previous close: {len(nz)} ({100*len(nz)/len(g):.1f}%); up {100*(nz.gap_ticks>0).mean():.0f}%")
print("size in ticks (1 tick = 0.01 USD):", nz.gap_ticks.abs().value_counts().sort_index().head(12).to_dict())
print(f"size in %: mean {nz.gap_pct.abs().mean():.3f}%, median {nz.gap_pct.abs().median():.3f}%, 90th pct {nz.gap_pct.abs().quantile(0.9):.3f}%, max {nz.gap_pct.abs().max():.2f}%")
print("by year, share of transitions with a gap:", g.groupby(g.index.year).apply(lambda x:100*(x.gap_ticks!=0).mean()).round(1).to_dict())
print("gaps by GMT hour (count of non-zero gaps / transitions):", (nz.groupby(nz.index.hour).size()/g.groupby(g.index.hour).size()*100).round(1).to_dict())
print("mean |gap| % by GMT hour:", nz.groupby(nz.index.hour).gap_pct.apply(lambda x:x.abs().mean()).round(3).to_dict())
# ---- forward outcomes ----
for k in [1,2,3,6,12]:
    g[f"f{k}o"]=100*(g.groupby("date").close.shift(-(k-1))/g.open-1)   # from gap bar open to close k bars later (k-1 ahead)
    g[f"f{k}c"]=100*(g.groupby("date").close.shift(-k)/g.close-1)     # from gap bar close
# fill: does price touch prev close within n bars (including the gap bar itself)?
for n in [1,3,6]:
    lo=g.groupby("date").low.transform(lambda x:x[::-1].rolling(n,min_periods=1).min()[::-1])
    hi=g.groupby("date").high.transform(lambda x:x[::-1].rolling(n,min_periods=1).max()[::-1])
    g[f"fill{n}"]=np.where(g.gap_ticks>0, lo<=g.prev_close, hi>=g.prev_close)
nz=g[g.gap_ticks!=0].copy()
def line(x, col, cost, label):
    r=x[col].dropna(); 
    if len(r)==0: return
    rn=r-cost; t=rn.mean()/(rn.std()/np.sqrt(len(rn))) if len(rn)>2 else np.nan
    yrs=rn.groupby(pd.DatetimeIndex(rn.index).year).mean()
    print(f"{label:<58} n={len(r):>6} gross={r.mean():+.4f}% net={rn.mean():+.4f}% win(net)={100*(rn>0).mean():>4.1f}% t={t:6.2f} | " + " ".join(f"{y}:{v:+.3f}" for y,v in yrs.items()))
COSTS=[0.05]
print("\n=== FILL RATES (prior close touched) by gap size in ticks: within the gap bar / 3 bars / 6 bars ===")
for lo,hi in [(1,1),(2,2),(3,4),(5,9),(10,999)]:
    x=nz[(nz.gap_ticks.abs()>=lo)&(nz.gap_ticks.abs()<=hi)]
    print(f"  {lo}-{hi} ticks: n={len(x):>5}  {100*x.fill1.mean():>4.0f}% / {100*x.fill3.mean():>4.0f}% / {100*x.fill6.mean():>4.0f}%   mean |gap| {x.gap_pct.abs().mean():.3f}%")
print("\n=== FADE every intraday gap (enter at the gap bar's open, against the gap), by exit; cost 0.05% ===")
for k in [1,3,6,12]:
    nz[f"fade{k}o"]=-np.sign(nz.gap_pct)*nz[f"f{k}o"]; nz[f"fade{k}c"]=-np.sign(nz.gap_pct)*nz[f"f{k}c"]
    line(nz, f"fade{k}o", 0.05, f"all gaps, entry at gap-bar open, exit after {k} bar(s)")
for k in [1,3,6,12]:
    line(nz, f"fade{k}c", 0.05, f"all gaps, entry at gap-bar close, exit {k} bar(s) later")
print("\n--- by gap size, entry at gap-bar OPEN, exit after 3 bars (15 min) ---")
for lo,hi in [(1,1),(2,2),(3,4),(5,9),(10,999)]:
    x=nz[(nz.gap_ticks.abs()>=lo)&(nz.gap_ticks.abs()<=hi)]; line(x, "fade3o", 0.05, f"  {lo}-{hi} ticks")
print("--- by gap size, entry at gap-bar OPEN, exit after 1 bar (5 min) ---")
for lo,hi in [(1,1),(2,2),(3,4),(5,9),(10,999)]:
    x=nz[(nz.gap_ticks.abs()>=lo)&(nz.gap_ticks.abs()<=hi)]; line(x, "fade1o", 0.05, f"  {lo}-{hi} ticks")
print("--- by gap size, entry at gap-bar CLOSE, exit 3 bars later ---")
for lo,hi in [(1,1),(2,2),(3,4),(5,9),(10,999)]:
    x=nz[(nz.gap_ticks.abs()>=lo)&(nz.gap_ticks.abs()<=hi)]; line(x, "fade3c", 0.05, f"  {lo}-{hi} ticks")
print("--- by gap size in %, entry at gap-bar OPEN, exit after 3 bars ---")
for lo,hi in [(0,0.02),(0.02,0.05),(0.05,0.1),(0.1,0.2),(0.2,99)]:
    x=nz[(nz.gap_pct.abs()>=lo)&(nz.gap_pct.abs()<hi)]; line(x, "fade3o", 0.05, f"  [{lo}%,{hi}%)")
print("\n--- by time of day (GMT hour), all gaps, entry at OPEN, exit after 3 bars ---")
for h in sorted(nz.index.hour.unique()):
    line(nz[nz.index.hour==h], "fade3o", 0.05, f"  hour {h:02d}")
print("\n--- direction split, all gaps, entry at OPEN, exit after 3 bars ---")
line(nz[nz.gap_ticks>0], "fade3o", 0.05, "  gap UP (short)"); line(nz[nz.gap_ticks<0], "fade3o", 0.05, "  gap DOWN (long)")
print("\n--- same at the measured spread only (0.017% + 0.013% slippage = 0.03%) and at zero cost, entry at OPEN exit 3 bars, gaps >=3 ticks ---")
x=nz[nz.gap_ticks.abs()>=3]
for c in [0.0,0.03,0.05]: line(x, "fade3o", c, f"  cost {c}%")
print("\n--- FOLLOW (with the gap), all gaps and >=3 ticks, entry at OPEN, exit after 3 and 6 bars ---")
for k in [3,6]:
    nz[f"fol{k}o"]=np.sign(nz.gap_pct)*nz[f"f{k}o"]; line(nz, f"fol{k}o", 0.05, f"  all gaps, exit after {k} bars"); line(nz[nz.gap_ticks.abs()>=3], f"fol{k}o", 0.05, f"  >=3 ticks, exit after {k} bars")
# relative size: gap vs the previous bar's range
nz["prev_rng"]=nz.groupby("date").apply(lambda x:(x.high-x.low).shift(1)).reset_index(level=0,drop=True) if False else (d.high-d.low).groupby(d.date).shift(1).reindex(nz.index)
nz["rel"]=nz.gap_usd.abs()/nz.prev_rng.replace(0,np.nan)
print("\n--- gap relative to the previous bar's high-low range, entry at OPEN, exit after 3 bars ---")
for lo,hi in [(0,0.25),(0.25,0.5),(0.5,1),(1,99)]:
    xx=nz[(nz.rel>=lo)&(nz.rel<hi)]; line(xx, "fade3o", 0.05, f"  gap/prev range in [{lo},{hi})")
nz[["gap_ticks","gap_pct","fill1","fill3","fill6","fade1o","fade3o","fade6o","fade3c"]].to_csv("deriv_tqqq_intraday_gaps.csv")
