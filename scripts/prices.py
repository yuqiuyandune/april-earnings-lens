"""Fetch daily closes and volumes for every covered ticker, its peer ETF and QQQ.

Writes data/prices.json: {"updated": ISO time, "src": source, "t": {TICKER: [[date, close, volume], ...]}}
Only end-of-day data; the site derives everything else (zone status, post-earnings moves) in the browser.
Usage: python3 scripts/prices.py [--since 2026-06-01] [--probe]
"""
import argparse, csv, datetime as dt, io, json, pathlib, sys, time, urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "prices.json"
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"}


def get(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode()


def yahoo(t, since):
    p1 = int(dt.datetime.fromisoformat(since).replace(tzinfo=dt.timezone.utc).timestamp())
    p2 = int(time.time()) + 86400
    j = json.loads(get(f"https://query2.finance.yahoo.com/v8/finance/chart/{t}?period1={p1}&period2={p2}&interval=1d&events=split"))
    r = j["chart"]["result"][0]
    q = r["indicators"]["quote"][0]
    tz = r["meta"].get("gmtoffset", -14400)
    rows = []
    for ts, c, v in zip(r["timestamp"], q["close"], q["volume"]):
        if c is None:
            continue
        d = dt.datetime.fromtimestamp(ts + tz, dt.timezone.utc).date().isoformat()
        rows.append([d, round(c, 2), int(v or 0)])
    return rows


def stooq(t, since):
    txt = get(f"https://stooq.com/q/d/l/?s={t.lower()}.us&d1={since.replace('-', '')}&i=d")
    rows = []
    for r in csv.DictReader(io.StringIO(txt)):
        rows.append([r["Date"], round(float(r["Close"]), 2), int(float(r.get("Volume") or 0))])
    return rows


SOURCES = {"yahoo": yahoo, "stooq": stooq}


def tickers():
    idx = json.loads((ROOT / "data" / "index.json").read_text())
    ts = {"QQQ"}
    for c in idx["companies"]:
        ts.add(c["t"])
        co = json.loads((ROOT / "data" / "companies" / f"{c['t']}.json").read_text())
        peer = co.get("config", {}).get("peer")
        if peer:
            ts.add(peer["t"])
    return sorted(ts)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default="2026-06-01")
    ap.add_argument("--probe", action="store_true", help="only report which sources answer")
    a = ap.parse_args()
    if a.probe:
        for n, f in SOURCES.items():
            try:
                rows = f("NVDA", a.since)
                print(n, "OK", len(rows), rows[-2:])
            except Exception as e:
                print(n, "FAIL", repr(e)[:200])
        return
    out, used, bad = {}, {}, []
    for t in tickers():
        for n, f in SOURCES.items():
            try:
                rows = f(t, a.since)
                if len(rows) > 5:
                    out[t] = rows
                    used[n] = used.get(n, 0) + 1
                    break
            except Exception as e:
                print(t, n, "failed:", repr(e)[:160])
        else:
            bad.append(t)
        time.sleep(0.4)
    if bad:
        old = json.loads(OUT.read_text())["t"] if OUT.exists() else {}
        for t in bad:
            if t in old:
                out[t] = old[t]
        print("kept previous data for", bad)
    if not out:
        sys.exit("no prices fetched")
    last = max(r[-1][0] for r in out.values())
    doc = {"updated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="minutes"), "last": last,
           "src": "+".join(sorted(used)), "t": out}
    new = json.dumps(doc, separators=(",", ":"))
    if OUT.exists():
        prev = json.loads(OUT.read_text())
        if prev.get("t") == out:
            print("no change"); return
    OUT.write_text(new)
    print("wrote", len(out), "tickers, last", last, "via", used)


if __name__ == "__main__":
    main()
