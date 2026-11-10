"""Does more research help? Fundamental filters on top of the trend method, and a "good price"
buy-only method, using point-in-time SEC numbers (bt/fund.json, values dated by filing date).

Variants (fixed in advance):
  T0  trend baseline (brk50, score 65, stop 7%, exit 50-day, pyramid) on companies with SEC data
  F1  T0 + revenue growth: latest quarter revenue +15% y/y or more, and not decelerating
  F2  T0 + EPS growth: latest quarter diluted EPS +20% y/y or more (prior year positive)
  F3  T0 + price not stretched: price/sales in the lower 60% of its own last 3 years
  F4  T0 + F1 + F3
  V1  "good price" without the trend score: revenue +15% y/y, positive trailing free cash flow,
      price/sales in the lowest 30% of its own 3 years, buy when price closes back above the 20-day
      line; exit at a 15% trailing stop or when price/sales reaches the top 20% of its range
  V2  V1 but price/sales in the lowest 50%
Usage: python3 bt/fund_test.py bt/data bt/fund.json OUT_JSON
"""
import json, sys
import numpy as np
import pandas as pd

sys.path.insert(0, "bt")
import engine as E
import variants as V


def quarterly(rows):
    """[[end, val, filed], ...] -> DataFrame indexed by filed date with end and val."""
    if not rows:
        return None
    df = pd.DataFrame(rows, columns=["end", "val", "filed"])
    df["end"] = pd.to_datetime(df["end"]); df["filed"] = pd.to_datetime(df["filed"])
    return df.sort_values("end")


def features(D, fund):
    cal = D.cal
    cols = D.C.columns
    out = {k: pd.DataFrame(np.nan, index=cal, columns=cols) for k in ("rev_yoy", "rev_acc", "eps_yoy", "fcf_pos", "ps_pct")}
    for t in cols:
        f = fund.get(t)
        if not f:
            continue
        rv = quarterly(f["rev"])
        if rv is None or len(rv) < 6:
            continue
        rv = rv.set_index("end")
        # y/y growth per quarter, known from that quarter's filing date
        recs = []
        ends = list(rv.index)
        for k, e in enumerate(ends):
            prev = [x for x in ends if abs((e - x).days - 365) <= 20]
            if not prev or rv.loc[prev[0], "val"] <= 0:
                continue
            g = rv.loc[e, "val"] / rv.loc[prev[0], "val"] - 1
            recs.append((rv.loc[e, "filed"], e, g))
        if not recs:
            continue
        g = pd.DataFrame(recs, columns=["filed", "end", "g"]).sort_values("end")
        g["acc"] = g["g"].diff()
        g = g.sort_values("filed").drop_duplicates("filed", keep="last").set_index("filed")
        out["rev_yoy"][t] = g["g"].reindex(cal, method="ffill")
        out["rev_acc"][t] = g["acc"].reindex(cal, method="ffill")
        # trailing-twelve-month revenue known at each filing date
        ttm = rv["val"].rolling(4).sum()
        ttm_f = pd.Series(ttm.values, index=rv["filed"].values).dropna()
        ttm_f = ttm_f[~ttm_f.index.duplicated(keep="last")].sort_index()
        ttm_d = ttm_f.reindex(cal, method="ffill")
        ps = D.C[t] / ttm_d  # adjusted price / total revenue: share-count changes ignored, splits cancel
        out["ps_pct"][t] = ps.rolling(756, min_periods=252).apply(lambda a: (a[:-1] < a[-1]).mean() if not np.isnan(a[-1]) else np.nan, raw=True)
        ep = quarterly(f["eps"])
        if ep is not None and len(ep) >= 5:
            ep = ep.set_index("end")
            recs = []
            for e in ep.index:
                prev = [x for x in ep.index if abs((e - x).days - 365) <= 20]
                if prev and ep.loc[prev[0], "val"] > 0:
                    recs.append((ep.loc[e, "filed"], ep.loc[e, "val"] / ep.loc[prev[0], "val"] - 1))
            if recs:
                s = pd.DataFrame(recs, columns=["filed", "g"]).sort_values("filed").drop_duplicates("filed", keep="last").set_index("filed")["g"]
                out["eps_yoy"][t] = s.reindex(cal, method="ffill")
        oc, cx = quarterly(f["ocf"]), quarterly(f["capex"])
        if oc is not None and cx is not None and len(oc) >= 4:
            m = oc.set_index("end").join(cx.set_index("end"), lsuffix="_o", rsuffix="_c", how="left").fillna({"val_c": 0})
            m["fcf4"] = (m["val_o"] - m["val_c"]).rolling(4).sum()
            s = pd.Series((m["fcf4"] > 0).astype(float).values, index=m["filed_o"].values)
            s = s[m["fcf4"].notna().values]
            s = s[~s.index.duplicated(keep="last")].sort_index()
            out["fcf_pos"][t] = s.reindex(cal, method="ffill")
    return out


