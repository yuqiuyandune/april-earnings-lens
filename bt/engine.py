"""Backtest engine for the desk strategies.

Rules that apply to every strategy (so strategies differ only in what and when):
- Signals use data up to the close of day t; orders fill at the open of day t+1.
- A stop fills at the stop price, or at the open if the stock gaps below it.
- Cost: 0.10% of notional on every buy and every sell (commission + slippage).
- Sizing: risk 1% of equity per name at the initial stop, at most 20% of equity per name,
  never more than available cash (no leverage). Cash earns nothing.
- Universe: a stock is eligible from its 253rd trading day, if price >= $5 and its 50-day
  average dollar volume >= $20M.

Usage: python3 bt/engine.py DATA_DIR OUT_JSON
"""
import gzip, json, math, pathlib, sys
import numpy as np
import pandas as pd

COST = 0.001
RISK = 0.01
MAXPOS = 0.20
START = "2016-01-04"
SPLIT = "2022-01-01"


# ---------------------------------------------------------------- data
def load(dirpath):
    d = pathlib.Path(dirpath)
    meta = json.loads((d / "meta.json").read_text())
    px = {}
    for f in d.glob("*.csv.gz"):
        t = f.name[:-7]
        df = pd.read_csv(f, parse_dates=["date"]).dropna(subset=["close"]).drop_duplicates("date").set_index("date").sort_index()
        for c in ("open", "high", "low"):
            df[c] = df[c].fillna(df["close"])
        px[t] = df
    return meta, px


def panel(px, names, col):
    return pd.DataFrame({t: px[t][col] for t in names if t in px})


class Data:
    def __init__(self, meta, px):
        self.meta = meta
        stocks = sorted(set(meta["ndx"]) | set(meta["covered"]))
        stocks = [t for t in stocks if t in px]
        cal = px["SPY"].index
        cal = cal[cal >= "2015-06-01"]
        self.cal = cal
        P = lambda col: panel(px, stocks, col).reindex(cal)
        self.O, self.H, self.L, self.C, self.V = P("open"), P("high"), P("low"), P("close"), P("volume")
        self.stocks = stocks
        idx = lambda t, col="close": px[t][col].reindex(cal).ffill()
        self.qqq, self.spy, self.ief = idx("QQQ"), idx("SPY"), idx("IEF")
        self.qqq_v = px["QQQ"]["volume"].reindex(cal)
        self.qqq_l = idx("QQQ", "low")
        self.vix = idx("^VIX") if "^VIX" in px else None
        self.vix3m = idx("^VIX3M") if "^VIX3M" in px else None
        C = self.C
        self.ma20, self.ma50 = C.rolling(20).mean(), C.rolling(50).mean()
        self.ma150, self.ma200 = C.rolling(150).mean(), C.rolling(200).mean()
        self.ma200b = self.ma200.shift(21)
        self.hi252, self.lo252 = C.rolling(252).max(), C.rolling(252).min()
        self.brk50 = C.shift(1).rolling(50).max()
        n = C.notna().cumsum()
        dv = (C * self.V).rolling(50).mean()
        self.elig = (n >= 253) & (C >= 5) & (dv >= 2e7)
        r63, r126 = C / C.shift(63) - 1, C / C.shift(126) - 1
        q63, q126 = self.qqq / self.qqq.shift(63) - 1, self.qqq / self.qqq.shift(126) - 1
        rs = 0.6 * r63.sub(q63, axis=0) + 0.4 * r126.sub(q126, axis=0)
        self.rs = rs.where(self.elig)
        self.rsrank = self.rs.rank(axis=1, pct=True)
        a50 = ((C / self.ma50 - 1) / 0.10 + 1).clip(0, 1).where(C <= self.ma50, 1.0)
        align = ((C > self.ma150).astype(float) + (self.ma50 > self.ma150) + (self.ma150 > self.ma200) + (C > self.ma200)) / 4
        slope = (self.ma200 > self.ma200b).astype(float)
        near = ((C / self.hi252 - 1 + 0.40) / 0.30).clip(0, 1)
        self.score = 100 * (0.25 * a50 + 0.20 * align + 0.10 * slope + 0.20 * near + 0.25 * self.rsrank)
        # market regime, same signals as the desk where history exists (no credit spread history here)
        s = pd.Series(0, index=cal, dtype=float)
        for ser in (self.qqq, self.spy):
            d50 = ser / ser.rolling(50).mean() - 1
            s += np.where(d50 > 0.01, 1, np.where(d50 < -0.01, -1, 0))
        br = (C > self.ma50).where(self.elig).sum(axis=1) / self.elig.sum(axis=1)
        s += np.where(br >= 0.60, 1, np.where(br <= 0.35, -1, 0))
        d200 = self.spy / self.spy.rolling(200).mean() - 1
        s += np.where(d200 > 0.03, 1, np.where(d200 < 0, -1, 0))
        if self.vix is not None:
            s += np.where(self.vix < 18, 1, np.where(self.vix > 25, -1, 0))
        i21 = self.ief / self.ief.shift(21) - 1  # bond prices up = yields down
        s += np.where(i21 > 0.01, 1, np.where(i21 < -0.015, -1, 0))
        self.regime = pd.Series(np.where(s >= 2, "att", np.where(s <= -2, "def", "neu")), index=cal)
        self.breadth = br


