# April's Earnings Lens

Source for https://april-insider-flow.com/earnings/

- `index.html` — generic page template (reads `data/`)
- `calendar.html` — earnings-season calendar
- `switcher.js` — the site header shared by every April's Stock Atlas page except the homepage (brand, sections, ticker search, language, subscribe); keep it in step with the homepage header in april-stock-atlas `scripts/build_home.py`
- `data/` — `index.json`, `companies/`, `reports/<TICKER>/<YYYYQn>.json`, `promises/`
- `build.py` — builds `dist/` (Cloudflare Pages build command: `python3 build.py`, output: `dist`)
- `scripts/capital_return.py` — buybacks, dividends and dividend per share per quarter from SEC XBRL into `data/companies/*.json` (`bb`, `dv`, `dps`, and `fcfx` when there is no hand-entered free-cash-flow series). Run it after adding a quarter; hand-entered extras go in a report's `valuation.cash.ret` (`auth`: buyback authorization left, `note`: one-line reading)
