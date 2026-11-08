"""Estimate-revision triggers for the companies we cover, from data/consensus.json.

A company triggers when its fiscal-year EPS consensus (next year first, else this year) moved
at least 3% in 7 days or 5% in 30 days. When its own report falls inside that window (or within 14 days)
the move is labelled post-earnings: the report explains it, and the page links there. Other triggers need a written
reason in data/alerts.json (and i18n/en/alerts.json, same list order).

The same rule runs in the page (index.html, revTrig); keep the two in step.
Usage: python3 scripts/revisions.py            all current triggers
       python3 scripts/revisions.py --pending  only those that still need a written reason
"""
import argparse, datetime as dt, json, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
T7, T30, POST_DAYS, COVER_DAYS = 0.03, 0.05, 14, 14


def chg(r, k):
    e, v = r.get("eps"), r.get(k)
    return None if not e or not v or e <= 0 or v <= 0 else e / v - 1


def trigger(rec):
    for h in ("ny", "fy"):
        r = next((x for x in rec.get("fy", []) if x.get("h") == h), None)
        if not r:
            continue
        c7, c30 = chg(r, "e7"), chg(r, "e30")
        if c7 is not None and abs(c7) >= T7:
            return {"h": h, "end": r["end"], "win": 7, "c": round(c7, 4)}
        if c30 is not None and abs(c30) >= T30:
            return {"h": h, "end": r["end"], "win": 30, "c": round(c30, 4)}
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pending", action="store_true")
    a = ap.parse_args()
    cn = json.loads((ROOT / "data" / "consensus.json").read_text())["t"]
    idx = json.loads((ROOT / "data" / "index.json").read_text(encoding="utf-8"))
    alerts = json.loads((ROOT / "data" / "alerts.json").read_text(encoding="utf-8"))["items"] if (ROOT / "data" / "alerts.json").exists() else []
    out = []
    for c in idx["companies"]:
        rec = cn.get(c["t"])
        if not rec:
            continue
        tr = trigger(rec)
        if not tr:
            continue
        on = dt.date.fromisoformat(rec["on"])
        ev = json.loads((ROOT / "data" / "reports" / c["t"] / f"{c['latest']}.json").read_text(encoding="utf-8")).get("event") or {}
        days = (on - dt.date.fromisoformat(ev["date"])).days if ev.get("date") else None
        tr.update(t=c["t"], on=rec["on"], report=ev.get("date"), post=days is not None and 0 <= days <= max(POST_DAYS, tr["win"] + 3))
        tr["covered"] = any(x["t"] == c["t"] and x.get("kind") == "est" and 0 <= (on - dt.date.fromisoformat(x["on"])).days <= COVER_DAYS for x in alerts)
        if a.pending and (tr["post"] or tr["covered"]):
            continue
        out.append(tr)
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
