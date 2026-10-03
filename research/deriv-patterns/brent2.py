import pandas as pd, numpy as np
from lib import *
COST=0.03
h = load("brent","1h"); h=h[h.index>=START-pd.Timedelta(days=10)]
h["date"]=h.index.date; h["hour"]=h.index.hour; h["dow"]=h.index.dayofweek; h["ret"]=100*(h.Close/h.Open-1)
lon = h.index.tz_convert("Europe/London"); h["lhour"]=lon.hour
ny = h.index.tz_convert("America/New_York"); h["nhour"]=ny.hour
d = h[(h.hour<=20)&(h.dow<=4)].copy()
sess = pd.read_csv("brent_sessions.csv", index_col=0, parse_dates=True); sess.index=pd.to_datetime(sess.index, utc=True)
def robust(r, label, cost=COST):
    r=pd.Series(r).dropna()-cost
    w=r.clip(lower=r.quantile(0.05), upper=r.quantile(0.95))
    trim=r[r.abs()<3]
    q=r.groupby(r.index.tz_convert(None).to_period("Q")).mean()
    print(f"{label:<58} n={len(r)} mean={r.mean():.3f} median={r.median():.3f} win={100*(r>0).mean():.1f} winsor5={w.mean():.3f} t_w={w.mean()/(w.std()/np.sqrt(len(w))):.2f} trim|r|<3={trim.mean():.3f}(n={len(trim)}) worst={r.min():.2f} best={r.max():.2f}")
    print("     quarterly mean:", " ".join(f"{str(k)}:{v:+.2f}" for k,v in q.items()), " | positive quarters:", f"{(q>0).sum()}/{len(q)}")
print("=== 1. WEEKEND GAP FADE deep-dive ===")
wk = sess[(sess.dow==0)&(sess.gapdays==3)].copy()
def fade_fill(w):
    out={}
    for t,row in w.iterrows():
        s=-np.sign(row.gap)
        if s==0: continue
        out[t]=100*(row.prev_close/row.open-1)*s if row.filled else 100*(row.close/row.open-1)*s
    return pd.Series(out)
robust(fade_fill(wk), "Fade to fill, all gaps")
robust(fade_fill(wk[wk.gap>0]), "Fade to fill, GAP UP only (short)")
robust(fade_fill(wk[wk.gap<0]), "Fade to fill, GAP DOWN only (long)")
robust(fade_fill(wk[wk.gap.abs()>0.3]), "Fade to fill, |gap|>0.3%")
robust(fade_fill(wk[(wk.gap>0.3)]), "Fade to fill, gap up >0.3% (short)")
robust(fade_fill(wk[(wk.gap<-0.3)]), "Fade to fill, gap down >0.3% (long)")
# exit 13:00 variant and partial target (half fill)
for col in ["c8","c13","close"]:
    r=-np.sign(wk.gap)*100*(wk[col]/wk.open-1)
    robust(r[wk.gap>0.3], f"Fade gap-up>0.3% exit {col}")
    robust(r[wk.gap<-0.3], f"Fade gap-down>0.3% exit {col}")
# Monday full-day direction stats
print("\nMonday session by gap size bucket (gap up):"); print(bucket_table(wk[wk.gap>0].assign(sr=-wk.sess_ret), "gap","sr",[0,0.3,0.6,1,2,20]).to_string())
print("Monday session by gap size bucket (gap down, long):"); print(bucket_table(wk[wk.gap<0].assign(sr=wk.sess_ret, g=-wk.gap), "g","sr",[0,0.3,0.6,1,2,20]).to_string())
print("Largest weekend gaps:"); print(wk.gap.abs().sort_values(ascending=False).head(8).round(2).to_string())
# time of fill: hour at which prev_close touched
rows=[]
for t,row in wk.iterrows():
    g=d[d.date==t.date()]
    hit=None
    for tt,b in g.iterrows():
        if (row.gap>0 and b.Low<=row.prev_close) or (row.gap<0 and b.High>=row.prev_close): hit=b.hour;break
    rows.append(hit)
