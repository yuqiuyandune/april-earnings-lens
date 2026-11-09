"""Private desk page data (april-insider-flow.com/earnings/desk/, unlisted): a daily screen of the
covered companies plus a small market-risk regime.

Inputs: data/prices.json (daily closes), data/hist.json (one year of closes, kept here),
data/market.json (indices, VIX, 10-year yield), data/consensus.json, data/reports (zones),
data/desk_groups.json (risk groups), data/chain.json (segments), and FRED's public CSV for the
high-yield credit spread.
Writes data/desk.json and refreshes data/hist.json.

Trend is a score, not a hard template: five parts, each 0..1, weighted to 0..100
  above 50-day line (25), moving-average alignment 50/150/200 (20), 200-day line rising (10),
  distance from the 52-week high (20), relative strength vs QQQ over 3 and 6 months, ranked (25).
Tiers only say which conditions hold; they are not buy or sell calls.
Usage: python3 scripts/desk.py [--fetch]   (--fetch backfills missing history from Nasdaq; Actions only)
"""
import argparse, datetime as dt, json, os, pathlib, sys, time, urllib.parse, urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
D = ROOT / "data"
HIST = D / "hist.json"
OUT = D / "desk.json"
TODAY = dt.date.today()
SCORE_OK, RR_OK, EST_OK, EST_BAD = 65, 1.5, -0.01, -0.03


def load(p, default=None):
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default


def ma(c, n, off=0):
    if len(c) < n + off:
        return None
    s = c[len(c) - n - off: len(c) - off]
    return sum(s) / n


def ret(c, n):
    return c[-1] / c[-1 - n] - 1 if len(c) > n else None


def clamp(x, lo=0.0, hi=1.0):
    return max(lo, min(hi, x))


def history(universe, fetch):
    hist = load(HIST, {})
    pr = load(D / "prices.json", {"t": {}})["t"]
    need = (TODAY - dt.timedelta(days=360)).isoformat()
    if fetch:
        sys.path.insert(0, str(ROOT / "scripts"))
        import prices
        since = (TODAY - dt.timedelta(days=420)).isoformat()
        for t in universe:
            rows = hist.get(t, [])
            if rows and rows[0][0] <= need:
                continue
            try:
                hist[t] = [[d, c] for d, c, _ in prices.nasdaq(t, since)]
                print(t, "backfilled", len(hist[t]))
            except Exception as e:
                print(t, "backfill failed:", repr(e)[:120])
            time.sleep(0.4)
    for t in universe:  # merge the daily file (it is the fresher source)
        m = {d: c for d, c in hist.get(t, [])}
        for d, c, _ in pr.get(t, []):
            m[d] = c
        if m:
            hist[t] = sorted([d, c] for d, c in m.items())[-320:]
    HIST.write_text(json.dumps(hist, separators=(",", ":")))
    return hist


def zone(t, idx):
    r = load(D / "reports" / t / f"{idx[t]['latest']}.json", {})
    z = (r.get("valuation") or {}).get("pricezone")
    if not z:
        return None
    return {"bear": z["scen"][0]["p"], "base": z["scen"][1]["p"], "bull": z["scen"][2]["p"],
            "lo": z["zone"][0], "hi": z["zone"][1], "status": z.get("status", "ok"), "on": z.get("on")}


def est(t, cn):
    c = (cn or {}).get(t)
    if not c:
        return None
    r = next((x for x in c.get("fy", []) if x.get("h") == "ny"), None) or next(iter(c.get("fy", [])), None)
    if not r:
        return None
    f = lambda k: (r["eps"] / r[k] - 1) if r.get("eps") and r.get(k) and r["eps"] > 0 and r[k] > 0 else None
    return {"fy": "FY" + r["end"][:4], "eps": r.get("eps"), "c30": f("e30"), "c90": f("e90"), "on": c.get("on")}


def fred_hy():
    """ICE BofA US high-yield spread from FRED's public CSV (no key needed); FRED_KEY is not required."""
    since = (TODAY - dt.timedelta(days=70)).isoformat()
    try:
        req = urllib.request.Request(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id=BAMLH0A0HYM2&cosd={since}",
                                     headers={"User-Agent": "EarningsLens research bot admin@example.com"})
        with urllib.request.urlopen(req, timeout=75) as r:
            lines = r.read().decode().strip().splitlines()[1:]
        v = [(d, float(x)) for d, x in (l.split(",") for l in lines) if x not in (".", "")]
        return {"on": v[-1][0], "now": v[-1][1], "m1": v[-1][1] - v[max(0, len(v) - 22)][1]}
    except Exception as e:
        print("FRED failed:", repr(e)[:120])
        return None