# ---------------------------------------------------------------- portfolio
class Book:
    def __init__(self, cash=100_000.0):
        self.cash, self.pos, self.trades, self.curve = cash, {}, [], []

    def value(self, C, i):
        v = self.cash
        for t, p in self.pos.items():
            c = C.iat[i, C.columns.get_loc(t)]
            v += p["sh"] * (c if not math.isnan(c) else p["last"])
        return v

    def buy(self, t, sh, price, day, stop, tag=""):
        sh = int(sh)
        if sh <= 0:
            return
        cost = sh * price * (1 + COST)
        if cost > self.cash:
            sh = int(self.cash / (price * (1 + COST)))
            if sh <= 0:
                return
            cost = sh * price * (1 + COST)
        self.cash -= cost
        if t in self.pos:
            p = self.pos[t]
            p["cost"] += cost; p["sh"] += sh; p["adds"] += 1
        else:
            self.pos[t] = {"sh": sh, "cost": cost, "entry": price, "day": day, "stop": stop, "risk": price - stop,
                           "adds": 0, "tag": tag, "last": price, "peak": price}

    def sell(self, t, price, day, why, frac=1.0):
        p = self.pos[t]
        sh = p["sh"] if frac >= 1 else int(p["sh"] * frac)
        if sh <= 0:
            return
        got = sh * price * (1 - COST)
        self.cash += got
        part_cost = p["cost"] * sh / p["sh"]
        r_mult = (got - part_cost) / (sh * p["risk"]) if p["risk"] > 0 else None
        self.trades.append({"t": t, "in": str(p["day"].date()), "out": str(day.date()), "pnl": got - part_cost,
                            "ret": got / part_cost - 1, "R": r_mult, "why": why, "tag": p["tag"]})
        p["cost"] -= part_cost; p["sh"] -= sh
        if p["sh"] <= 0:
            del self.pos[t]


def run(D, strat, start=START):
    cal = D.cal
    i0 = cal.searchsorted(pd.Timestamp(start))
    B = Book()
    col = {t: k for k, t in enumerate(D.stocks)}
    O, H, L, C = D.O.values, D.H.values, D.L.values, D.C.values
    orders = []  # (kind, t, args) to fill at next open
    state = {}
    for i in range(i0, len(cal)):
        day = cal[i]
        # 1) fill orders from yesterday's close at today's open
        for kind, t, a in orders:
            j = col.get(t)
            o = O[i, j] if j is not None else np.nan
            if np.isnan(o):
                continue
            if kind == "sell" and t in B.pos:
                B.sell(t, o, day, a.get("why", ""), a.get("frac", 1.0))
            elif kind == "buy":
                stop = o * (1 - a["stopd"]) if "stopd" in a else a["stop"]
                if stop >= o:
                    stop = o * 0.93
                eq = B.value(D.C, i - 1)
                risk_cash = eq * RISK * a.get("mult", 1.0) * a.get("frac", 1.0)
                sh = min(risk_cash / (o - stop), eq * MAXPOS * a.get("frac", 1.0) / o)
                if a.get("weight"):
                    sh = eq * a["weight"] / o
                B.buy(t, sh, o, day, stop, a.get("tag", ""))
        orders = []
        # 2) intraday stops
        for t in list(B.pos):
            j = col[t]; p = B.pos[t]
            lo, op = L[i, j], O[i, j]
            if not np.isnan(lo) and p["stop"] and lo <= p["stop"]:
                B.sell(t, min(op, p["stop"]) if not np.isnan(op) else p["stop"], day, "stop")
        for t, p in B.pos.items():
            c = C[i, col[t]]
            if not np.isnan(c):
                p["last"] = c; p["peak"] = max(p["peak"], c)
        # 3) strategy decides at the close
        orders = strat(D, B, i, state)
        B.curve.append((day, B.value(D.C, i), sum(1 for _ in B.pos)))
    return B


