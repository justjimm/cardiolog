import pandas as pd, numpy as np, sys
from lib import *
name=sys.argv[1]; COST=float(sys.argv[2])
dd=load(name,"1d"); dd=dd[dd.index>=START-pd.Timedelta(days=40)]
dd["prev_close"]=dd.Close.shift(1); dd["gap"]=100*(dd.Open/dd.prev_close-1); dd["intra"]=100*(dd.Close/dd.Open-1); dd["cc"]=100*(dd.Close/dd.prev_close-1)
dd["dow"]=dd.index.dayofweek; dd["prev_date"]=pd.Series(dd.index,index=dd.index).shift(1); dd["gapdays"]=(dd.index-dd.prev_date).dt.days
dd["filled"]=((dd.gap>0)&(dd.Low<=dd.prev_close))|((dd.gap<0)&(dd.High>=dd.prev_close))
dd["atr"]=(100*(dd.High-dd.Low)/dd.Open).rolling(20).mean().shift(1)
dd["prev_cc"]=dd.cc.shift(1); dd["gapatr"]=dd.gap/dd.atr
dd=dd[dd.index>=START]
print(f"=== {name.upper()} daily n={len(dd)} {dd.index.min().date()}..{dd.index.max().date()} cost={COST}% ===")
print(f"gap: mean={dd.gap.mean():.3f}% |gap|={dd.gap.abs().mean():.3f}% up={100*(dd.gap>0).mean():.1f}% fill-same-day={100*dd.filled.mean():.1f}%  intra mean={dd.intra.mean():.3f}%  cc mean={dd.cc.mean():.3f}%")
print(fmt(stats(dd.gap, COST, "OVERNIGHT hold long (close->open), every night")))
print(fmt(stats(dd.intra, COST, "INTRADAY hold long (open->close), every day")))
print(fmt(stats(dd.gap[dd.gapdays>=3], COST, "WEEKEND hold long (Fri close->Mon open)")))
print(fmt(stats(dd.gap[dd.gapdays==1], COST, "Weeknight hold long (1-day gaps)")))
for dw,nm in enumerate("Mon Tue Wed Thu Fri".split()):
    print(fmt(stats(dd.gap[dd.dow==dw], COST, f"  overnight into {nm} open")))
    print(fmt(stats(dd.intra[dd.dow==dw], COST, f"  intraday {nm}")))
print("\n--- GAP FADE / FOLLOW (open->close) ---")
fade=-np.sign(dd.gap)*dd.intra; follow=-fade
print(fmt(stats(fade, COST, "Fade gap, exit close, all")))
print(fmt(stats(follow, COST, "Follow gap, exit close, all")))
print(bucket_table(dd.assign(fade=fade, gabs=dd.gap.abs()), "gabs","fade",[0,0.3,0.6,1,2,5,50], COST).to_string())
print("by gap/ATR:"); print(bucket_table(dd.assign(fade=fade, g=dd.gapatr.abs()), "g","fade",[0,0.1,0.25,0.5,1,10], COST).to_string())
print("Gap UP fade (short) by size:"); print(bucket_table(dd[dd.gap>0].assign(fade=fade), "gap","fade",[0,0.5,1,2,5,50], COST).to_string())
print("Gap DOWN fade (long) by size:"); print(bucket_table(dd[dd.gap<0].assign(fade=fade, g=-dd.gap), "g","fade",[0,0.5,1,2,5,50], COST).to_string())
print("fill rate by |gap| bucket:"); print(dd.groupby(pd.cut(dd.gap.abs(),[0,0.3,0.6,1,2,5,50])).filled.agg(["count","mean"]).round(3).to_string())
# fade to fill
def fade_fill(w):
    out={}
    for t,row in w.iterrows():
        s=-np.sign(row.gap)
        if s==0: continue
        out[t]=100*(row.prev_close/row.Open-1)*s if row.filled else 100*(row.Close/row.Open-1)*s
    return pd.Series(out)
