#!/usr/bin/env python3
"""Shareholder returns (buybacks and dividends) per quarter, from SEC XBRL company facts.

  python3 scripts/capital_return.py            # all companies in data/companies
  python3 scripts/capital_return.py ETN TLN    # only these
  python3 scripts/capital_return.py --cache DIR   # read/write companyfacts JSON in DIR (skips download when present)

Writes into data/companies/X.json -> series.metrics:
  bb    buybacks paid in the quarter (cash-flow statement, $B)
  dv    common dividends paid in the quarter ($B)
  dps   dividend per share declared in the quarter ($), when the company tags it
  fcfx  operating cash flow minus capital expenditure ($B), only for companies without a hand-entered "fcf" series,
        so the page can still compare buybacks + dividends with free cash flow

Cash-flow lines in 10-Qs are year-to-date; quarters are recovered by differencing YTD periods with the same start.
A quarter where the company reported operating cash flow but no buyback / dividend line counts as 0.
Quarter keys follow the site: the calendar quarter that holds the middle of the fiscal quarter.
IFRS filers (TSM) have no quarterly US-GAAP facts and are skipped.
"""
import datetime as dt, json, os, sys, time, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UA = "EarningsLens research bot admin@example.com"
TAGS = {
    "bb": ["PaymentsForRepurchaseOfCommonStock", "PaymentsForRepurchaseOfEquity"],
    "dv": ["PaymentsOfDividendsCommonStock", "PaymentsOfOrdinaryDividends", "PaymentsOfDividends"],
    "ocf": ["NetCashProvidedByUsedInOperatingActivities", "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations"],
    "dps": ["CommonStockDividendsPerShareDeclared", "CommonStockDividendsPerShareCashPaid"],
    "capex": ["PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsToAcquireProductiveAssets"],
}
TITLE = {"dps": ("每股股息（宣布）", "Dividend per share declared"), "bb": ("回购", "Buybacks"), "dv": ("股息", "Dividends"), "fcfx": ("自由现金流（经营现金流减资本开支）", "Free cash flow (operating cash flow minus capex)")}


def d(s):
    return dt.date.fromisoformat(s)


def qkey(start, end):
    mid = d(start) + (d(end) - d(start)) / 2
    return f"{mid.year}Q{(mid.month - 1) // 3 + 1}"


def quarters(facts):
    """{(start, end): value} of any duration -> {quarter key: value} for ~3-month periods."""
    out = {}
    by_start = {}
    for (s, e), v in facts.items():
        n = (d(e) - d(s)).days
        if 80 <= n <= 100:
            out[qkey(s, e)] = v
        by_start.setdefault(s, []).append((e, v))
    for s, lst in by_start.items():
        lst.sort()
        prev_e, prev_v = s, 0.0          # the period start itself = 0 so far
        prev_e = (d(s) - dt.timedelta(days=1)).isoformat()
        for e, v in lst:
            n = (d(e) - d(prev_e)).days
            if 80 <= n <= 100 and (d(e) - d(s)).days > 100:
                k = qkey((d(prev_e) + dt.timedelta(days=1)).isoformat(), e)
                out.setdefault(k, v - prev_v)
            prev_e, prev_v = e, v
    return out


def series(cf, names, unit="USD"):
    """Pool the tags (earlier names win for the same period; companies switch tags between filings), then
    split into quarters. Also returns the pooled facts, to tell "no payment" from "not broken out"."""
    gaap = cf.get("facts", {}).get("us-gaap", {})
    facts = {}
    for name in names:
        units = gaap.get(name, {}).get("units", {}).get(unit, [])
        mine = {}
        for x in sorted(units, key=lambda x: x.get("filed", "")):   # later filings (restatements) win
            if x.get("start") and x.get("form", "").startswith(("10-Q", "10-K")):
                mine[(x["start"], x["end"])] = x["val"]
        for k, v in mine.items():
            facts.setdefault(k, v)
    return quarters(facts), facts


def covered(facts, q):
    """True if some reported period containing quarter q shows a non-zero payment."""
    y, n = int(q[:4]), int(q[5])
    mid = dt.date(y, 3 * n - 1, 15)
    return any(v and d(s) <= mid <= d(e) for (s, e), v in facts.items())


def fetch(cik, cache):
    p = Path(cache) / f"CIK{cik:010d}.json" if cache else None
    if p and p.exists():
        return json.loads(p.read_text())
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"
    b = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=60).read()
    time.sleep(0.2)
    if p:
        p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(b)
    return json.loads(b)


def ciks(cache):
    p = Path(cache) / "company_tickers.json" if cache else None
    if p and p.exists():
        j = json.loads(p.read_text())
    else:
        j = json.loads(urllib.request.urlopen(urllib.request.Request("https://www.sec.gov/files/company_tickers.json",
                                                                     headers={"User-Agent": UA}), timeout=60).read())
        if p:
            p.parent.mkdir(parents=True, exist_ok=True); p.write_text(json.dumps(j))
    return {v["ticker"]: v["cik_str"] for v in j.values()}


def main():
    args = sys.argv[1:]
    cache = None
    if "--cache" in args:
        i = args.index("--cache"); cache = args[i + 1]; del args[i:i + 2]
    files = sorted((ROOT / "data" / "companies").glob("*.json"))
    if args:
        files = [f for f in files if f.stem in args]
    cmap = ciks(cache)
    for f in files:
        co = json.loads(f.read_text(encoding="utf-8"))
        t = co["t"]
        if t not in cmap:
            print(f"{t}: no CIK, skipped"); continue
        cf = fetch(cmap[t], cache)
        if "us-gaap" not in cf.get("facts", {}):
            print(f"{t}: no US-GAAP facts (IFRS filer), skipped"); continue
        S, F = {}, {}
        for k, v in TAGS.items():
            S[k], F[k] = series(cf, v, "USD/shares" if k == "dps" else "USD")
        qs = co["series"]["q"]
        M = co["series"]["metrics"]
        got = {}
        for k in ("bb", "dv"):
            vals = []
            for q in qs:
                v = S[k].get(q)
                if v is None and q in S["ocf"] and not covered(F[k], q):
                    v = 0.0                    # quarter is reported and no period covering it shows a payment
                vals.append(None if v is None else round(v / 1e9, 3))
            got[k] = vals
        dps = [S["dps"].get(q) for q in qs]
        if any(dps):
            got["dps"] = [None if v is None else round(v, 4) for v in dps]
        if "fcf" not in M:
            got["fcfx"] = [round((S["ocf"][q] - S["capex"].get(q, 0)) / 1e9, 3) if q in S["ocf"] else None for q in qs]
        for k, vals in got.items():
            if all(v is None for v in vals):
                M.pop(k, None); continue
            M[k] = {"t": TITLE[k][0], "u": "$" if k == "dps" else "$B", "dec": 2, "v": vals, "auto": "sec-xbrl"}
        f.write_text(json.dumps(co, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(t, {k: v for k, v in got.items()})
        en = ROOT / "i18n" / "en" / "companies" / f.name
        if en.exists():
            e = json.loads(en.read_text(encoding="utf-8"))
            em = e.setdefault("series", {}).setdefault("metrics", {})
            for k in got:
                if k in M:
                    em.setdefault(k, {})["t"] = TITLE[k][1]
                else:
                    em.pop(k, None)
            en.write_text(json.dumps(e, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
