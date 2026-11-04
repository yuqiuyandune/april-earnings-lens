"""Fetch one year of daily closes for the Stock Atlas "Market watch" page (april-insider-flow.com/market/).

Writes data/market.json:
  {"updated": ISO time, "last": newest date, "src": {KEY: source}, "t": {KEY: [[date, close], ...]}}

Keys
  SPY RSP IWM QQQ                    broad market, equal weight, small caps, Nasdaq 100
  XLK XLC XLY XLP XLE XLF XLV XLI XLB XLRE XLU   the 11 S&P 500 sector ETFs
  TNX  US 10-year Treasury yield, in percent (4.95 = 4.95%)
  WTI  WTI crude oil, USD per barrel
  DXY  US dollar index
  VIX  CBOE volatility index

Each series tries several free sources in order and keeps the previous data if all fail, so one bad
day never blanks the page. Standard library only (runs in the daily prices workflow).
Usage: python3 scripts/market.py [--probe]
"""
import argparse, csv, datetime as dt, io, json, pathlib, sys, time, urllib.parse

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import prices
from prices import get, nasdaq, stooq  # same headers and parsers as the daily prices job

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "market.json"
ETFS = ["SPY", "RSP", "IWM", "QQQ", "XLK", "XLC", "XLY", "XLP", "XLE", "XLF", "XLV", "XLI", "XLB", "XLRE", "XLU"]
prices.ETFS.update(ETFS + ["USO", "UUP"])  # so the Nasdaq source asks for them as ETFs
# key -> (yahoo symbol, stooq symbol, FRED series)
MACRO = {"TNX": ("^TNX", "10usy.b", "DGS10"), "WTI": ("CL=F", "cl.f", "DCOILWTICO"),
         "DXY": ("DX-Y.NYB", "dx.f", None), "VIX": ("^VIX", "^vix", "VIXCLS")}


def yahoo(sym, since):
    p1 = int(dt.datetime.fromisoformat(since).replace(tzinfo=dt.timezone.utc).timestamp())
    p2 = int(time.time()) + 86400
    j = json.loads(get(f"https://query2.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(sym)}?period1={p1}&period2={p2}&interval=1d"))
    r = j["chart"]["result"][0]
    tz = r["meta"].get("gmtoffset", -14400)
    rows = []
    for ts, c in zip(r["timestamp"], r["indicators"]["quote"][0]["close"]):
        if c is None: continue
        rows.append([dt.datetime.fromtimestamp(ts + tz, dt.timezone.utc).date().isoformat(), round(c, 3)])
    return rows


def stooq_raw(sym, since):
    txt = get(f"https://stooq.com/q/d/l/?s={urllib.parse.quote(sym)}&d1={since.replace('-', '')}&i=d")
    if not txt.startswith("Date"): raise ValueError("stooq: " + txt[:100])
    return [[r["Date"], round(float(r["Close"]), 3)] for r in csv.DictReader(io.StringIO(txt))]