def regime(mk, rows):
    t = mk["t"]
    cl = lambda k: [c for _, c in t.get(k, [])]
    sig = []

    def add(k, label, val, score, note):
        sig.append({"k": k, "label": label, "val": val, "s": score, "note": note})

    for k, n in (("QQQ", "纳指 100"), ("SPY", "标普 500")):
        c = cl(k)
        if len(c) >= 50:
            d = c[-1] / ma(c, 50) - 1
            add(k, f"{n} 距 50 日线", d, 1 if d > 0.01 else -1 if d < -0.01 else 0, "站上为正")
    above = [r for r in rows if r.get("d50") is not None]
    if above:
        share = sum(1 for r in above if r["d50"] > 0) / len(above)
        add("breadth", "关注公司站上 50 日线的比例", share, 1 if share >= 0.6 else -1 if share <= 0.35 else 0, "小样本广度")
    s = cl("SPY")
    if len(s) >= 200:
        d = s[-1] / ma(s, 200) - 1
        add("spy200", "标普 500 距 200 日线", d, 1 if d > 0.03 else -1 if d < 0 else 0, "长期趋势")
    v = cl("VIX")
    if len(v) > 6:
        add("vix", "VIX", v[-1], 1 if v[-1] < 18 else -1 if v[-1] > 25 else 0, f"5 日前 {v[-6]:.1f}")
    y = cl("TNX")
    if len(y) > 22:
        d = y[-1] - y[-22]
        add("tnx", "10 年期美债 1 个月变化（百分点）", d, -1 if d > 0.25 else 1 if d < -0.15 else 0, f"现在 {y[-1]:.2f}%")
    hy = fred_hy()
    if hy:
        add("hy", "高收益债利差 1 个月变化（百分点）", hy["m1"], -1 if hy["m1"] > 0.5 else 1 if hy["m1"] < -0.2 else 0, f"现在 {hy['now']:.2f}%")
    tot = sum(x["s"] for x in sig)
    level = "进攻" if tot >= 2 else "防守" if tot <= -2 else "中性"
    return {"level": level, "score": tot, "of": len(sig), "signals": sig}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fetch", action="store_true")
    a = ap.parse_args()
    idx = {c["t"]: c for c in load(D / "index.json")["companies"]}
    groups = load(D / "desk_groups.json")
    chain = load(D / "chain.json", {"co": {}, "segments": []})
    seg = {s["id"]: s["name"]["zh"] for s in chain["segments"]}
    cn = (load(D / "consensus.json") or {}).get("t", {})
    mk = load(D / "market.json")
    universe = sorted(set(idx) | {"QQQ"})
    hist = history(universe, a.fetch)
    q = [c for _, c in hist.get("QQQ", [])] or [c for _, c in mk["t"]["QQQ"]]

    rows = []
    for t in sorted(idx):
        c = [x for _, x in hist.get(t, [])]
        if len(c) < 60:
            continue
        p = c[-1]
        m50, m150, m200, m200b = ma(c, 50), ma(c, 150), ma(c, 200), ma(c, 200, 21)
        hi, lo = max(c[-252:]), min(c[-252:])
        a50 = 1.0 if p > m50 else clamp(1 + (p / m50 - 1) / 0.10)
        checks = [p > m150 if m150 else None, (m50 > m150) if m150 else None,
                  (m150 > m200) if m200 else None, (p > m200) if m200 else None]
        checks = [x for x in checks if x is not None]
        align = sum(checks) / len(checks) if checks else (1.0 if p > m50 else 0.0)
        slope = (1.0 if m200 > m200b else 0.0) if m200 and m200b else (1.0 if m50 > ma(c, 50, 10) else 0.0)
        near = clamp((p / hi - 1 + 0.40) / 0.30)
        rs3 = (ret(c, 63) - ret(q, 63)) if ret(c, 63) is not None and ret(q, 63) is not None else None
        rs6 = (ret(c, 126) - ret(q, 126)) if ret(c, 126) is not None and ret(q, 126) is not None else None
        rs1 = (ret(c, 21) - ret(q, 21)) if ret(c, 21) is not None else None
        z, e = zone(t, idx), est(t, cn)
        up = z["base"] / p - 1 if z else None
        dn = z["bear"] / p - 1 if z else None
        rr = up / -dn if z and dn < 0 else (99.0 if z and up and up > 0 else None)
        where = None
        if z:
            where = ("低于悲观" if p < z["bear"] else "区间下方" if p < z["lo"] else "区间内" if p <= z["hi"]
                     else "区间上方" if p <= z["base"] else "高于基准")
        rows.append({"t": t, "n": idx[t]["n"], "seg": seg.get((chain["co"].get(t) or [0, 0])[1], idx[t].get("cat", "")),
                     "groups": groups["co"].get(t, []), "p": p, "d50": p / m50 - 1,
                     "ma20": round(ma(c, 20), 2), "ma50": round(m50, 2), "lo10": min(c[-10:]),
                     "d200": (p / m200 - 1) if m200 else None, "dhi": p / hi - 1, "dlo": p / lo - 1,
                     "rs1": rs1, "rs3": rs3, "rs6": rs6,
                     "parts": {"a50": a50, "align": align, "slope": slope, "near": near},
                     "est": e, "zone": z, "where": where, "up": up, "dn": dn, "rr": rr,
                     "short": len(c) < 200})
    # relative-strength rank across the universe, then the score
    rsv = [(r["t"], 0.6 * (r["rs3"] or 0) + 0.4 * (r["rs6"] if r["rs6"] is not None else (r["rs3"] or 0))) for r in rows]
    order = sorted(v for _, v in rsv)
    rank = {t: (order.index(v) / max(1, len(order) - 1)) for t, v in rsv}
    for r in rows:
        pr = r["parts"]
        pr["rs"] = rank[r["t"]]
        r["score"] = round(100 * (0.25 * pr["a50"] + 0.20 * pr["align"] + 0.10 * pr["slope"] + 0.20 * pr["near"] + 0.25 * pr["rs"]))
        e30 = (r["est"] or {}).get("c30")
        est_ok = e30 is None or e30 >= EST_OK
        val_ok = r["rr"] is not None and r["rr"] >= RR_OK and r["zone"]["status"] != "review"
        trend_ok = r["score"] >= SCORE_OK
        if (e30 is not None and e30 <= EST_BAD) or (e30 is not None and e30 < EST_OK and r["score"] < 35):
            tier = "avoid"  # estimates are being cut (with a weak trend, any cut counts)
        elif trend_ok and est_ok and val_ok:
            tier = "all"
        elif est_ok and val_ok:
            tier = "wait"   # fundamentals and valuation pass; waiting for the trend
        else:
            tier = "watch"
        r["tier"] = tier
        r["why"] = [k for k, ok in (("趋势", trend_ok), ("预期", est_ok), ("回报/风险", val_ok)) if not ok]

    prev = load(OUT, {}) or {}
    prev_tier = {r["t"]: r["tier"] for r in prev.get("rows", [])}
    last = max(d for d, _ in hist["QQQ"]) if hist.get("QQQ") else TODAY.isoformat()
    changes = [{"on": last, "t": r["t"], "from": prev_tier[r["t"]], "to": r["tier"]}
               for r in rows if r["t"] in prev_tier and prev_tier[r["t"]] != r["tier"] and prev.get("last") != last]
    log = (changes + [c for c in prev.get("log", []) if c["on"] != last])[:60] if prev.get("last") != last else prev.get("log", [])

    # bear-case exposure by group among the names that pass the fundamentals
    gx = {}
    for r in rows:
        if r["tier"] in ("all", "wait"):
            for g in r["groups"]:
                gx.setdefault(g, []).append(r["t"])

    doc = {"updated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="minutes"), "last": last,
           "rules": {"score": SCORE_OK, "rr": RR_OK, "est": EST_OK, "est_bad": EST_BAD},
           "regime": regime(mk, rows), "rows": rows, "log": log,
           "groups": {k: {**v, "names": gx.get(k, [])} for k, v in groups["groups"].items()}}
    OUT.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print("desk:", {k: sum(1 for r in rows if r["tier"] == k) for k in ("all", "wait", "watch", "avoid")},
          "regime", doc["regime"]["level"], doc["regime"]["score"])


if __name__ == "__main__":
    main()
