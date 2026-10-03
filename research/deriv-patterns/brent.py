import pandas as pd, numpy as np, json
from lib import *
COST=0.03
h = load("brent","1h"); h = h[h.index>=START- pd.Timedelta(days=10)]
h["date"]=h.index.date; h["hour"]=h.index.hour; h["dow"]=h.index.dayofweek
h["ret"]=100*(h.Close/h.Open-1)
# Deriv session bars: 00:00..20:00 GMT Mon-Fri
d = h[(h.hour<=20)&(h.dow<=4)].copy()
res={}
days = d.groupby("date")
sess = pd.DataFrame({"open":days.Open.first(),"close":days.Close.last(),"high":days.High.max(),"low":days.Low.min(),
                     "first_hour":days.hour.first(),"last_hour":days.hour.last(),"nbars":days.size()})
sess.index=pd.to_datetime(sess.index, utc=True); sess["dow"]=sess.index.dayofweek
sess = sess[(sess.nbars>=15)&(sess.first_hour==0)]
sess["prev_close"]=sess.close.shift(1); sess["prev_date"]=pd.Series(sess.index, index=sess.index).shift(1)
sess["gapdays"]=(sess.index - sess.prev_date).dt.days
sess["gap"]=100*(sess.open/sess.prev_close-1)
sess["sess_ret"]=100*(sess.close/sess.open-1)
sess["atr"]=(100*(sess.high-sess.low)/sess.open).rolling(20).mean().shift(1)
sess["filled"]=((sess.gap>0)&(sess.low<=sess.prev_close))|((sess.gap<0)&(sess.high>=sess.prev_close))
# exit prices at various hours
def px_at(hour):
    x=d[d.hour==hour].groupby("date").Close.last(); x.index=pd.to_datetime(x.index,utc=True); return x
for hh in [3,6,7,8,9,10,12,13,14,15,16,18]:
    sess[f"c{hh}"]=px_at(hh).reindex(sess.index)
sess=sess[sess.index>=START]
print("sessions", len(sess), sess.index.min().date(), sess.index.max().date())
# ---------- WEEKEND GAP ----------
wk = sess[(sess.dow==0)&(sess.gapdays==3)].copy()
print("\n=== WEEKEND GAP (Fri 21:00 -> Mon 00:00 GMT) ===")
print(f"n={len(wk)} mean gap={wk.gap.mean():.3f}% median={wk.gap.median():.3f}% up%={100*(wk.gap>0).mean():.1f} |gap| mean={wk.gap.abs().mean():.3f}% max={wk.gap.abs().max():.2f}%")
print("fill by Mon close: ", f"{100*wk.filled.mean():.1f}%", " | fill when |gap|>0.3%:", f"{100*wk[wk.gap.abs()>0.3].filled.mean():.1f}% (n={int((wk.gap.abs()>0.3).sum())})", " | |gap|>0.6%:", f"{100*wk[wk.gap.abs()>0.6].filled.mean():.1f}% (n={int((wk.gap.abs()>0.6).sum())})")
print(fmt(stats(wk.gap, COST, "Weekend hold long (Fri 21:00 -> Mon 00:00)")))
print(fmt(stats(-wk.gap, COST, "Weekend hold short")))
for hh in [3,8,13,None]:
    col = f"c{hh}" if hh else "close"
    r = 100*(wk[col]/wk.open-1)
    sign=-np.sign(wk.gap)
    print(fmt(stats(sign*r, COST, f"Fade weekend gap, exit {hh or 21}:00 GMT, all gaps")))
    big = wk.gap.abs()>0.3
    print(fmt(stats((sign*r)[big], COST, f"Fade weekend gap |gap|>0.3%, exit {hh or 21}:00")))
    big = wk.gap.abs()>0.6
    print(fmt(stats((sign*r)[big], COST, f"Fade weekend gap |gap|>0.6%, exit {hh or 21}:00")))
# fade with target = fill, exit Mon close otherwise
def fade_target(w, stop_mult=None):
    out=[]
    for t,row in w.iterrows():
        s=-np.sign(row.gap)
        if s==0: continue
        if row.filled: r=100*(row.prev_close/row.open-1)*s
        else: r=100*(row.close/row.open-1)*s
        if stop_mult is not None:
            stop = abs(row.gap)*stop_mult
            adverse = 100*(row.high/row.open-1) if s<0 else 100*(row.open/row.low-1)
            if adverse>=stop and not row.filled: r=-stop
            elif adverse>=stop and row.filled: r=-stop  # conservative: assume stop hit first
        out.append((t,r))
    return pd.Series(dict(out))
