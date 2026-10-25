# April's Earnings Lens

Source for https://april-insider-flow.com/earnings/

- `index.html` — generic page template (reads `data/`)
- `calendar.html` — earnings-season calendar
- `switcher.js` — product switcher bar shared with Insider Flow
- `data/` — `index.json`, `companies/`, `reports/<TICKER>/<YYYYQn>.json`, `promises/`
- `build.py` — builds `dist/` (Cloudflare Pages build command: `python3 build.py`, output: `dist`)
