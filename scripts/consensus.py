"""Analyst consensus for every covered company: EPS estimate revisions, mean target price, rating counts.

Source: Alpha Vantage (EARNINGS_ESTIMATES + OVERVIEW). Needs the repo secret ALPHAVANTAGE_KEY.
The free key allows about 25 calls a day, so each run refreshes the companies with the oldest data
and keeps the rest from earlier runs. OVERVIEW (target price, ratings) is premium on the free key:
the script notices and goes on with estimates only.

Writes data/consensus.json:
  {"updated": ISO time, "src": "Alpha Vantage",
   "t": {TICKER: {"on": date,
                  "fy": [{"h": horizon, "end": period end, "eps": now, "e7", "e30", "e60", "e90",
                          "up7", "dn7", "up30", "dn30", "n": analysts, "rev": revenue estimate}, ...],
                  "tgt": mean target price, "rt": [strong buy, buy, hold, sell, strong sell],
                  "hist": [[date, tgt, this-year EPS, next-year EPS], ...]}}}
Only derived numbers reach the page (direction, % change, counts); the raw tables are not shown.
Usage: python3 scripts/consensus.py [--max 12] [--only VST,LITE] [--probe]
"""
import argparse, datetime as dt, json, os, pathlib, sys, time, urllib.parse, urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "consensus.json"
API = "https://www.alphavantage.co/query"
UA = {"User-Agent": "EarningsLens research bot admin@example.com", "Accept": "application/json"}
PAUSE = 13  # the free key also limits calls per minute


class Limit(Exception):
    pass


class Premium(Exception):
    pass


def call(fn, sym, key):
    q = urllib.parse.urlencode({"function": fn, "symbol": sym, "apikey": key})
    with urllib.request.urlopen(urllib.request.Request(f"{API}?{q}", headers=UA), timeout=40) as r:
        j = json.loads(r.read().decode())
    for k in ("Information", "Note", "Error Message"):
        if k in j:
            if "premium endpoint" in j[k]:
                raise Premium(fn)
            raise Limit(f"{fn} {sym}: {j[k][:160]}")
    return j


def num(x, f=float):
    try:
        return f(float(x)) if x not in (None, "", "None", "-") else None
    except (TypeError, ValueError):
        return None


def parse_est(j):
    """Keep the fiscal-year rows (current and next year); quarters are too noisy for the page."""
    out = []
    for r in j.get("estimates", []):
        h = (r.get("horizon") or "").lower()
        if "year" not in h:
            continue
        out.append({"end": r.get("date"),
                    "eps": num(r.get("eps_estimate_average")),
                    "e7": num(r.get("eps_estimate_average_7_days_ago")), "e30": num(r.get("eps_estimate_average_30_days_ago")),
                    "e60": num(r.get("eps_estimate_average_60_days_ago")), "e90": num(r.get("eps_estimate_average_90_days_ago")),
                    "up7": num(r.get("eps_estimate_revision_up_trailing_7_days"), int),
                    "dn7": num(r.get("eps_estimate_revision_down_trailing_7_days"), int),
                    "up30": num(r.get("eps_estimate_revision_up_trailing_30_days"), int),
                    "dn30": num(r.get("eps_estimate_revision_down_trailing_30_days"), int),
                    "n": num(r.get("eps_estimate_analyst_count"), int), "rev": num(r.get("revenue_estimate_average"))})
    out.sort(key=lambda r: r["end"] or "")
    out = out[:2]  # the two nearest fiscal years: this year and next
    for r, h in zip(out, ("fy", "ny")):
        r["h"] = h
    return out


def parse_ov(j):
    rt = [num(j.get(k), int) for k in ("AnalystRatingStrongBuy", "AnalystRatingBuy", "AnalystRatingHold",
                                       "AnalystRatingSell", "AnalystRatingStrongSell")]
    return num(j.get("AnalystTargetPrice")), (rt if any(v is not None for v in rt) else None)


def tickers():
    idx = json.loads((ROOT / "data" / "index.json").read_text(encoding="utf-8"))
    out = []
    for c in idx["companies"]:
        co = json.loads((ROOT / "data" / "companies" / f"{c['t']}.json").read_text(encoding="utf-8"))
        if not co.get("foreignIssuer"):  # TSM and other ADRs: estimates are in local currency or thin
            out.append(c["t"])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max", type=int, default=22, help="companies per run")
    ap.add_argument("--only", default="", help="comma-separated tickers to refresh first")
    ap.add_argument("--probe", action="store_true", help="print the raw answers for IBM with the public demo key")
    a = ap.parse_args()

    if a.probe:
        key = os.environ.get("ALPHAVANTAGE_KEY") or "demo"
        for fn in ("EARNINGS_ESTIMATES", "OVERVIEW"):
            try:
                j = call(fn, "IBM", key)
                print(fn, json.dumps(j)[:3000])
                if fn == "EARNINGS_ESTIMATES":
                    print("parsed", json.dumps(parse_est(j)))
                else:
                    print("parsed", parse_ov(j))
            except Exception as e:
                print(fn, "FAILED", e)
            time.sleep(2)
        return

    key = os.environ.get("ALPHAVANTAGE_KEY")
    if not key:
        print("ALPHAVANTAGE_KEY is not set; nothing to do")
        return
    db = json.loads(OUT.read_text()) if OUT.exists() else {"t": {}}
    db.setdefault("t", {})
    have = db["t"]
    first = [t.strip().upper() for t in a.only.split(",") if t.strip()]
    order = first + sorted((t for t in tickers() if t not in first), key=lambda t: have.get(t, {}).get("on", ""))
    today = dt.date.today().isoformat()
    done = 0
    ov_ok = os.environ.get("AV_OVERVIEW", "1") == "1"  # target price and ratings; premium on some keys
    budget = 24
    for t in order:
        if done >= a.max or budget < (2 if ov_ok else 1):
            break
        try:
            est = parse_est(call("EARNINGS_ESTIMATES", t, key)); budget -= 1; time.sleep(PAUSE)
            tgt, rt = have.get(t, {}).get("tgt"), have.get(t, {}).get("rt")
            if ov_ok:
                try:
                    tgt, rt = parse_ov(call("OVERVIEW", t, key))
                except Premium:
                    print("OVERVIEW is premium on this key: skipping target price and ratings")
                    ov_ok = False
                budget -= 1; time.sleep(PAUSE)
        except Limit as e:
            print("stopped:", e)
            break
        except Exception as e:
            print(t, "failed:", e)
            continue
        rec = have.get(t, {})
        hist = [h for h in rec.get("hist", []) if h[0] != today]
        fy = next((r["eps"] for r in est if r["h"] == "fy"), None)
        ny = next((r["eps"] for r in est if r["h"] == "ny"), None)
        hist.append([today, tgt, fy, ny])
        have[t] = {"on": today, "fy": est, "tgt": tgt, "rt": rt, "hist": hist[-80:]}
        done += 1
        print(t, "ok", tgt, [(r["h"], r["eps"], r["e90"]) for r in est])
    if done:
        db["updated"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
        db["src"] = "Alpha Vantage"
        OUT.write_text(json.dumps(db, separators=(",", ":")))
    print("refreshed", done, "of", len(order))


if __name__ == "__main__":
    sys.exit(main())
