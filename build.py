"""Build the Cloudflare Pages upload for April's Earnings Lens.

Source pages (index.html, calendar.html) are written as artifact-style fragments
(no <html>/<head>). This script wraps them into full HTML documents and lays out:

  dist/index.html                 -> redirect to /earnings/
  dist/earnings/index.html        -> analysis site (template)
  dist/earnings/calendar/index.html
  dist/earnings/data/...          -> JSON data files (Simplified Chinese, the source)
  dist/earnings/data-tw/...       -> Traditional Chinese, converted with OpenCC (s2twp) at build time
  dist/earnings/data-en/...       -> English: i18n/en/<same path> deep-merged over the Chinese file;
                                     files without an English version keep Chinese and get "_zhOnly": true

Usage:  python3 build.py   (creates dist/ and earnings-lens-site.zip)
"""
import json, pathlib, re, shutil, zipfile

ROOT = pathlib.Path(__file__).parent
DIST = ROOT / "dist"

HEAD = """<!doctype html>
<html lang="zh-Hans">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="description" content="{desc}">
<style>:root{{padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}}body{{margin:0}}img{{max-width:100%}}[hidden]{{display:none!important}}</style>
"""

try:
    from opencc import OpenCC
    _CC = OpenCC("s2twp")
    def to_tw(t: str) -> str: return _CC.convert(t)
except Exception:  # OpenCC missing: Traditional falls back to the Simplified text
    print("warning: opencc not installed, data-tw will be Simplified")
    def to_tw(t: str) -> str: return t

def conv(o, f):
    if isinstance(o, str): return f(o)
    if isinstance(o, list): return [conv(x, f) for x in o]
    if isinstance(o, dict): return {k: (v if k == "u" else conv(v, f)) for k, v in o.items()}
    return o

def merge(base, over):
    """English overlay: dicts merge by key, same-length lists merge item by item, anything else is replaced."""
    if isinstance(base, dict) and isinstance(over, dict):
        out = dict(base)
        for k, v in over.items(): out[k] = merge(base[k], v) if k in base else v
        return out
    if isinstance(base, list) and isinstance(over, list) and len(base) == len(over):
        return [merge(b, o) for b, o in zip(base, over)]
    return over

def build_langs(out: pathlib.Path):
    src = ROOT / "data"; en_src = ROOT / "i18n" / "en"
    en_done = set()
    for f in sorted(src.rglob("*.json")):
        rel = f.relative_to(src); d = json.loads(f.read_text(encoding="utf-8"))
        tw = out / "data-tw" / rel; tw.parent.mkdir(parents=True, exist_ok=True)
        tw.write_text(json.dumps(conv(d, to_tw), ensure_ascii=False), encoding="utf-8")
        e = en_src / rel; en = out / "data-en" / rel; en.parent.mkdir(parents=True, exist_ok=True)
        if e.exists():
            d2 = merge(d, json.loads(e.read_text(encoding="utf-8")))
            if rel.parts[0] == "reports": en_done.add((rel.parts[1], rel.stem))
        else:
            d2 = dict(d) if isinstance(d, dict) else d
            if rel.parts[0] == "reports": d2["_zhOnly"] = True
        if rel.as_posix() == "index.json": index_en = (en, d2)
        else: en.write_text(json.dumps(d2, ensure_ascii=False), encoding="utf-8")
    en, d2 = index_en  # mark companies whose latest report has no English version yet
    CAT = {"应用": "Applications", "模型与云": "Models & cloud", "芯片": "Chips", "代工与设备": "Foundry & equipment",
           "基础设施": "Infrastructure", "能源": "Energy", "消费与平台": "Consumer & platforms", "存储": "Memory & storage"}
    for c in d2["companies"]:
        c["zhOnly"] = (c["t"], c["latest"]) not in en_done
        c["n"] = c.get("en") or c["n"]; c["cat"] = CAT.get(c["cat"], c["cat"])
        if not c["zhOnly"]:
            c["headline"] = json.loads((out / "data-en" / "reports" / c["t"] / f"{c['latest']}.json").read_text(encoding="utf-8"))["headline"]
    en.write_text(json.dumps(d2, ensure_ascii=False), encoding="utf-8")
    print("languages: tw converted, en reports", len(en_done))

def tw_ui(page: str) -> str:
    """Add I18N.tw to the page by converting the Simplified UI dictionary."""
    m = re.search(r"/\*I18N_ZH\*/(\{.*?\})/\*END\*/", page, re.S)
    if not m: return page
    tw = {k: to_tw(v) for k, v in json.loads(m.group(1)).items()}
    return page.replace("let LANG=", "I18N.tw=" + json.dumps(tw, ensure_ascii=False) + ";\nlet LANG=", 1)

def wrap(src: str, desc: str) -> str:
    i = src.index('<div class="wrap">')  # everything before the first wrapper goes in <head>
    return HEAD.format(desc=desc) + src[:i] + "</head>\n<body>\n<script src=\"/earnings/switcher.js\"></script>\n" + src[i:] + "\n</body>\n</html>\n"

def main():
    if DIST.exists():
        shutil.rmtree(DIST)
    (DIST / "earnings" / "calendar").mkdir(parents=True)
    (DIST / "index.html").write_text(
        '<!doctype html><meta charset="utf-8"><meta http-equiv="refresh" content="0;url=/earnings/">'
        '<a href="/earnings/">April\'s Earnings Lens</a>\n', encoding="utf-8")
    (DIST / "earnings" / "index.html").write_text(
        wrap(tw_ui((ROOT / "index.html").read_text(encoding="utf-8")),
             "April's Earnings Lens：AI 产业链和重点科技公司的季度财报解读。"), encoding="utf-8")
    (DIST / "earnings" / "calendar" / "index.html").write_text(
        wrap((ROOT / "calendar.html").read_text(encoding="utf-8"),
             "April's Earnings Lens 财报日历：重点公司的发布日期与解读进度。"), encoding="utf-8")
    shutil.copytree(ROOT / "data", DIST / "earnings" / "data")
    build_langs(DIST / "earnings")
    shutil.copy(ROOT / "switcher.js", DIST / "earnings" / "switcher.js")
    zpath = ROOT / "earnings-lens-site.zip"
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(DIST.rglob("*")):
            if f.is_file():
                z.write(f, f.relative_to(DIST))
    print("built", zpath, sum(1 for f in DIST.rglob("*") if f.is_file()), "files")

if __name__ == "__main__":
    main()
