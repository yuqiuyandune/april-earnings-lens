"""Pre-registered variant grids for each strategy family (fixed before any run; nothing added
after seeing results). Selection uses the build period only (2017-11..2021); the test period
(2022..) is reported for the selected ones and for the whole grid.
Usage: python3 bt/variants.py bt/data OUT_JSON [fund.json]
"""
import itertools, json, multiprocessing as mp, sys
import numpy as np
import pandas as pd

sys.path.insert(0, "bt")
import engine as E

D = None
F = None  # fundamentals panel (optional)


# ------------------------------------------------------------ helpers
def slow_regime(D):
    """Weekly reading of the daily regime; defensive only after two defensive weeks in a row."""
    wk = D.regime.copy()
    last_of_week = pd.Series(D.cal, index=D.cal).groupby(D.cal.to_period("W")).transform("max")
    out, prev_def, state = [], False, "neu"
    for d in D.cal:
        if d == last_of_week[d]:
            now_def = wk[d] == "def"
            state = "def" if (now_def and prev_def) else ("att" if wk[d] == "att" else ("neu" if not now_def else state if state == "def" else "neu"))
            prev_def = now_def
        out.append(state)
    return pd.Series(out, index=D.cal)


def make_trend(entry, smin, stopd, exit_, pyramid, regime, fund=None):
    brk = {"brk20": D.C.shift(1).rolling(20).max(), "brk50": D.brk50}.get(entry)
    rg = {"none": None, "fast": D.regime, "slow": SLOW}[regime]
    below20 = (D.C < D.ma20).rolling(5).max().shift(1).fillna(0) > 0

    def strat(D_, B, i, st):
        out = []
        r = rg.iat[i] if rg is not None else "att"
        prev = st.get("rg"); st["rg"] = r
        mult = E.MULT[r] if rg is not None else 1.0
        sold = set()
        for t, p in B.pos.items():
            j = D.C.columns.get_loc(t)
            c = D.C.iat[i, j]
            if np.isnan(c):
                continue
            ex = (c < D.ma20.iat[i, j]) if exit_ == "ma20" else (c < D.ma50.iat[i, j]) if exit_ == "ma50" else (c < p["peak"] * 0.85)
            if ex:
                out.append(("sell", t, {"why": exit_})); sold.add(t); continue
            if c >= p["entry"] * (1 + 2 * stopd) and p["stop"] < p["entry"]:
                p["stop"] = p["entry"]
            if pyramid and p["adds"] == 0 and c >= p["entry"] * 1.03 and D.score.iat[i, j] >= smin:
                out.append(("buy", t, {"stop": p["stop"], "mult": mult, "frac": 0.5, "tag": "add"}))
        if r == "def" and prev != "def" and rg is not None:
            out += [("sell", t, {"why": "regime", "frac": 0.5}) for t in B.pos if t not in sold]
        if r != "def":
            ok = (D.score.iloc[i] >= smin) & (D.C.iloc[i] > D.ma50.iloc[i]) & D.elig.iloc[i]
            if entry == "pull":
                ok &= below20.iloc[i] & (D.C.iloc[i] > D.ma20.iloc[i]) & (D.C.iloc[i] > D.C.iloc[i - 1])
            else:
                ok &= D.C.iloc[i] > brk.iloc[i]
            if fund is not None:
                ok &= fund(i)
            names = [t for t in ok[ok.fillna(False)].index if t not in B.pos]
            names.sort(key=lambda t: -D.rsrank.iat[i, D.rsrank.columns.get_loc(t)])
            out += [("buy", t, {"stopd": stopd, "mult": mult, "frac": 0.5 if pyramid else 1.0, "tag": "trend"}) for t in names[:3]]
        return out
    return strat


def make_rotation(lb, top, spyf, trail):
    if lb == "blend":
        rs = D.rs
    else:
        n = int(lb)
        rs = (D.C / D.C.shift(n) - 1).sub(D.qqq / D.qqq.shift(n) - 1, axis=0).where(D.elig)

    def strat(D_, B, i, st):
        out = []
        if trail:
            for t, p in B.pos.items():
                c = D.C.iat[i, D.C.columns.get_loc(t)]
                if c < p["peak"] * 0.85:
                    out.append(("sell", t, {"why": "trail"}))
        cal = D.cal
        if i + 1 >= len(cal) or cal[i + 1].month == cal[i].month:
            return out
        out = [("sell", t, {"why": "rebalance"}) for t in B.pos]
        if (not spyf) or D.spy.iat[i] > D.spy.iloc[i - 199: i + 1].mean():
            ok = D.elig.iloc[i] & (D.C.iloc[i] > D.ma50.iloc[i])
            pick = rs.iloc[i][ok.fillna(False)].dropna().sort_values(ascending=False).index[:top]
            out += [("buy", t, {"weight": 0.995 / top, "stop": 0, "tag": "rot"}) for t in pick]
        return out
    return strat