# ---------------------------------------------------------------- strategies
def cand(D, i, cond):
    row = cond.iloc[i]
    return list(row[row.fillna(False)].index)


def trend_entries(D, B, i, mult=1.0, maxnew=3):
    ok = (D.score.iloc[i] >= 65) & (D.C.iloc[i] > D.brk50.iloc[i]) & (D.C.iloc[i] > D.ma50.iloc[i]) & D.elig.iloc[i]
    names = [t for t in ok[ok.fillna(False)].index if t not in B.pos]
    names.sort(key=lambda t: -D.rsrank.iat[i, D.rsrank.columns.get_loc(t)])
    return [("buy", t, {"stopd": 0.07, "mult": mult, "frac": 0.5, "tag": "trend"}) for t in names[:maxnew]]


def trend_manage(D, B, i, mult=1.0):
    out = []
    for t, p in B.pos.items():
        j = D.C.columns.get_loc(t)
        c, m50 = D.C.iat[i, j], D.ma50.iat[i, j]
        if np.isnan(c):
            continue
        if c < m50:
            out.append(("sell", t, {"why": "below 50-day"}))
            continue
        if p["entry"] and c >= p["entry"] * (1 + 2 * 0.07) and p["stop"] < p["entry"]:
            p["stop"] = p["entry"]  # 2R: stop to breakeven
        if p["adds"] == 0 and c >= p["entry"] * 1.03 and D.score.iat[i, j] >= 65:
            out.append(("buy", t, {"stop": p["stop"], "mult": mult, "frac": 0.5, "tag": "trend-add"}))
    return out


def s1_trend(D, B, i, st):
    return trend_manage(D, B, i) + trend_entries(D, B, i)


MULT = {"att": 1.0, "neu": 0.75, "def": 0.5}


def s2_trend_regime(D, B, i, st):
    rg, prev = D.regime.iat[i], st.get("rg")
    st["rg"] = rg
    out = trend_manage(D, B, i, MULT[rg])
    if rg == "def" and prev != "def":
        out += [("sell", t, {"why": "regime to defensive", "frac": 0.5}) for t in B.pos if t not in {o[1] for o in out}]
    if rg != "def":
        out += trend_entries(D, B, i, MULT[rg])
    return out