print(fmt(stats(fade_target(wk), COST, "Fade weekend gap, target=fill else Mon close")))
print(fmt(stats(fade_target(wk[wk.gap.abs()>0.3]), COST, "Fade weekend gap |gap|>0.3%, target=fill else Mon close")))
print(fmt(stats(fade_target(wk[wk.gap.abs()>0.3],1.0), COST, "Fade |gap|>0.3%, target=fill, stop=1x gap (conservative)")))
print(fmt(stats(np.sign(wk.gap)*wk.sess_ret, COST, "Follow weekend gap, exit Mon close")))
print(bucket_table(wk.assign(fade=-np.sign(wk.gap)*wk.sess_ret, gabs=wk.gap.abs()), "gabs", "fade", [0,0.2,0.4,0.7,1.0,10], COST).to_string())
print("Monday session return by gap sign:", wk.groupby(np.sign(wk.gap)).sess_ret.agg(["count","mean","median"]).round(3).to_string())
res["weekend"]={"n":len(wk),"mean_gap":wk.gap.mean(),"up":100*(wk.gap>0).mean(),"fill":100*wk.filled.mean(),"abs_mean":wk.gap.abs().mean()}
# ---------- OVERNIGHT (Tue-Fri 21:00->00:00) ----------
on = sess[(sess.gapdays==1)].copy()
print("\n=== OVERNIGHT GAP Tue-Fri (21:00 -> 00:00 GMT) ===")
print(f"n={len(on)} mean={on.gap.mean():.3f}% |gap| mean={on.gap.abs().mean():.3f}% fill by close={100*on.filled.mean():.1f}%")
print(fmt(stats(on.gap, COST, "Overnight hold long (21:00->00:00)")))
print(fmt(stats(-np.sign(on.gap)*on.sess_ret, COST, "Fade overnight gap exit 21:00")))
print(fmt(stats(-np.sign(on.gap)*100*(on.c8/on.open-1), COST, "Fade overnight gap exit 08:00")))
print(fmt(stats(np.sign(on.gap)*on.sess_ret, COST, "Follow overnight gap exit 21:00")))
print(bucket_table(on.assign(fade=-np.sign(on.gap)*on.sess_ret, gabs=on.gap.abs()), "gabs", "fade", [0,0.1,0.2,0.4,10], COST).to_string())
# ---------- DAY OF WEEK ----------
print("\n=== SESSION RETURN BY DAY OF WEEK (00:00->21:00 GMT) ===")
for dw,nm in enumerate("Mon Tue Wed Thu Fri".split()):
    print(fmt(stats(sess[sess.dow==dw].sess_ret, COST, f"Long session {nm}")))
print(fmt(stats(sess.sess_ret, COST, "Long every session")))
# ---------- HOUR OF DAY ----------
print("\n=== HOURLY BAR RETURNS (GMT) all sessions ===")
dd=d[d.index>=START]
g=dd.groupby("hour").ret
tab=pd.DataFrame({"n":g.size(),"mean":g.mean().round(4),"win":(100*g.apply(lambda x:(x>0).mean())).round(1),"t":(g.mean()/(g.std()/np.sqrt(g.size()))).round(2),"absmean":g.apply(lambda x:x.abs().mean()).round(3),
                  "IS_mean":dd[dd.index<SPLIT].groupby("hour").ret.mean().round(4),"OOS_mean":dd[dd.index>=SPLIT].groupby("hour").ret.mean().round(4),
                  "range":(100*(dd.High-dd.Low)/dd.Open).groupby(dd.hour).mean().round(3)})
print(tab.to_string())
res["hourly"]=tab.reset_index().to_dict(orient="records")
print("\n=== HOURLY by DOW mean ret (GMT) ===")
print(dd.pivot_table(index="hour",columns="dow",values="ret",aggfunc="mean").round(3).to_string())
# ---------- SESSION BLOCKS ----------
def blk(a,b,name):
    # return from close of bar a-1 (= open of bar a) to close of bar b
    o=d[d.hour==a].groupby("date").Open.first(); c=d[d.hour==b].groupby("date").Close.last()
    r=(100*(c/o-1)).dropna(); r.index=pd.to_datetime(r.index,utc=True); r=r[r.index>=START]; r.name=name; return r
