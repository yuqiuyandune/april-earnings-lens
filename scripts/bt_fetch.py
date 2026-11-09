"""Fetch daily OHLCV since 2015 for the backtest universe (Nasdaq-100 as of Feb 2026 + covered
companies + ETFs) and VIX / VIX3M from Cboe. Runs in GitHub Actions; the result is uploaded as a
workflow artifact (bt-data), not committed. Usage: python3 scripts/bt_fetch.py OUTDIR"""
import csv, gzip, json, pathlib, sys, time, urllib.request, datetime as dt

ROOT = pathlib.Path(__file__).resolve().parent.parent
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/126 Safari/537.36",
      "Accept": "application/json, text/plain, */*"}
NDX = ("ADBE ADP AMD ABNB ALNY GOOGL AMZN AEP AMGN ADI AAPL AMAT APP ARM ASML TEAM ADSK AXON BKR BKNG AVGO CDNS "
       "CHTR CTAS CSCO CCEP CTSH CMCSA CEG CPRT CSGP COST CRWD CSX DDOG DXCM FANG DASH EA EXC FAST FER FTNT GEHC GILD "
       "HON IDXX INSM INTC INTU ISRG KDP KLAC KHC LRCX LIN MAR MRVL MELI META MCHP MU MSFT MSTR MDLZ MPWR MNST NFLX "
       "NVDA NXPI ODFL ORLY PCAR PLTR PANW PAYX PYPL PDD PEP QCOM REGN ROP ROST STX SHOP SBUX SNPS TTWO TSLA TXN TRI "
       "TMUS VRSK VRTX WMT WBD WDC WDAY XEL ZS").split()
ETFS = ["QQQ", "SPY", "RSP", "TLT", "IEF", "SHY", "SMH"]


def get(url, timeout=40):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
        return r.read().decode()


def num(x):
    x = (x or "").replace("$", "").replace(",", "").strip()
    return float(x) if x not in ("", "N/A") else None


def nasdaq(t, kind):
    j = json.loads(get(f"https://api.nasdaq.com/api/quote/{t}/historical?assetclass={kind}&fromdate=2015-06-01&limit=9999"))
    out = []
    for r in j["data"]["tradesTable"]["rows"]:
        m, d, y = r["date"].split("/")
        out.append([f"{y}-{m}-{d}", num(r["open"]), num(r["high"]), num(r["low"]), num(r["close"]), int(num(r["volume"]) or 0)])
    return sorted(out)


def yahoo(t):
    p1 = int(dt.datetime(2015, 6, 1, tzinfo=dt.timezone.utc).timestamp()); p2 = int(time.time()) + 86400
    j = json.loads(get(f"https://query2.finance.yahoo.com/v8/finance/chart/{t}?period1={p1}&period2={p2}&interval=1d"))
    r = j["chart"]["result"][0]; q = r["indicators"]["quote"][0]
    out = []
    for i, ts in enumerate(r["timestamp"]):
        if q["close"][i] is None:
            continue
        d = dt.datetime.fromtimestamp(ts + r["meta"].get("gmtoffset", -14400), dt.timezone.utc).date().isoformat()
        out.append([d, q["open"][i], q["high"][i], q["low"][i], q["close"][i], int(q["volume"][i] or 0)])
    return out


def cboe(name):
    rows = list(csv.reader(get(f"https://cdn.cboe.com/api/global/us_indices/daily_prices/{name}_History.csv", 75).splitlines()))
    out = []
    for r in rows[1:]:
        try:
            m, d, y = r[0].split("/")
            out.append([f"{y}-{int(m):02d}-{int(d):02d}", float(r[1]), float(r[2]), float(r[3]), float(r[4]), 0])
        except Exception:
            pass
    return [x for x in out if x[0] >= "2015-06-01"]


def main(outdir):
    out = pathlib.Path(outdir); out.mkdir(parents=True, exist_ok=True)
    idx = json.loads((ROOT / "data" / "index.json").read_text())
    cov = [c["t"] for c in idx["companies"]]
    names = sorted(set(NDX) | set(cov))
    ok, bad = [], []
    for t in names + ETFS:
        rows, src = None, None
        for f, s in ((lambda: nasdaq(t, "etf" if t in ETFS else "stocks"), "nasdaq"), (lambda: yahoo(t), "yahoo")):
            try:
                rows = f(); src = s
                if rows:
                    break
            except Exception as e:
                print(t, s, "failed", repr(e)[:100])
        if rows:
            with gzip.open(out / f"{t}.csv.gz", "wt") as fh:
                w = csv.writer(fh); w.writerow(["date", "open", "high", "low", "close", "volume"]); w.writerows(rows)
            ok.append(t); print(t, src, len(rows), rows[0][0], rows[-1][0])
        else:
            bad.append(t)
        time.sleep(0.35)
    for v in ("VIX", "VIX3M"):
        try:
            rows = cboe(v)
            with gzip.open(out / f"^{v}.csv.gz", "wt") as fh:
                w = csv.writer(fh); w.writerow(["date", "open", "high", "low", "close", "volume"]); w.writerows(rows)
            print(v, len(rows))
        except Exception as e:
            print(v, "failed", repr(e)[:100])
    (out / "meta.json").write_text(json.dumps({"ndx": NDX, "covered": cov, "etfs": ETFS, "ok": ok, "bad": bad,
                                               "fetched": dt.datetime.utcnow().isoformat()}))
    print("ok", len(ok), "bad", bad)


if __name__ == "__main__":
    main(sys.argv[1])