def s3_dip(D, B, i, st):
    q = D.qqq
    hi = q.iloc[max(0, i - 251): i + 1].max()
    dd = q.iat[i] / hi - 1
    out = []
    ep = st.get("ep")
    if ep is None and dd <= -0.08:
        peak_i = int(np.argmax(q.iloc[max(0, i - 251): i + 1].values)) + max(0, i - 251)
        ep = st["ep"] = {"peak": peak_i, "low": D.qqq_l.iat[i], "low_i": i, "done": set(), "start": i}
    if ep is not None:
        if D.qqq_l.iat[i] < ep["low"]:
            ep["low"], ep["low_i"] = D.qqq_l.iat[i], i
        sig = {}
        if D.vix is not None:
            vmax = D.vix.iloc[max(0, i - 9): i + 1].max()
            ratio = D.vix.iat[i] / D.vix3m.iat[i] if D.vix3m is not None and not np.isnan(D.vix3m.iat[i]) else 0.9
            sig["vix"] = D.vix.iat[i] < 0.8 * vmax and ratio < 1
        r1 = q.iat[i] / q.iat[i - 1] - 1
        sig["ftd"] = (i - ep["low_i"] >= 3) and r1 >= 0.0125 and D.qqq_v.iat[i] > D.qqq_v.iat[i - 1]
        sig["ma50"] = q.iat[i] > q.iloc[i - 49: i + 1].mean()
        fired = [k for k in ("vix", "ftd", "ma50") if sig.get(k) and k not in ep["done"]]
        if fired:
            # leaders: best relative performance since the index peak, eligible, above the 20-day line
            pk = ep["peak"]
            rel = (D.C.iloc[i] / D.C.iloc[pk] - 1) - (q.iat[i] / q.iat[pk] - 1)
            ok = D.elig.iloc[i] & (D.C.iloc[i] > D.ma20.iloc[i])
            lead = rel[ok.fillna(False)].dropna().sort_values(ascending=False).index[:6]
            for k in fired:
                ep["done"].add(k)
                for t in lead:
                    j = D.C.columns.get_loc(t)
                    elow = D.L.iloc[ep["start"]: i + 1, j].min()
                    stop = max(elow * 0.99, D.C.iat[i, j] * 0.88)
                    out.append(("buy", t, {"stop": stop, "frac": 1 / 3, "tag": "dip-" + k}))
        if q.iat[i] >= hi or i - ep["start"] > 120 or len(ep["done"]) == 3:
            st["ep"] = None
    for t, p in B.pos.items():
        j = D.C.columns.get_loc(t)
        c = D.C.iat[i, j]
        held = (D.cal[i] - p["day"]).days
        if held > 28 and c < D.ma50.iat[i, j]:
            out.append(("sell", t, {"why": "below 50-day"}))
        elif c >= p["entry"] * 1.2 and p["stop"] < p["entry"]:
            p["stop"] = p["entry"]
    return out


def s4_rotation(D, B, i, st):
    cal = D.cal
    if i + 1 >= len(cal) or cal[i + 1].month == cal[i].month:
        return []
    out = [("sell", t, {"why": "monthly rebalance"}) for t in B.pos]
    if D.spy.iat[i] > D.spy.iloc[i - 199: i + 1].mean():
        ok = D.elig.iloc[i] & (D.C.iloc[i] > D.ma50.iloc[i])
        top = D.rs.iloc[i][ok.fillna(False)].dropna().sort_values(ascending=False).index[:6]
        # sells fill first at the same open, so buy with weight of equity
        out += [("buy", t, {"weight": 0.995 / 6, "stop": 0, "tag": "rotation"}) for t in top]
    return out


def rsi2(C):
    d = C.diff()
    up, dn = d.clip(lower=0), -d.clip(upper=0)
    rs = up.ewm(alpha=0.5, adjust=False).mean() / dn.ewm(alpha=0.5, adjust=False).mean()
    return 100 - 100 / (1 + rs)


def s5_meanrev(D, B, i, st):
    if "rsi" not in st:
        st["rsi"] = rsi2(D.C)
    R, out = st["rsi"], []
    for t, p in B.pos.items():
        j = D.C.columns.get_loc(t)
        c = D.C.iat[i, j]
        if c > D.C.iloc[i - 4: i + 1, j].mean() or (D.cal[i] - p["day"]).days > 14:
            out.append(("sell", t, {"why": "bounce or time"}))
    if len(B.pos) < 10:
        ok = D.elig.iloc[i] & (D.C.iloc[i] > D.ma200.iloc[i]) & (R.iloc[i] < 10)
        names = [t for t in ok[ok.fillna(False)].index if t not in B.pos]
        names.sort(key=lambda t: R.iat[i, R.columns.get_loc(t)])
        out += [("buy", t, {"weight": 0.10, "stop": 0, "tag": "meanrev"}) for t in names[: 10 - len(B.pos)]]
        for o in out:
            if o[0] == "buy":
                o[2]["stop"] = None
    return out


def bench_qqq(D, start=START):
    s = D.qqq[D.qqq.index >= start]
    return list(zip(s.index, (s / s.iloc[0] * 100_000).values))


