import pandas as pd, numpy as np, sys
from lib import *
name=sys.argv[1]; COST=float(sys.argv[2])
def run_bars(bars, entry_t, cap_t, prev_close_map, tmult, smult, entry_col="Open", conservative=True):
    """bars: intraday df with NY 'date','t' (hhmm). Enter at open of bar at entry_t, walk bars until cap_t (exclusive of bar starting at cap_t)."""
    out=[]
    for dt,g in bars.groupby("date"):
        pc=prev_close_map.get(dt)
        if pc is None or np.isnan(pc): continue
        g=g.sort_index()
        e=g[g.t==entry_t]
        if len(e)==0: continue
        first=g[g.t==930]
        open930=first.Open.iloc[0] if len(first) else e.Open.iloc[0]
        gap=open930-pc
        if gap==0: continue
        d=np.sign(gap); entry=e[entry_col].iloc[0]
        target=entry+d*tmult*abs(gap); stop=entry-d*smult*abs(gap)
        walk=g[(g.t>=entry_t)&(g.t<cap_t)]
        r=None
        for _,b in walk.iterrows():
            hit_t = b.High>=target if d>0 else b.Low<=target
            hit_s = b.Low<=stop if d>0 else b.High>=stop
            if hit_t and hit_s: r=(stop if conservative else target); break
            if hit_s: r=stop; break
            if hit_t: r=target; break
        if r is None: r=walk.Close.iloc[-1]
        out.append((pd.Timestamp(dt).tz_localize("UTC"), 100*d*(r/entry-1), 100*gap/pc, r==target, r==stop))
    o=pd.DataFrame(out, columns=["t","r","gap","hit_t","hit_s"]).set_index("t"); return o
def report(o, title, cost):
    print(f"\n### {title}")
    for lo in [0.0,0.3,0.5,1.0,2.0]:
        m=o.gap.abs()>=lo; x=o[m]
        if len(x)<5: continue
        st=stats(x.r, cost, f"|gap|>={lo}%  (target hit {100*x.hit_t.mean():.0f}%, stop hit {100*x.hit_s.mean():.0f}%)")
        print(fmt(st))
# ---------- 2-year test on 1h bars: entry 09:30 bar open, cap = end of first hour (10:30) ----------
dd=load(name,"1d"); dd=dd[dd.index>=START-pd.Timedelta(days=5)]; pcm={d:c for d,c in zip(dd.index.date, dd.Close.shift(1).values)}  # daily index is UTC midnight of the trading date
h=load(name,"1h"); h=h[h.index>=START]; ny=h.index.tz_convert("America/New_York"); h["date"]=ny.date; h["t"]=ny.hour*100+ny.minute
h=h[(h.t>=930)&(h.t<1600)]
print(f"=== {name.upper()} GAP FOLLOW, cost {COST}% ===")
print("2-year test, hourly bars: enter at the 09:30 open, cap at 10:30 (1 hour). Conservative: if target and stop both touched in the bar, count the stop.")
for tm in [1.0,2.0]:
    o=run_bars(h, 930, 1030, pcm, tm, 0.5); report(o, f"1h cap, target {tm:.0f}x gap, stop 0.5x gap, CONSERVATIVE", COST)
    o2=run_bars(h, 930, 1030, pcm, tm, 0.5, conservative=False); report(o2, f"1h cap, target {tm:.0f}x gap, stop 0.5x gap, OPTIMISTIC (target first)", COST)
# ---------- 60-day test on 5m bars: entry 09:35 (Deriv open), caps 30 min and 1 h ----------
m=load(name,"5m"); ny=m.index.tz_convert("America/New_York"); m["date"]=ny.date; m["t"]=ny.hour*100+ny.minute; m=m[(m.t>=930)&(m.t<1600)]
print(f"\n60-session test, 5-minute bars {m.index.min().date()}..{m.index.max().date()}: enter at the 09:35 open (Deriv's open)")
for cap,capname in [(1005,"30 min"),(1035,"1 hour")]:
    for tm in [1.0,2.0]:
        o=run_bars(m, 935, cap, pcm, tm, 0.5); report(o, f"{capname} cap, target {tm:.0f}x gap, stop 0.5x gap, entry 09:35", COST)
print("\nSame 60 sessions, entry at the 09:30 open (what the exchange gives, not Deriv):")
for cap,capname in [(1005,"30 min"),(1035,"1 hour")]:
    for tm in [1.0,2.0]:
        o=run_bars(m, 930, cap, pcm, tm, 0.5); report(o, f"{capname} cap, target {tm:.0f}x gap, stop 0.5x gap, entry 09:30", COST)