def get_slow(url, timeout=75):
    req = urllib.request.Request(url, headers=prices.UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def treasury_10y(since):
    """Daily 10-year par yield from the US Treasury's own CSV, one file per year."""
    rows = {}
    for y in range(int(since[:4]), dt.date.today().year + 1):
        txt = get_slow(f"https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/{y}/all"
                       f"?type=daily_treasury_yield_curve&field_tdr_date_value={y}&page&_format=csv")
        for r in csv.DictReader(io.StringIO(txt)):
            m, d, yy = r["Date"].split("/")
            if r.get("10 Yr"): rows[f"{yy}-{m}-{d}"] = round(float(r["10 Yr"]), 3)
    return [[k, v] for k, v in sorted(rows.items()) if k >= since]


def cboe_vix(since):
    txt = get_slow("https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv")
    out = []
    for r in csv.DictReader(io.StringIO(txt)):
        m, d, y = r["DATE"].split("/")
        k = f"{y}-{int(m):02d}-{int(d):02d}"
        if k >= since: out.append([k, round(float(r["CLOSE"]), 3)])
    return out


def nasdaq_any(sym, kind, since):
    j = json.loads(get(f"https://api.nasdaq.com/api/quote/{urllib.parse.quote(sym)}/historical?assetclass={kind}&fromdate={since}&limit=9999"))
    out = []
    for r in j["data"]["tradesTable"]["rows"]:
        m, d, y = r["date"].split("/")
        out.append([f"{y}-{m}-{d}", round(float(str(r["close"]).replace("$", "").replace(",", "")), 3)])
    return sorted(out)


def fred(series, since):
    txt = get_slow(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series}&cosd={since}")
    rows = []
    for r in csv.reader(io.StringIO(txt)):
        if len(r) == 2 and r[0][:2] == "20" and r[1] not in (".", ""):
            rows.append([r[0], round(float(r[1]), 3)])
    return rows


def sources(key, since):
    """Ordered (name, fetch) pairs. A name starting with "etf:" means the series is a tracking fund, not the index
    itself; the page then labels the card with the fund (UUP for the dollar, USO for oil)."""
    two = lambda rows: [[d, c] for d, c, *_ in rows]
    if key in MACRO:
        y, s, f = MACRO[key]
        out = {"TNX": [("treasury", lambda: treasury_10y(since))],
               "VIX": [("cboe", lambda: cboe_vix(since)), ("nasdaq", lambda: nasdaq_any("VIX", "index", since))],
               "WTI": [("nasdaq", lambda: nasdaq_any("CL:NMX", "commodities", since))],
               "DXY": [("nasdaq", lambda: nasdaq_any("DX:NYB", "commodities", since))]}[key]
        fund = {"WTI": "USO", "DXY": "UUP"}.get(key)
        if fund: out.append(("etf:" + fund, lambda: two(nasdaq(fund, since))))  # works from GitHub runners (Nov 2026 probe)
        out += [("yahoo", lambda: yahoo(y, since)), ("stooq", lambda: stooq_raw(s, since))]
        if f: out.append(("fred", lambda: fred(f, since)))
        return out
    two = lambda rows: [[d, c] for d, c, *_ in rows]
    return [("nasdaq", lambda: two(nasdaq(key, since))), ("yahoo", lambda: yahoo(key, since)), ("stooq", lambda: two(stooq(key, since)))]


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--probe", action="store_true"); a = ap.parse_args()
    since = (dt.date.today() - dt.timedelta(days=400)).isoformat()
    old = json.loads(OUT.read_text()) if OUT.exists() else {"t": {}, "src": {}}
    out, src, bad = {}, {}, []
    if a.probe:
        for key in list(MACRO):
            for name, fn in sources(key, since):
                try: rows = sorted(fn()); print("PROBE", key, name, "OK", len(rows), rows[-1:])
                except Exception as e: print("PROBE", key, name, "FAIL", repr(e)[:140])
                time.sleep(0.4)
        return
    for key in ETFS + list(MACRO):
        for name, fn in sources(key, since):
            try:
                rows = sorted(fn())
                if len(rows) > 150:
                    out[key], src[key] = rows, name
                    break
                print(key, name, "too few rows:", len(rows))
            except Exception as e:
                print(key, name, "failed:", repr(e)[:160])
        else:
            bad.append(key)
        time.sleep(0.4)
    print("ok:", {k: (src[k], len(out[k]), out[k][-1]) for k in out})
    if a.probe: return
    for k in bad:
        if k in old["t"]: out[k], src[k] = old["t"][k], old["src"].get(k, "previous")
    if bad: print("kept previous data for", bad)
    if not out: sys.exit("no market data fetched")
    if out == old.get("t"): print("no change"); return
    doc = {"updated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="minutes"),
           "last": max(r[-1][0] for r in out.values()), "src": src, "t": out}
    OUT.write_text(json.dumps(doc, separators=(",", ":")))
    print("wrote", len(out), "series, last", doc["last"])


if __name__ == "__main__":
    main()
