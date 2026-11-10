"""Point-in-time quarterly fundamentals from SEC XBRL companyfacts, for the backtest.

For every period we keep the FIRST filed value and its filing date, so a backtest on day t only
sees numbers filed on or before t (no restatements, no look-ahead). Q4 is derived as the annual
value minus the first three quarters, dated by the 10-K filing.
Foreign filers (20-F, annual only) are skipped.
Usage: python3 bt/fund_fetch.py bt/data/meta.json bt/fund.json
"""
import json, sys, time, urllib.request, datetime as dt

UA = {"User-Agent": "EarningsLens research bot admin@example.com"}
CONCEPTS = {
    "rev": ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet",
            "RevenueFromContractWithCustomerIncludingAssessedTax", "SalesRevenueGoodsNet"],
    "ni": ["NetIncomeLoss"],
    "eps": ["EarningsPerShareDiluted", "EarningsPerShareBasicAndDiluted"],
    "ocf": ["NetCashProvidedByUsedInOperatingActivities"],
    "capex": ["PaymentsToAcquirePropertyPlantAndEquipment"],
}
CASHFLOW = {"ocf", "capex"}  # reported year-to-date in 10-Qs


def get(url):
    for k in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=90) as r:
                return json.loads(r.read())
        except Exception as e:
            if k == 2:
                raise
            time.sleep(2)


def days(a, b):
    return (dt.date.fromisoformat(b) - dt.date.fromisoformat(a)).days


def series(facts, names, ytd):
    """Return {period_end: (value, filed)} quarterly, first-filed values."""
    best = {}
    for nm in names:
        f = facts.get("us-gaap", {}).get(nm)
        if not f:
            continue
        units = f["units"].get("USD") or f["units"].get("USD/shares") or next(iter(f["units"].values()))
        for x in units:
            if x.get("form") not in ("10-Q", "10-K", "10-Q/A", "10-K/A") or "start" not in x:
                continue
            d = days(x["start"], x["end"])
            key = (x["start"], x["end"])
            if key not in best or x["filed"] < best[key][1]:
                best[key] = (x["val"], x["filed"], d)
    q = {}
    # plain quarters
    for (s, e), (v, filed, d) in best.items():
        if 80 <= d <= 100:
            q.setdefault(e, (v, filed))
    # year-to-date (cash flow) -> quarters by differencing within the same fiscal year start
    if ytd or True:
        by_start = {}
        for (s, e), (v, filed, d) in best.items():
            by_start.setdefault(s, []).append((e, v, filed, d))
        for s, lst in by_start.items():
            lst.sort()
            prev = None
            for e, v, filed, d in lst:
                if 80 <= d <= 100:
                    prev = (e, v, d); continue
                if prev and d > 120 and e not in q and abs(d - prev[2] - 91) <= 15:
                    q[e] = (v - prev[1], filed)
                if d > 120:
                    prev = (e, v, d)
    return dict(sorted(q.items()))


def main(meta_path, out_path):
    meta = json.load(open(meta_path))
    names = sorted(set(meta["ndx"]) | set(meta["covered"]))
    tick = get("https://www.sec.gov/files/company_tickers.json")
    cik = {v["ticker"]: v["cik_str"] for v in tick.values()}
    out = {}
    for t in names:
        c = cik.get(t) or cik.get(t.replace(".", "-"))
        if not c:
            print(t, "no cik"); continue
        try:
            j = get(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{c:010d}.json")
        except Exception as e:
            print(t, "failed", repr(e)[:80]); continue
        facts = j.get("facts", {})
        if "us-gaap" not in facts:
            print(t, "no us-gaap (foreign filer?)"); continue
        rec = {k: series(facts, v, k in CASHFLOW) for k, v in CONCEPTS.items()}
        out[t] = {k: [[e, v, f] for e, (v, f) in s.items()] for k, s in rec.items()}
        print(t, {k: len(v) for k, v in out[t].items()})
        time.sleep(0.15)
    json.dump(out, open(out_path, "w"), separators=(",", ":"))
    print("done", len(out))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