def make_value(FT, pct_max):
    def strat(D, B, i, st):
        out = []
        for t, p in B.pos.items():
            j = D.C.columns.get_loc(t)
            c = D.C.iat[i, j]
            if c < p["peak"] * 0.85 or FT["ps_pct"].iat[i, j] >= 0.8:
                out.append(("sell", t, {"why": "trail or rich"}))
        ok = (D.elig.iloc[i] & (FT["rev_yoy"].iloc[i] >= 0.15) & (FT["fcf_pos"].iloc[i] == 1)
              & (FT["ps_pct"].iloc[i] <= pct_max) & (D.C.iloc[i] > D.ma20.iloc[i]) & (D.C.iloc[i - 1] <= D.ma20.iloc[i - 1]))
        names = [t for t in ok[ok.fillna(False)].index if t not in B.pos]
        names.sort(key=lambda t: FT["ps_pct"].iat[i, FT["ps_pct"].columns.get_loc(t)])
        out += [("buy", t, {"stopd": 0.15, "tag": "value"}) for t in names[:3]]
        return out
    return strat


if __name__ == "__main__":
    V.init(sys.argv[1])
    D = V.D
    fund = json.load(open(sys.argv[2]))
    FT = features(D, fund)
    has = FT["rev_yoy"].notna()
    filt = {
        "T0": lambda i: has.iloc[i],
        "F1": lambda i: (FT["rev_yoy"].iloc[i] >= 0.15) & (FT["rev_acc"].iloc[i] >= 0),
        "F2": lambda i: FT["eps_yoy"].iloc[i] >= 0.20,
        "F3": lambda i: has.iloc[i] & (FT["ps_pct"].iloc[i] <= 0.6),
        "F4": lambda i: (FT["rev_yoy"].iloc[i] >= 0.15) & (FT["rev_acc"].iloc[i] >= 0) & (FT["ps_pct"].iloc[i] <= 0.6),
    }
    res = {"covered_names": int(has.any().sum()), "s": {}}
    for k, fn in filt.items():
        B = E.run(D, V.make_trend("brk50", 65, 0.07, "ma50", True, "none", fund=fn))
        res["s"][k] = E.stats([(d, v) for d, v, _ in B.curve], B.trades)
        print(k, {s: (round(res["s"][k][s]["cagr"], 3), round(res["s"][k][s]["maxdd"], 3), res["s"][k][s].get("n")) for s in ("all", "build", "test")})
    for k, pm in (("V1", 0.3), ("V2", 0.5)):
        B = E.run(D, make_value(FT, pm))
        res["s"][k] = E.stats([(d, v) for d, v, _ in B.curve], B.trades)
        print(k, {s: (round(res["s"][k][s]["cagr"], 3), round(res["s"][k][s]["maxdd"], 3), res["s"][k][s].get("n")) for s in ("all", "build", "test")})
    json.dump(res, open(sys.argv[3], "w"), default=str, indent=1)
