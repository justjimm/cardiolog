import pandas as pd, numpy as np, sys
from lib import *
name=sys.argv[1]; COST=float(sys.argv[2])
def walker(bars, entry_t, cap_t, pcm, tmult, smult, conservative=True, tol=0.0, use_target=True):
    out=[]
    for dt,g in bars.groupby("date"):
        pc=pcm.get(dt)
        if pc is None or np.isnan(pc): continue
        g=g.sort_index(); e=g[g.t==entry_t]
        if len(e)==0: continue
        first=g[g.t==930]; open930=first.Open.iloc[0] if len(first) else e.Open.iloc[0]
        gap=open930-pc
        if gap==0: continue
        d=-np.sign(gap); entry=e.Open.iloc[0]
        target=entry+d*tmult*abs(gap); stop=entry-d*smult*abs(gap)
        # tol: price must go beyond the target by tol% of price for the limit to be considered filled
        tpx = target*(1+d*tol/100)
        walk=g[(g.t>=entry_t)&(g.t<cap_t)]; r=None; how="time"
        for _,b in walk.iterrows():
            hit_t = use_target and ((b.High>=tpx) if d>0 else (b.Low<=tpx))
            hit_s = (b.Low<=stop) if d>0 else (b.High>=stop)
            if hit_t and hit_s: r=(stop if conservative else target); how="stop" if conservative else "target"; break
            if hit_s: r=stop; how="stop"; break
            if hit_t: r=target; how="target"; break
        if r is None: r=walk.Close.iloc[-1]
        out.append((pd.Timestamp(dt).tz_localize("UTC"), 100*d*(r/entry-1), 100*gap/pc, how, d))
    return pd.DataFrame(out, columns=["t","r","gap","how","dir"]).set_index("t")
dd=load(name,"1d"); dd=dd[dd.index>=START-pd.Timedelta(days=5)]; pcm={d:c for d,c in zip(dd.index.date, dd.Close.shift(1).values)}  # daily index is UTC midnight of the trading date
h=load(name,"1h"); h=h[h.index>=START]; ny=h.index.tz_convert("America/New_York"); h["date"]=ny.date; h["t"]=ny.hour*100+ny.minute; h=h[(h.t>=930)&(h.t<1600)]
print(f"=== {name.upper()} fade-gap robustness (1h bars, entry 09:30, cap 10:30, target 0.5x gap, stop 1x gap, conservative), cost {COST}% ===")
o=walker(h,930,1030,pcm,0.5,1.0)
base=o[o.gap.abs()>=1.0]
print(fmt(stats(base.r, COST, "Base |gap|>=1%")))
print(fmt(stats(base.r, 0.30, "  same at 0.30% cost (wide open spread)")))
print(fmt(stats(base[base.dir<0].r, COST, "  gap UP days (short)")), "\n", fmt(stats(base[base.dir>0].r, COST, "  gap DOWN days (long)")))
print("  exit types:", base.how.value_counts().to_dict(), " mean r by exit:", base.groupby("how").r.mean().round(3).to_dict())
for tol in [0.1,0.2,0.3]:
    o2=walker(h,930,1030,pcm,0.5,1.0,tol=tol); print(fmt(stats(o2[o2.gap.abs()>=1.0].r, COST, f"  target must be exceeded by {tol}% to count as filled")))
o3=walker(h,930,1030,pcm,0.5,1.0,use_target=False); print(fmt(stats(o3[o3.gap.abs()>=1.0].r, COST, "  NO target: fade, stop 1x gap, exit at 10:30 close")))
o4=walker(h,930,1030,pcm,0.5,99.0); print(fmt(stats(o4[o4.gap.abs()>=1.0].r, COST, "  target 0.5x gap, NO stop, exit 10:30")))
q=(base.r-COST).groupby(base.index.tz_convert(None).to_period("Q")).agg(["count","mean"]).round(3); print("  by quarter:", {str(k):(int(v["count"]),v["mean"]) for k,v in q.iterrows()})
mth=(base.r-COST).groupby(base.index.tz_convert(None).to_period("M")).sum().round(2); print(f"  months positive: {(mth>0).sum()}/{len(mth)}; worst month {mth.min()}%, best {mth.max()}%")
print("  by gap size bucket:"); print(bucket_table(o.assign(fade=o.r, g=o.gap.abs()), "g","fade",[1,1.5,2,3,5,50], COST).to_string())
# ATR-relative: gap / 20-day avg true range (in %)
atr=(100*(dd.High-dd.Low)/dd.Open).rolling(20).mean().shift(1); atrm={d:a for d,a in zip(dd.index.date, atr.values)}
o["atr"]=[atrm.get(t.tz_convert("America/New_York").date()) for t in o.index]; o["gatr"]=o.gap.abs()/o.atr
print("  by |gap|/ATR:"); print(bucket_table(o.assign(fade=o.r), "gatr","fade",[0,0.25,0.5,0.75,1,10], COST).to_string())
