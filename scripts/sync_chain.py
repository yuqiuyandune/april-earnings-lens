"""Copy the AI supply-chain classification from the Insider Flow repo into data/chain.json,
so the earnings home page groups companies exactly like the supply-chain page (april-insider-flow.com/).

Run when the chain's taxonomy changes or a new company is added to Earnings Lens:
  python3 scripts/sync_chain.py /path/to/-april-insider-flow
A company missing from the chain is listed and lands in an "other" group on the page; add it to
stack/company_master.csv in the Insider Flow repo (or to "extra" below) first.
"""
import csv, json, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
EXTRA = {}  # ticker: [layer id, segment id] for companies not on the chain page


def main(src):
    src = pathlib.Path(src)
    tax = json.loads((src / "stack" / "taxonomy.json").read_text(encoding="utf-8"))
    rows = {r["ticker"]: r for r in csv.DictReader(open(src / "stack" / "company_master.csv", encoding="utf-8-sig"))}
    energy = {r["ticker"] for r in csv.DictReader(open(src / "energy" / "company_master.csv", encoding="utf-8-sig"))}
    idx = json.loads((ROOT / "data" / "index.json").read_text(encoding="utf-8"))
    co, missing = {}, []
    for c in idx["companies"]:
        t = c["t"]
        if t in rows:
            co[t] = [int(rows[t]["层序号"]), int(rows[t]["环节序号"])]
        elif t in EXTRA:
            co[t] = EXTRA[t]
        else:
            missing.append(t)
            continue
        if t in energy:
            co[t].append(1)
    out = {"layers": [{"id": L["id"], "name": L["name"], "sub": L["sub"]} for L in tax["layers"]],
           "segments": [{"id": s["id"], "layer": s["layer"], "name": s["name"]} for s in tax["segments"]],
           "co": co}
    (ROOT / "data" / "chain.json").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print("companies", len(co), "missing", missing)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "../-april-insider-flow")