print("\n=== SESSION BLOCKS ===")
blocks={"Asia 00-07":blk(0,6,"asia"),"London 07-13":blk(7,12,"london"),"US 13-21":blk(13,20,"us"),"Early US 13-16":blk(13,15,"eus"),"Late 16-21":blk(16,20,"late"),"London open 07-09":blk(7,8,"lo"),"Pre-US 11-13":blk(11,12,"pre")}
for k,v in blocks.items(): print(fmt(stats(v, COST, f"Long {k} GMT")))
# ---------- INTRADAY MOMENTUM / REVERSAL ----------
print("\n=== INTRADAY MOMENTUM: sign of 00:00->X predicts X->21:00 ===")
for X in [3,6,7,8,10,12,13,14,15,16]:
    early=100*(sess[f"c{X}"]/sess.open-1); late=100*(sess.close/sess[f"c{X}"]-1)
    both=pd.DataFrame({"e":early,"l":late}).dropna()
    corr=both.e.corr(both.l)
    print(fmt(stats(np.sign(both.e)*both.l, COST, f"Follow 00->{X}:00 sign into {X}->21:00 (corr={corr:.3f})")))
    print(fmt(stats(-np.sign(both.e)*both.l, COST, f"  Fade 00->{X}:00 sign")))
    for thr in [0.3,0.5]:
        m=both.e.abs()>thr
        print(fmt(stats((np.sign(both.e)*both.l)[m], COST, f"  Follow |00->{X}|>{thr}%")))
# ---------- ASIAN RANGE BREAKOUT ----------
print("\n=== ASIAN RANGE (00:00-07:00 GMT) BREAKOUT, decided on 1h closes, exit 21:00 ===")
def range_breakout(start_h, end_h, decide_from, decide_to, exit_h=20, stop="mid", cost=COST):
    out=[]
    for dt,g in d.groupby("date"):
        g=g.sort_index()
        rng=g[(g.hour>=start_h)&(g.hour<=end_h)]
        if len(rng)<(end_h-start_h): continue
        hi,lo=rng.High.max(),rng.Low.min(); mid=(hi+lo)/2
        after=g[(g.hour>=decide_from)&(g.hour<=decide_to)]
        pos=0;entry=None;entry_hour=None
        for t,row in after.iterrows():
            if row.Close>hi: pos=1;entry=row.Close;entry_hour=row.hour;break
            if row.Close<lo: pos=-1;entry=row.Close;entry_hour=row.hour;break
        if pos==0: continue
        rest=g[(g.hour>entry_hour)&(g.hour<=exit_h)]
        if len(rest)==0: continue
        exitpx=rest.Close.iloc[-1]
        stop_px = mid if stop=="mid" else (lo if pos==1 else hi) if stop=="opp" else None
        r=None
        if stop_px is not None:
            if pos==1 and (rest.Low<=stop_px).any(): r=100*(stop_px/entry-1)
            if pos==-1 and (rest.High>=stop_px).any(): r=100*(entry/stop_px-1)
        if r is None: r=100*pos*(exitpx/entry-1)
        out.append((pd.Timestamp(dt,tz="UTC"),r,pos,entry_hour))
    o=pd.DataFrame(out,columns=["t","r","pos","eh"]).set_index("t")
    return o
for (a,b,c,e) in [(0,6,7,9),(0,6,7,12),(0,7,8,12),(0,6,7,15)]:
    for stop in ["mid","opp",None]:
        o=range_breakout(a,b,c,e,stop=stop); o=o[o.index>=START]
        print(fmt(stats(o.r, COST, f"Range {a:02d}-{b+1:02d} break during {c:02d}-{e+1:02d}, stop={stop}, exit 21:00")))
    o=range_breakout(a,b,c,e,stop="mid"); o=o[o.index>=START]
    print("   long/short split:", o.groupby("pos").r.agg(["count","mean"]).round(3).to_dict())
print("\n=== US-session range (13:00-15:00) breakout 15:00-18:00, exit 21:00 ===")
for stop in ["mid","opp",None]:
    o=range_breakout(13,14,15,18,stop=stop); o=o[o.index>=START]
    print(fmt(stats(o.r, COST, f"Range 13-15 break 15-19 stop={stop}")))
# ---------- HOURLY REVERSAL after big moves ----------
print("\n=== NEXT-HOUR after big 1h move (within session) ===")
dd=dd.copy(); dd["next"]=dd.groupby("date").ret.shift(-1); dd["absret"]=dd.ret.abs()
dd["sd"]=dd.ret.rolling(100).std().shift(1)
for k in [1.5,2,3]:
    m=(dd.absret>k*dd.sd)&dd.next.notna()
    x=dd[m]
    print(fmt(stats(-np.sign(x.ret)*x.next, COST, f"Fade next hour after |move|>{k} sd (n={m.sum()})")))
# ---------- EIA Wednesday / API ----------
print("\n=== WEDNESDAY (EIA 14:30/15:30 GMT) hourly means ===")
w=dd[dd.dow==2]; print(w.groupby("hour").ret.agg(["count","mean"]).round(3).T.to_string())
# ---------- Last hours ----------
print("\n=== Settlement/late hours ===")
for hh in [17,18,19,20]:
    x=dd[dd.hour==hh]; print(fmt(stats(x.ret, COST, f"Long {hh}:00-{hh+1}:00 bar")))
json.dump(res, open("brent_res.json","w"), default=float)
sess.to_csv("brent_sessions.csv")