def make_dip(ddth, nlead, exit_):
    def strat(D_, B, i, st):
        q = D.qqq
        lo_i = max(0, i - 251)
        hi = q.iloc[lo_i: i + 1].max()
        out, ep = [], st.get("ep")
        if ep is None and q.iat[i] / hi - 1 <= -ddth:
            pk = int(np.argmax(q.iloc[lo_i: i + 1].values)) + lo_i
            ep = st["ep"] = {"peak": pk, "low": D.qqq_l.iat[i], "low_i": i, "done": set(), "start": i}
        if ep is not None:
            if D.qqq_l.iat[i] < ep["low"]:
                ep["low"], ep["low_i"] = D.qqq_l.iat[i], i
            vmax = D.vix.iloc[max(0, i - 9): i + 1].max()
            ratio = D.vix.iat[i] / D.vix3m.iat[i] if not np.isnan(D.vix3m.iat[i]) else 0.9
            sig = {"vix": D.vix.iat[i] < 0.8 * vmax and ratio < 1,
                   "ftd": (i - ep["low_i"] >= 3) and q.iat[i] / q.iat[i - 1] - 1 >= 0.0125 and D.qqq_v.iat[i] > D.qqq_v.iat[i - 1],
                   "ma50": q.iat[i] > q.iloc[i - 49: i + 1].mean()}
            fired = [k for k in ("vix", "ftd", "ma50") if sig[k] and k not in ep["done"]]
            if fired:
                pk = ep["peak"]
                rel = (D.C.iloc[i] / D.C.iloc[pk] - 1) - (q.iat[i] / q.iat[pk] - 1)
                ok = D.elig.iloc[i] & (D.C.iloc[i] > D.ma20.iloc[i])
                lead = rel[ok.fillna(False)].dropna().sort_values(ascending=False).index[:nlead]
                for k in fired:
                    ep["done"].add(k)
                    for t in lead:
                        j = D.C.columns.get_loc(t)
                        elow = D.L.iloc[ep["start"]: i + 1, j].min()
                        out.append(("buy", t, {"stop": max(elow * 0.99, D.C.iat[i, j] * 0.88), "frac": 1 / 3, "tag": "dip"}))
            if q.iat[i] >= hi or i - ep["start"] > 120 or len(ep["done"]) == 3:
                st["ep"] = None
        for t, p in B.pos.items():
            j = D.C.columns.get_loc(t)
            c = D.C.iat[i, j]
            held = (D.cal[i] - p["day"]).days
            if exit_ == "ma50" and held > 28 and c < D.ma50.iat[i, j]:
                out.append(("sell", t, {"why": "ma50"}))
            elif exit_ == "trail20" and c < p["peak"] * 0.80:
                out.append(("sell", t, {"why": "trail"}))
            elif c >= p["entry"] * 1.2 and p["stop"] < p["entry"]:
                p["stop"] = p["entry"]
        return out
    return strat


# ------------------------------------------------------------ grids (fixed in advance)
GRIDS = {
    "trend": [dict(entry=e, smin=s, stopd=sd, exit_=x, pyramid=py, regime="none")
              for e, s, sd, x, py in itertools.product(["brk20", "brk50", "pull"], [55, 65, 75], [0.05, 0.07, 0.10],
                                                       ["ma20", "ma50", "trail15"], [True, False])],
    "regime": [dict(entry="brk50", smin=65, stopd=0.07, exit_="ma50", pyramid=True, regime=r) for r in ("none", "fast", "slow")],
    "rotation": [dict(lb=lb, top=n, spyf=f, trail=tr)
                 for lb, n, f, tr in itertools.product(["63", "126", "252", "blend"], [3, 6, 10], [True, False], [True, False])],
    "dip": [dict(ddth=d, nlead=n, exit_=x) for d, n, x in itertools.product([0.06, 0.08, 0.12], [3, 6, 10], ["ma50", "trail20"])],
}
MAKE = {"trend": make_trend, "regime": make_trend, "rotation": make_rotation, "dip": make_dip}


def one(job):
    fam, k, params = job
    B = E.run(D, MAKE[fam](**params))
    st = E.stats([(d, v) for d, v, _ in B.curve], B.trades)
    keep = lambda s: {x: (None if v is None else float(v)) for x, v in s.items()} if s else None
    return {"fam": fam, "k": k, "params": params, "all": keep(st.get("all")), "build": keep(st.get("build")), "test": keep(st.get("test"))}


def init(datadir):
    global D, SLOW
    meta, px = E.load(datadir)
    D = E.Data(meta, px)
    SLOW = slow_regime(D)


if __name__ == "__main__":
    init(sys.argv[1])
    jobs = [(fam, k, p) for fam, ps in GRIDS.items() for k, p in enumerate(ps)]
    print("variants", len(jobs), {f: len(p) for f, p in GRIDS.items()})
    with mp.get_context("fork").Pool(min(8, mp.cpu_count())) as pool:
        res = pool.map(one, jobs, chunksize=2)
    json.dump(res, open(sys.argv[2], "w"), default=str)
    print("done")
