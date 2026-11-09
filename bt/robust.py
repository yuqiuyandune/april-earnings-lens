"""Survivorship check: rerun every strategy without the N biggest winners of the whole period."""
import json, sys
sys.path.insert(0, "bt")
import engine as E

meta, px = E.load(sys.argv[1])
N = int(sys.argv[3]) if len(sys.argv) > 3 else 10
D0 = E.Data(meta, px)
tot = (D0.C.iloc[-1] / D0.C.apply(lambda s: s.dropna().iloc[0]) - 1).sort_values(ascending=False)
drop = list(tot.index[:N])
meta2 = dict(meta, ndx=[t for t in meta["ndx"] if t not in drop], covered=[t for t in meta["covered"] if t not in drop])
D = E.Data(meta2, px)
out = {"dropped": drop, "s": {}}
out["s"]["S0a"] = E.stats(E.bench_qqq(D)); out["s"]["S0b"] = E.stats(E.bench_ew(D))
for k, f in (("S1", E.s1_trend), ("S2", E.s2_trend_regime), ("S3", E.s3_dip), ("S4", E.s4_rotation), ("S5", E.s5_meanrev)):
    B = E.run(D, f)
    out["s"][k] = E.stats([(d, v) for d, v, _ in B.curve], B.trades)
json.dump(out, open(sys.argv[2], "w"), default=str, indent=1)
for k, v in out["s"].items():
    print(k, {s: (round(v[s]["cagr"], 3), round(v[s]["maxdd"], 3), v[s]["mar"] and round(v[s]["mar"], 2)) for s in ("all", "build", "test") if s in v})