print(fmt(stats(fade_fill(dd), COST, "Fade gap, target=fill else close, all")))
print(fmt(stats(fade_fill(dd[dd.gap.abs()>1]), COST, "Fade gap |gap|>1%, target=fill else close")))
print(fmt(stats(fade_fill(dd[dd.gap>1]), COST, "Fade gap UP >1% (short), target=fill")))
print(fmt(stats(fade_fill(dd[dd.gap<-1]), COST, "Fade gap DOWN >1% (long), target=fill")))
print(fmt(stats(fade_fill(dd[dd.gapdays>=3]), COST, "Fade WEEKEND gap, target=fill")))
print(fmt(stats(follow[dd.gap.abs()>2], COST, "Follow gap |gap|>2% exit close")))
print(fmt(stats(follow[dd.gap.abs()>3], COST, "Follow gap |gap|>3% exit close")))
# conditional on prior day
print(fmt(stats(dd.intra[(dd.prev_cc<-3)], COST, "Long intraday after prev day < -3%")))
print(fmt(stats(dd.intra[(dd.prev_cc>3)], COST, "Long intraday after prev day > +3%")))
print(fmt(stats(dd.gap[(dd.prev_cc<-3)], COST, "Overnight long after day < -3%")))
print(fmt(stats(dd.gap[(dd.prev_cc>3)], COST, "Overnight long after day > +3%")))
print(fmt(stats(dd.gap[(dd.intra<-2)], COST, "Overnight long after intraday < -2% (buy close)")))
print(fmt(stats(dd.gap[(dd.intra>2)], COST, "Overnight long after intraday > +2%")))
# ------------- HOURLY -------------
h=load(name,"1h"); h=h[h.index>=START]; h["ret"]=100*(h.Close/h.Open-1)
ny=h.index.tz_convert("America/New_York"); h["nh"]=ny.hour*60+ny.minute; h["date"]=ny.date; h["dow"]=h.index.dayofweek
lab={570:"09:30-10:30",630:"10:30-11:30",690:"11:30-12:30",750:"12:30-13:30",810:"13:30-14:30",870:"14:30-15:30",930:"15:30-16:00"}
g=h.groupby("nh").ret
tab=pd.DataFrame({"n":g.size(),"mean":g.mean().round(3),"win":(100*g.apply(lambda x:(x>0).mean())).round(1),"t":(g.mean()/(g.std()/np.sqrt(g.size()))).round(2),
                  "IS":h[h.index<SPLIT].groupby("nh").ret.mean().round(3),"OOS":h[h.index>=SPLIT].groupby("nh").ret.mean().round(3),"absmean":g.apply(lambda x:x.abs().mean()).round(3)})
tab.index=[lab.get(i,i) for i in tab.index]; print("\n--- HOURLY (New York time) ---"); print(tab.to_string())
print(h.pivot_table(index="nh",columns="dow",values="ret",aggfunc="mean").round(3).rename(index=lab).to_string())
# first hour momentum -> rest of day
fh=h[h.nh==570].groupby("date").agg(o=("Open","first"),c=("Close","last")); fh["r1"]=100*(fh.c/fh.o-1)
cl=h[h.nh==930].groupby("date").Close.last(); fh["close"]=cl; fh["rest"]=100*(fh.close/fh.c-1)
fh.index=pd.to_datetime(fh.index).tz_localize("UTC"); fh=fh.dropna()
print("\n--- FIRST HOUR -> REST OF DAY ---  corr", round(fh.r1.corr(fh.rest),3))
print(fmt(stats(np.sign(fh.r1)*fh.rest, COST, "Follow first-hour sign, exit close")))
print(fmt(stats(-np.sign(fh.r1)*fh.rest, COST, "Fade first-hour sign, exit close")))
for thr in [1,2,3]:
    m=fh.r1.abs()>thr
    print(fmt(stats((np.sign(fh.r1)*fh.rest)[m], COST, f"Follow first hour |r1|>{thr}%")))
# first-hour ORB: breakout of first hour high/low at hourly close, exit close
rows=[]
for dt,gg in h.groupby("date"):
    gg=gg.sort_index(); f=gg[gg.nh==570]
    if len(f)==0: continue
    hi,lo=f.High.iloc[0],f.Low.iloc[0]; after=gg[gg.nh>570]
    pos=0
    for t,b in after.iterrows():
        if b.Close>hi: pos=1;entry=b.Close;break
        if b.Close<lo: pos=-1;entry=b.Close;break
    if pos==0: continue
    rows.append((pd.Timestamp(dt).tz_localize("UTC"), pos*100*(gg.Close.iloc[-1]/entry-1)))
orb=pd.Series(dict(rows)); print(fmt(stats(orb, COST, "First-hour range breakout (1h close), exit close")))
# last-hour patterns: 15:30-16:00 after day up/down
lh=h[h.nh==930].copy(); lh["dayso"]=np.nan
op=h[h.nh==570].groupby("date").Open.first(); lh["dopen"]=lh.date.map(op); lh["day_to_1530"]=100*(lh.Open/lh.dopen-1)
print(fmt(stats(np.sign(lh.day_to_1530)*lh.ret, COST, "Last 30m: follow day direction")))
print(fmt(stats((np.sign(lh.day_to_1530)*lh.ret)[lh.day_to_1530.abs()>2], COST, "Last 30m: follow day direction when |day|>2%")))
print(fmt(stats((np.sign(lh.day_to_1530)*lh.ret)[lh.day_to_1530.abs()>4], COST, "Last 30m: follow day direction when |day|>4%")))
# buy at 15:30 hold to next open (overnight incl last 30 min)
nxt=dd.Open.shift(-1); lh2=lh.copy(); lh2["nopen"]=[nxt.get(pd.Timestamp(x).tz_localize("UTC"), np.nan) for x in lh2.date]
r=100*(lh2.nopen/lh2.Open-1); r.index=pd.DatetimeIndex(pd.to_datetime(lh2.date.values)).tz_localize("UTC")
print(fmt(stats(r, COST, "Buy 15:30 NY, sell next open (overnight incl. last 30m)")))
dd.to_csv(f"{name}_daily.csv")