def bench_ew(D, start=START):
    """Equal weight of the eligible universe, rebalanced monthly (buy-and-hold of the same pool)."""
    cal = D.cal; i0 = cal.searchsorted(pd.Timestamp(start))
    rets = D.C.pct_change()
    v, out, w = 100_000.0, [], None
    for i in range(i0, len(cal)):
        if w is not None:
            r = rets.iloc[i][w].fillna(0).mean()
            v *= 1 + r
        if w is None or (i + 1 < len(cal) and cal[i + 1].month != cal[i].month):
            w = list(D.elig.iloc[i][D.elig.iloc[i].fillna(False)].index)
        out.append((cal[i], v))
    return out


# ---------------------------------------------------------------- metrics
def stats(curve, trades=None, exposure=None):
    s = pd.Series([v for _, v in curve], index=[d for d, _ in curve])
    out = {}
    for name, part in (("all", s), ("build", s[s.index < SPLIT]), ("test", s[s.index >= SPLIT])):
        if len(part) < 30:
            continue
        yrs = (part.index[-1] - part.index[0]).days / 365.25
        cagr = (part.iloc[-1] / part.iloc[0]) ** (1 / yrs) - 1
        dd = (part / part.cummax() - 1).min()
        r = part.pct_change().dropna()
        m = part.resample("ME").last().pct_change().dropna()
        qtr = part.resample("QE").last().pct_change().dropna()
        out[name] = {"cagr": cagr, "maxdd": dd, "mar": cagr / -dd if dd < 0 else None,
                     "sharpe": r.mean() / r.std() * math.sqrt(252) if r.std() > 0 else None,
                     "worst_m": m.min(), "worst_q": qtr.min(), "total": part.iloc[-1] / part.iloc[0] - 1}
    if trades is not None:
        tr = pd.DataFrame(trades)
        if len(tr):
            for name, part in (("all", tr), ("build", tr[tr["in"] < SPLIT]), ("test", tr[tr["in"] >= SPLIT])):
                if not len(part) or name not in out:
                    continue
                w, l = part[part.pnl > 0], part[part.pnl <= 0]
                out[name].update({"n": len(part), "win": len(w) / len(part),
                                  "avg_win": w.ret.mean() if len(w) else 0, "avg_loss": l.ret.mean() if len(l) else 0,
                                  "pf": w.pnl.sum() / -l.pnl.sum() if l.pnl.sum() < 0 else None,
                                  "avgR": part.R.dropna().mean() if part.R.notna().any() else None})
    if exposure is not None:
        out["exposure"] = exposure
    return out


def main(datadir, outpath):
    meta, px = load(datadir)
    D = Data(meta, px)
    res = {"universe": len(D.stocks), "start": START, "split": SPLIT, "end": str(D.cal[-1].date()), "s": {}}
    res["s"]["S0a"] = {"name": "买入持有 QQQ", **stats(bench_qqq(D))}
    res["s"]["S0b"] = {"name": "同一池子等权、每月再平衡", **stats(bench_ew(D))}
    curves = {"S0a": bench_qqq(D), "S0b": bench_ew(D)}
    for key, name, f in (("S1", "纯趋势", s1_trend), ("S2", "趋势 + 市场档位", s2_trend_regime),
                         ("S3", "大跌后分批买", s3_dip), ("S4", "相对强度月度轮动", s4_rotation),
                         ("S5", "抄底反弹（对照）", s5_meanrev)):
        B = run(D, f)
        expo = float(np.mean([1 if n else 0 for _, _, n in B.curve]))
        res["s"][key] = {"name": name, **stats([(d, v) for d, v, _ in B.curve], B.trades, expo)}
        curves[key] = [(d, v) for d, v, _ in B.curve]
        res["s"][key]["trades_sample"] = B.trades[-8:]
        print(key, name, json.dumps({k: (round(v, 3) if isinstance(v, float) else v) for k, v in res["s"][key]["all"].items()}))
    # monthly equity for charts
    res["monthly"] = {k: [[str(d.date()), round(v)] for d, v in pd.Series(dict(c)).resample("ME").last().items()] for k, c in curves.items()}
    pathlib.Path(outpath).write_text(json.dumps(res, ensure_ascii=False, default=str, indent=1))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
