/* April's Stock Atlas — the site header shared by every page except the homepage (which renders the same header itself,
   in april-stock-atlas/scripts/build_home.py; keep the two in step).
   Loaded as a blocking <script> at the start of <body>; inserts the header right after itself so it paints with the page.
   One white bar: brand · sections (Today, Insiders, Options, Funds, Earnings, Calendar, Markets, Themes) · ticker search · language · Subscribe.
   Below 1260px wide it becomes three rows: brand + Subscribe, search + language, then the sections as a scrolling tab row.
   Pages keep their own section-level controls (insider tabs and filters, the Earnings Lens sub-navigation and search);
   their own brand row and language buttons are hidden once this header is up, and this header's language buttons press
   the page's own (#lang-xx, or .lang button[data-l]) so each page keeps switching language its own way. Pages with no
   such control (company pages, which switch by address) keep their own links and this header shows no language buttons.
   Subscribe opens a small dialog (Buttondown embed form). */
(function () {
  if (document.getElementById("aps")) return;
  var path = location.pathname;
  var cur = /^\/options(\/|$)/.test(path) ? "opt" : /^\/institutions(\/|$)/.test(path) ? "inst" : /^\/earnings(\/|$)/.test(path) ? "earn" : /^\/calendar(\/|$)/.test(path) ? "cal"
    : /^\/(market|articles)(\/|$)/.test(path) ? "mkt" : /^\/(themes|stack|energy|ai)(\/|$)/.test(path) ? "chain"
    : /^\/(insider|en|zh|tw|s|subscribed)(\/|\.|$)/.test(path) ? "ins" : path === "/" ? "home" : "";
  var NAV = ["home", "ins", "opt", "inst", "earn", "cal", "mkt", "chain"];
  var HREF = { home: "/", ins: "/insider/", opt: "/options/", inst: "/institutions/", earn: "/earnings/", cal: "/calendar/", mkt: "/market/", chain: "/themes/" };
  var L = {
    en: { home: "Today", ins: "Insiders", opt: "Options", inst: "Funds", earn: "Earnings", cal: "Calendar", mkt: "Markets", chain: "Themes", sub: "Subscribe",
      ph: "Search ticker, e.g. NVDA", none: "No page for ", nav: "Sections", lang: "Language",
      st: "Weekly email and daily brief", sd: "One email every weekend with the week's insider trading highlights and new earnings reviews.", sd2: "Also send me the daily brief: the day's recap, signals and what's coming, around 8pm Beijing time on trading days (already subscribed? tick it and submit again)",
      sp: "you@example.com", sb: "Subscribe", sf: "Free, unsubscribe anytime. Chinese first, English below.", sc: "Close" },
    zh: { home: "今日", ins: "内部人", opt: "期权", inst: "机构", earn: "财报", cal: "日历", mkt: "市场", chain: "产业链", sub: "订阅",
      ph: "搜索代码，如 NVDA", none: "没有找到 ", nav: "栏目", lang: "语言",
      st: "周报和每日早报", sd: "每个周末一封，汇总一周的内部人买卖要点和新上线的财报解读。", sd2: "也每天收早报：每个交易日北京时间晚上 8 点左右，当天的复盘、信号和接下来的大事（已订阅的读者勾选后再提交一次即可）",
      sp: "你的邮箱", sb: "订阅", sf: "免费，随时可以退订。中文在前，英文在后。", sc: "关闭" },
    tw: { home: "今日", ins: "內部人", opt: "選擇權", inst: "機構", earn: "財報", cal: "日曆", mkt: "市場", chain: "產業鏈", sub: "訂閱",
      ph: "搜尋代碼，如 NVDA", none: "沒有找到 ", nav: "欄目", lang: "語言",
      st: "週報和每日早報", sd: "每個週末一封，彙總一週的內部人買賣要點和新上線的財報解讀。", sd2: "也每天收早報：每個交易日北京時間晚上 8 點左右，當天的復盤、信號和接下來的大事（已訂閱的讀者勾選後再提交一次即可）",
      sp: "你的郵箱", sb: "訂閱", sf: "免費，隨時可以退訂。中文在前，英文在後。", sc: "關閉" }
  };
  function fromTag(v) {
    v = String(v || "").toLowerCase();
    if (v.indexOf("zh") === 0) return /hant|-tw|-hk|-mo/.test(v) ? "tw" : "zh";
    return v.indexOf("en") === 0 ? "en" : null;
  }
  function detect() {
    var v = fromTag(document.documentElement.getAttribute("lang"));
    try { var s = localStorage.getItem("sif-lang"); if (s === "en" || s === "zh" || s === "tw") v = s; } catch (e) {}
    if (v) return v;
    var ls = (navigator.languages && navigator.languages.length ? navigator.languages : [navigator.language || "en"]);
    for (var i = 0; i < ls.length; i++) { var x = fromTag(ls[i]); if (x) return x; }
    return "en";
  }
  var lang = detect();
  /* the site's own Latin fonts (served by the main site at /fonts/), so the header looks the same on every page */
  var FONT = [["Figtree", 400, "f1"], ["Figtree", 600, "f2"], ["Figtree", 700, "f3"], ["Bricolage Grotesque", 700, "f4"]].map(function (f) {
    return "@font-face{font-family:'" + f[0] + "';font-style:normal;font-weight:" + f[1] + ";font-display:swap;src:url(/fonts/" + f[2] + ".woff2) format('woff2');"
      + "unicode-range:U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+2000-206F,U+2074,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD}";
  }).join("");
  var css = FONT +
    "#aps{--h-bg:#fff;--h-ink:#0e1726;--h-muted:#5d6879;--h-faint:#7d8798;--h-line:#e1e6ed;--h-soft:#f5f7fa;--h-accent:#2c49c9;--h-accent-ink:#fff;" +
    "background:var(--h-bg);border-bottom:1px solid var(--h-line);position:relative;z-index:30;color:var(--h-ink);" +
    "font-family:Figtree,'PingFang SC','Hiragino Sans GB','Microsoft YaHei','Noto Sans SC',system-ui,-apple-system,sans-serif;font-size:15px;line-height:1.5;padding-top:env(safe-area-inset-top,0px)}" +
    "@media (prefers-color-scheme:dark){:root:not([data-theme=light]) #aps{--h-bg:#131c2a;--h-ink:#e8edf4;--h-muted:#9aa6b8;--h-faint:#7a869a;--h-line:#243146;--h-soft:#1a2535;--h-accent:#8ea6ff;--h-accent-ink:#0b111b}}" +
    ":root[data-theme=dark] #aps{--h-bg:#131c2a;--h-ink:#e8edf4;--h-muted:#9aa6b8;--h-faint:#7a869a;--h-line:#243146;--h-soft:#1a2535;--h-accent:#8ea6ff;--h-accent-ink:#0b111b}" +
    "#aps *{box-sizing:border-box}#aps svg{display:block;flex:none;max-width:none}#aps .aps-s svg{width:16px!important;height:16px!important}#aps .aps-lg svg{width:18px!important;height:18px!important}" +
    "#aps .aps-in{max-width:1200px;margin:0 auto;padding:0 max(16px,env(safe-area-inset-right,0px)) 0 max(16px,env(safe-area-inset-left,0px));min-height:64px;display:flex;align-items:center;gap:16px}" +
    "#aps .aps-br{display:flex;align-items:center;gap:10px;color:var(--h-ink);text-decoration:none;flex:none;min-width:0}" +
    "#aps .aps-lg{width:30px;height:30px;border-radius:9px;background:#0f1b2d;display:grid;place-items:center;flex:none}" +
    "#aps .aps-br b{font-family:'Bricolage Grotesque',Figtree,system-ui,sans-serif;font-weight:700;font-size:18px;letter-spacing:-.01em;white-space:nowrap}" +
    "#aps .aps-br b i{font-style:normal;color:var(--h-accent)}" +
    "#aps .aps-nav{display:flex;gap:16px;align-items:center;flex:1;min-width:0}" +
    "#aps .aps-nav a{color:var(--h-muted);text-decoration:none;font-size:14.5px;font-weight:500;padding:20px 1px 18px;border-bottom:2px solid transparent;white-space:nowrap}" +
    "#aps .aps-nav a:hover{color:var(--h-ink)}#aps .aps-nav a[aria-current=page]{color:var(--h-ink);font-weight:700;border-bottom-color:var(--h-accent)}" +
    "#aps .aps-s{position:relative;display:flex;align-items:center;gap:8px;background:var(--h-soft);border:1px solid var(--h-line);border-radius:10px;padding:0 12px;height:38px;width:170px;flex:none;color:var(--h-faint);margin:0}" +
    "#aps .aps-s:focus-within{border-color:var(--h-accent)}" +
    "#aps .aps-s input{border:0;background:transparent;outline:none;font:inherit;font-size:14px;width:100%;min-width:0;color:var(--h-ink);padding:0;margin:0;box-shadow:none}" +
    "#aps .aps-msg{position:absolute;left:0;top:42px;font-size:12.5px;color:var(--h-muted);white-space:nowrap}" +
    "#aps .aps-lang{display:inline-flex;background:var(--h-soft);border:1px solid var(--h-line);border-radius:999px;padding:3px;flex:none}" +
    "#aps .aps-lang[hidden]{display:none}" +
    "#aps .aps-lang button{border:0;background:none;padding:5px 10px;border-radius:999px;font:inherit;font-size:13px;color:var(--h-muted);cursor:pointer;min-width:0}" +
    "#aps .aps-lang button[aria-pressed=true]{background:var(--h-ink);color:var(--h-bg)}" +
    "#aps .aps-sub{border:0;background:var(--h-accent);color:var(--h-accent-ink);font:inherit;font-weight:700;font-size:14px;border-radius:10px;padding:9px 16px;cursor:pointer;flex:none}" +
    "#aps a:focus-visible,#aps button:focus-visible{outline:2px solid var(--h-accent);outline-offset:2px}" +
    "@media (max-width:1260px){" +
    "#aps .aps-in{display:grid;grid-template-columns:minmax(0,1fr) auto;grid-template-areas:'br sub' 's lang' 'nav nav';gap:10px;padding-top:10px;min-height:0}" +
    "#aps .aps-br{grid-area:br}#aps .aps-sub{grid-area:sub;justify-self:end}#aps .aps-s{grid-area:s;width:auto}#aps .aps-lang{grid-area:lang;align-self:center}" +
    "#aps.nolang .aps-in{grid-template-areas:'br sub' 's s' 'nav nav'}" +
    "#aps .aps-nav{grid-area:nav;gap:18px;overflow-x:auto;scrollbar-width:none;margin:0 -16px;padding:0 16px}#aps .aps-nav::-webkit-scrollbar{display:none}" +
    "#aps .aps-nav a{padding:8px 1px 9px}}" +
    "@media (max-width:420px){#aps .aps-sub{padding:8px 12px}}" +
    /* the page's own brand row and language buttons give way to this header */
    "html[data-aps] header.top:not(.gutter){display:none}html[data-aps] header.top .topin{display:none}" +
    "html[data-aps] .lang:not(.aps-lang){display:none!important}html[data-aps] #subopen{display:none}html[data-aps] a.brand{display:none}" +
    /* subscribe dialog */
    "#aps-m{position:fixed;inset:0;z-index:90;background:rgba(5,10,20,.66);display:grid;place-items:center;padding:16px;font-family:system-ui,-apple-system,'PingFang SC','Microsoft YaHei',sans-serif;--m-bg:#fff;--m-ink:#14171c;--m-muted:#5d6879;--m-line:#d5dae3;--m-btn:#2c49c9;--m-btn-ink:#fff}" +
    "@media (prefers-color-scheme:dark){:root:not([data-theme=light]) #aps-m{--m-bg:#1c2230;--m-ink:#e8eaee;--m-muted:#9aa3b2;--m-line:#33405a;--m-btn:#8ea6ff;--m-btn-ink:#0b111b}}" +
    ":root[data-theme=dark] #aps-m{--m-bg:#1c2230;--m-ink:#e8eaee;--m-muted:#9aa3b2;--m-line:#33405a;--m-btn:#8ea6ff;--m-btn-ink:#0b111b}" +
    "#aps-m[hidden]{display:none}" +
    "#aps-m .box{position:relative;background:var(--m-bg);color:var(--m-ink);border-radius:18px;padding:26px 22px 20px;width:min(440px,100%);text-align:center;box-shadow:0 20px 60px rgba(0,0,0,.35)}" +
    "#aps-m h2{margin:0 0 8px;font-size:21px;line-height:1.2;border:0;padding:0}" +
    "#aps-m p{margin:0 0 14px;font-size:14.5px;line-height:1.55;color:var(--m-muted)}" +
    "#aps-m p.fine{margin:12px 0 0;font-size:12.5px}" +
    "#aps-m form{display:flex;gap:8px;flex-wrap:wrap}#aps-m .dly{flex:1 1 100%;display:flex;gap:8px;align-items:flex-start;text-align:left;font-size:13px;color:var(--m-muted);cursor:pointer}#aps-m .dly input{margin-top:3px}" +
    "#aps-m input[type=email]{flex:1;min-width:0;font:inherit;font-size:15px;padding:10px 12px;border:1px solid var(--m-line);border-radius:12px;background:transparent;color:var(--m-ink)}" +
    "#aps-m input[type=email]:focus-visible{outline:2px solid #7d9bff;outline-offset:1px}" +
    "#aps-m form button{font:inherit;font-size:14.5px;font-weight:700;padding:10px 16px;border:0;border-radius:12px;background:var(--m-btn);color:var(--m-btn-ink);cursor:pointer;white-space:nowrap}" +
    "#aps-m .x{position:absolute;top:8px;right:8px;border:0;background:none;color:var(--m-muted);font-size:24px;line-height:1;padding:6px 10px;border-radius:10px;cursor:pointer}" +
    "#aps-m .x:focus-visible,#aps-m form button:focus-visible{outline:2px solid #7d9bff;outline-offset:2px}" +
    "@media (max-width:420px){#aps-m form{flex-direction:column}}";
  var st = document.createElement("style");
  st.textContent = css;
  document.head.appendChild(st);

  var LOGO = '<span class="aps-lg" aria-hidden="true"><svg width="18" height="18" viewBox="0 0 18 18"><rect x="2" y="9" width="3" height="7" rx="1.5" fill="#ff7b72"/><rect x="7.5" y="5" width="3" height="11" rx="1.5" fill="#3ddc9b"/><rect x="13" y="2" width="3" height="14" rx="1.5" fill="#3ddc9b"/></svg></span>';
  var bar = document.createElement("header");
  bar.id = "aps";
  bar.innerHTML = '<div class="aps-in">' +
    '<a class="aps-br" href="/" aria-label="April\'s Stock Atlas">' + LOGO + "<b><i>April's</i> Stock Atlas</b></a>" +
    '<nav class="aps-nav">' + NAV.map(function (k) { return '<a href="' + HREF[k] + '" data-k="' + k + '"' + (cur === k ? ' aria-current="page"' : "") + "></a>"; }).join("") + "</nav>" +
    '<form class="aps-s" role="search"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>' +
    '<input type="search" autocomplete="off" autocapitalize="characters" spellcheck="false"><span class="aps-msg" role="status"></span></form>' +
    '<div class="aps-lang" role="group"><button type="button" data-lng="zh" lang="zh-CN">简</button><button type="button" data-lng="tw" lang="zh-TW">繁</button><button type="button" data-lng="en">EN</button></div>' +
    '<button type="button" class="aps-sub"></button></div>';
  var me = document.currentScript;
  if (me && me.parentNode) me.parentNode.insertBefore(bar, me.nextSibling);
  else document.body.insertBefore(bar, document.body.firstChild);
  document.documentElement.setAttribute("data-aps", "");  /* an attribute, not a class: some pages rewrite <html class> when switching language */

  /* language: press the page's own control, so each page switches its own way */
  function pageControl(k) {
    return document.getElementById("lang-" + k) || document.querySelector('.lang:not(.aps-lang) button[data-l="' + k + '"]');
  }
  var langBox = bar.querySelector(".aps-lang");
  function checkLang() {
    var has = !!pageControl("zh");
    langBox.hidden = !has;
    bar.classList.toggle("nolang", !has);
  }
  langBox.addEventListener("click", function (e) {
    var b = e.target.closest("button"); if (!b) return;
    var k = b.getAttribute("data-lng"), c = pageControl(k);
    try { localStorage.setItem("sif-lang", k); } catch (x) {}
    if (c) c.click(); else location.reload();
    lang = k; paint();
  });

  /* ticker search: straight to the company page; the ticker list loads on first use */
  var form = bar.querySelector(".aps-s"), q = form.querySelector("input"), msg = form.querySelector(".aps-msg"), tick = null;
  function loadTickers() {
    if (tick) return tick;
    tick = fetch("/tickers.json").then(function (r) { if (!r.ok) throw 0; return r.json(); }).then(function (a) { return new Set(a); }).catch(function () { return null; });
    return tick;
  }
  q.addEventListener("focus", loadTickers);
  q.addEventListener("input", function () { msg.textContent = ""; });
  form.addEventListener("submit", function (e) {
    e.preventDefault();
    var v = q.value.trim().toUpperCase().replace(/^\$/, "");
    if (!v) return;
    loadTickers().then(function (set) {
      if (!set || set.has(v)) location.href = "/s/" + encodeURIComponent(v) + ".html";
      else msg.textContent = (L[lang] || L.en).none + v;
    });
  });

  /* subscribe dialog */
  var modal = null, opener = null;
  function buildModal() {
    modal = document.createElement("div");
    modal.id = "aps-m";
    modal.hidden = true;
    modal.innerHTML = '<div class="box" role="dialog" aria-modal="true" aria-labelledby="aps-mt"><button type="button" class="x" data-x></button>' +
      '<h2 id="aps-mt"></h2><p id="aps-md"></p>' +
      '<form action="https://buttondown.com/api/emails/embed-subscribe/april-insider-stock" method="post" target="_blank" rel="noopener">' +
      '<input type="email" name="email" required autocomplete="email"><input type="hidden" name="embed" value="1"><button type="submit"></button>' +
      '<label class="dly"><input type="checkbox" name="tag" value="daily"> <span id="aps-md2"></span></label></form>' +
      '<p class="fine" id="aps-mf"></p></div>';
    document.body.appendChild(modal);
    modal.addEventListener("click", function (e) { if (e.target === modal || e.target.hasAttribute("data-x")) close(); });
    modal.querySelector("form").addEventListener("submit", function () { setTimeout(close, 300); });
    document.addEventListener("keydown", function (e) { if (e.key === "Escape" && modal && !modal.hidden) close(); });
    paint();
  }
  function open() {
    if (!modal) buildModal();
    opener = document.activeElement;
    modal.hidden = false;
    setTimeout(function () { try { modal.querySelector("input[type=email]").focus(); } catch (e) {} }, 50);
  }
  function close() {
    if (!modal) return;
    modal.hidden = true;
    try { if (opener && opener.focus) opener.focus(); } catch (e) {}
  }
  bar.querySelector(".aps-sub").addEventListener("click", open);

  function paint() {
    var s = L[lang] || L.en;
    NAV.forEach(function (k) { bar.querySelector('a[data-k="' + k + '"]').textContent = s[k]; });
    bar.querySelector(".aps-nav").setAttribute("aria-label", s.nav);
    langBox.setAttribute("aria-label", s.lang);
    [].forEach.call(langBox.querySelectorAll("button"), function (b) { b.setAttribute("aria-pressed", String(b.getAttribute("data-lng") === lang)); });
    q.placeholder = s.ph; q.setAttribute("aria-label", s.ph);
    bar.querySelector(".aps-sub").textContent = s.sub;
    if (modal) {
      modal.querySelector(".x").textContent = "×";
      modal.querySelector(".x").setAttribute("aria-label", s.sc);
      modal.querySelector("#aps-mt").textContent = s.st;
      modal.querySelector("#aps-md").textContent = s.sd;
      modal.querySelector("input[type=email]").placeholder = s.sp;
      modal.querySelector("input[type=email]").setAttribute("aria-label", s.sp);
      modal.querySelector("form button").textContent = s.sb;
      modal.querySelector("#aps-mf").textContent = s.sf;
      modal.querySelector("#aps-md2").textContent = s.sd2;
    }
  }
  paint();
  /* follow the page's own language switch (the pages set <html lang> and "sif-lang") */
  new MutationObserver(function () {
    var x = fromTag(document.documentElement.getAttribute("lang"));
    if (x && x !== lang) { lang = x; paint(); }
  }).observe(document.documentElement, { attributes: true, attributeFilter: ["lang"] });
  function ready() { checkLang(); var x = fromTag(document.documentElement.getAttribute("lang")); if (x && x !== lang) { lang = x; paint(); } }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", ready); else ready();
})();
