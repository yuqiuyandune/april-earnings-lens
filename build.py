"""Build the Cloudflare Pages upload for April's Earnings Lens.

Source pages (index.html, calendar.html) are written as artifact-style fragments
(no <html>/<head>). This script wraps them into full HTML documents and lays out:

  dist/index.html                 -> redirect to /earnings/
  dist/earnings/index.html        -> analysis site (template)
  dist/earnings/calendar/index.html
  dist/earnings/data/...          -> JSON data files

Usage:  python3 build.py   (creates dist/ and earnings-lens-site.zip)
"""
import pathlib, shutil, zipfile

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
        wrap((ROOT / "index.html").read_text(encoding="utf-8"),
             "April's Earnings Lens：AI 产业链和重点科技公司的季度财报解读。"), encoding="utf-8")
    (DIST / "earnings" / "calendar" / "index.html").write_text(
        wrap((ROOT / "calendar.html").read_text(encoding="utf-8"),
             "April's Earnings Lens 财报日历：重点公司的发布日期与解读进度。"), encoding="utf-8")
    shutil.copytree(ROOT / "data", DIST / "earnings" / "data")
    shutil.copy(ROOT / "switcher.js", DIST / "earnings" / "switcher.js")
    zpath = ROOT / "earnings-lens-site.zip"
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(DIST.rglob("*")):
            if f.is_file():
                z.write(f, f.relative_to(DIST))
    print("built", zpath, sum(1 for f in DIST.rglob("*") if f.is_file()), "files")

if __name__ == "__main__":
    main()
