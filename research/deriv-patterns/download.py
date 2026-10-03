import yfinance as yf, pandas as pd, warnings
warnings.filterwarnings("ignore")
def fix(d):
    if isinstance(d.columns, pd.MultiIndex):
        d.columns = d.columns.get_level_values(0)
    return d
tickers = {"BZ=F":"brent","TQQQ":"tqqq","SPXS":"spxs","SPXL":"spxl","QQQ":"qqq","SPY":"spy","BNO":"bno"}
for t,name in tickers.items():
    d = fix(yf.download(t, start="2024-01-01", interval="1d", progress=False, auto_adjust=False))
    d.to_csv(f"data/{name}_1d.csv"); print(name,"1d",len(d), d.index.min().date(), d.index.max().date())
for t,name in tickers.items():
    if name in ("bno","spy","qqq"): continue
    d = fix(yf.download(t, period="730d", interval="1h", progress=False, auto_adjust=False, prepost=False))
    d.to_csv(f"data/{name}_1h.csv"); print(name,"1h",len(d), d.index.min(), d.index.max())
for t,name in tickers.items():
    if name in ("bno","spy","qqq"): continue
    d = fix(yf.download(t, period="60d", interval="5m", progress=False, auto_adjust=False, prepost=True))
    d.to_csv(f"data/{name}_5m.csv"); print(name,"5m",len(d), d.index.min(), d.index.max())
    d = fix(yf.download(t, period="60d", interval="30m", progress=False, auto_adjust=False, prepost=False))
    d.to_csv(f"data/{name}_30m.csv"); print(name,"30m",len(d), d.index.min(), d.index.max())
