import pandas as pd, numpy as np, json
SPLIT = pd.Timestamp("2025-10-03", tz="UTC")   # in-sample before, out-of-sample after
START = pd.Timestamp("2024-10-03", tz="UTC")

def load(name, tf):
    d = pd.read_csv(f"data/{name}_{tf}.csv", index_col=0, parse_dates=True)
    d.index = pd.to_datetime(d.index, utc=True)
    d = d[["Open","High","Low","Close","Volume"]].dropna(subset=["Close"])
    return d

def stats(r, cost=0.0, label="", dates=None):
    """r: pd.Series of per-trade returns in % (index = datetime). cost in % per round trip."""
    r = pd.Series(r).dropna()
    if len(r)==0: return {"label":label,"n":0}
    net = r - cost
    def block(x):
        if len(x)==0: return dict(n=0)
        n=len(x); m=x.mean(); s=x.std(ddof=1) if n>1 else np.nan
        t = m/(s/np.sqrt(n)) if n>1 and s>0 else np.nan
        g=x[x>0].sum(); l=-x[x<0].sum()
        cum=x.cumsum(); dd=(cum-cum.cummax()).min()
        return dict(n=int(n), win=round(100*(x>0).mean(),1), mean=round(m,3), median=round(x.median(),3),
                    t=round(t,2) if t==t else None, pf=round(g/l,2) if l>0 else None, total=round(x.sum(),1), maxdd=round(dd,1))
    out = {"label":label, "cost":cost, "all":block(net)}
    idx = net.index
    if isinstance(idx, pd.DatetimeIndex):
        out["IS"] = block(net[idx<SPLIT]); out["OOS"] = block(net[idx>=SPLIT])
    return out

def fmt(st):
    if st.get("n")==0 or "all" not in st: return f"{st.get('label','')}: n=0"
    a=st["all"]; s=f"{st['label']:<60} n={a['n']:>4} win={a['win']:>5}% mean={a['mean']:>7}% t={a['t']} pf={a['pf']} tot={a['total']}% dd={a['maxdd']}%"
    if "IS" in st and st["IS"].get("n"):
        i=st["IS"]; o=st["OOS"]
        s+=f"\n{'':<62} IS n={i['n']} win={i['win']}% mean={i['mean']}% t={i['t']} | OOS n={o.get('n')} win={o.get('win')}% mean={o.get('mean')}% t={o.get('t')}"
    return s

def bucket_table(df, col, ret, edges, cost=0.0):
    rows=[]
    for lo,hi in zip(edges[:-1],edges[1:]):
        m=(df[col]>=lo)&(df[col]<hi)
        x=df.loc[m,ret]-cost
        if len(x)==0: continue
        rows.append(dict(bucket=f"[{lo},{hi})", n=len(x), win=round(100*(x>0).mean(),1), mean=round(x.mean(),3), median=round(x.median(),3),
                         t=round(x.mean()/(x.std()/np.sqrt(len(x))),2) if len(x)>2 and x.std()>0 else None))
    return pd.DataFrame(rows)