wk["fill_hour"]=rows
print("fill hour distribution (Monday):", wk.fill_hour.value_counts().sort_index().to_dict())
print("cumulative fill % by hour:", (wk.fill_hour.value_counts().sort_index().cumsum()/len(wk)*100).round(0).to_dict())

print("\n=== 2. FADE EARLY ASIA MOVE (00:00->03:00 GMT) ===")
e=100*(sess.c3/sess.open-1)
for X,col in [(8,"c8"),(13,"c13"),(21,"close")]:
    late=100*(sess[col]/sess.c3-1)
    for thr in [0.3,0.5,0.8]:
        m=e.abs()>thr
        robust((-np.sign(e)*late)[m], f"Fade |00-03|>{thr}% exit {X}:00")
    m=e.abs()>0.5
    robust((-np.sign(e)*late)[m&(e>0)], f"  ..>0.5% UP moves (short) exit {X}")
    robust((-np.sign(e)*late)[m&(e<0)], f"  ..>0.5% DOWN moves (long) exit {X}")
    robust((-np.sign(e)*late)[m&(sess.dow!=0)], f"  ..>0.5% excl Monday exit {X}")
    robust((-np.sign(e)*late)[m&(sess.dow==0)], f"  ..>0.5% Monday only exit {X}")
# also 00->02
e2=100*(d[d.hour==2].groupby("date").Close.last()); e2.index=pd.to_datetime(e2.index,utc=True); e2=100*(e2.reindex(sess.index)/100/sess.open-1)
late=100*(sess.close/ (sess.open*(1+e2/100)) -1)
robust((-np.sign(e2)*late)[e2.abs()>0.5], "Fade |00-02|>0.5% exit 21:00")

print("\n=== 3. LONDON OPEN SHORT ===")
def win(h1,h2,col="hour"):
    o=d[d[col]==h1].groupby("date").Open.first(); c=d[d[col]==h2].groupby("date").Close.last()
    r=(100*(c/o-1)).dropna(); r.index=pd.to_datetime(r.index,utc=True); return r[r.index>=START]
for a,b in [(7,7),(7,8),(8,8),(7,9),(6,8)]:
    robust(-win(a,b), f"Short {a:02d}:00-{b+1:02d}:00 GMT")
for a,b in [(8,8),(8,9),(7,8),(9,9)]:
    robust(-win(a,b,"lhour"), f"Short {a:02d}:00-{b+1:02d}:00 LONDON local time")
# by dow
r=-win(7,8); print("by dow:", r.groupby(r.index.dayofweek).agg(["count","mean","median"]).round(3).to_dict())
# dependence on asia move
asia=100*(sess.c6/sess.open-1).reindex(r.index)
print("short 07-09 when asia up:", r[asia>0].mean().round(3), "n", (asia>0).sum(), " when asia down:", r[asia<0].mean().round(3))
# then recovery 09-13?
robust(win(9,12), "Long 09:00-13:00 GMT")
robust(win(9,9), "Long 09:00-10:00 GMT")
robust(win(1,2), "Long 01:00-03:00 GMT")
robust(win(18,18), "Long 18:00-19:00 GMT")
robust(-win(20,20), "Short 20:00-21:00 GMT")
robust(win(13,15), "Long 13:00-16:00 GMT (US open)")
robust(win(13,15,"nhour")*0+win(13,15), "placeholder")
# NY local
for a,b in [(9,10),(9,11),(8,9),(10,10)]:
    robust(win(a,b,"nhour"), f"Long {a:02d}:00-{b+1:02d}:00 NEW YORK local time")
# Big monthly outliers check: 07:00 bar worst days
x=d[(d.hour==7)&(d.index>=START)].ret.sort_values(); print("worst 07:00 bars:", x.head(6).round(2).to_dict())
