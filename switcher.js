/* April's product switcher — shared by April's Stock Atlas: Overview (/overview/), the supply-chain pages (AI at /, energy at /energy/ — both under the Supply Chains button), Insider Flow (/insider/), Earnings Lens (/earnings/) and Market watch (/market/, with its articles under /articles/).
   Loaded as a blocking <script> at the start of <body>; inserts the bar right after itself so it paints with the page.
   Design: a dark full-width band (clearly separate from any site's own header) with a five-button segmented control and a
   Subscribe button; the current product is a solid light button, the others are outlined, clearly clickable buttons.
   Labels follow the reader's language (EN / 简 / 繁): the page's <html lang>, else localStorage "sif-lang", else the browser.
   Subscribe opens a small dialog (Buttondown embed form) on every page. */
(function () {
  if (document.getElementById("aps")) return;
  var path = location.pathname;
  var cur = path.indexOf("/earnings") === 0 ? "earn" : path.indexOf("/overview") === 0 ? "ov" : /^\/(market|articles)(\/|$)/.test(path) ? "mkt"
    : /^\/(insider|en|zh|tw|s|subscribed)(\/|\.|$)/.test(path) ? "ins" : "chain";

  var L = {
    en: { ov: "Overview", ovS: "About", chainS: "Chain", insS: "Insiders", earnS: "Earnings", chain: "Supply Chains", ins: "Insider Flow", earn: "Earnings Lens", mkt: "Market Watch", mktS: "Markets", sub: "Subscribe",
      st: "Weekly email", sd: "One email every weekend with the week's insider trading highlights: sectors, cluster buys, the largest purchases and planned sales.",
      sp: "you@example.com", sb: "Subscribe", sf: "Free, unsubscribe anytime. Chinese first, English below.", sc: "Close", nav: "April’s" },
    zh: { ov: "概览", ovS: "概览", chainS: "产业链", insS: "内部人", earnS: "财报", chain: "产业链", ins: "内部人动向", earn: "财报解读", mkt: "市场观察", mktS: "市场", sub: "订阅",
      st: "每周邮件", sd: "每个周末一封，汇总一周的内部人买卖要点：板块、集群买入、最大的买入和拟出售。",
      sp: "你的邮箱", sb: "订阅", sf: "免费，随时可以退订。中文在前，英文在后。", sc: "关闭", nav: "April’s" },
    tw: { ov: "概覽", ovS: "概覽", chainS: "產業鏈", insS: "內部人", earnS: "財報", chain: "產業鏈", ins: "內部人動向", earn: "財報解讀", mkt: "市場觀察", mktS: "市場", sub: "訂閱",
      st: "每週郵件", sd: "每個週末一封，彙總一週的內部人買賣要點：板塊、集群買入、最大的買入和擬出售。",
      sp: "你的郵箱", sb: "訂閱", sf: "免費，隨時可以退訂。中文在前，英文在後。", sc: "關閉", nav: "April’s" }
  };
  function fromTag(v) {
    v = String(v || "").toLowerCase();
    if (v.indexOf("zh") === 0) return /hant|-tw|-hk|-mo/.test(v) ? "tw" : "zh";
    return v.indexOf("en") === 0 ? "en" : null;
  }
  function detect() {
    var v = null;
    try { v = localStorage.getItem("sif-lang"); } catch (e) {}
    if (v === "en" || v === "zh" || v === "tw") return v;
    var ls = (navigator.languages && navigator.languages.length ? navigator.languages : [navigator.language || "en"]);
    for (var i = 0; i < ls.length; i++) { var x = fromTag(ls[i]); if (x) return x; }
    return "en";
  }
  var lang = detect();

  var css =
    "#aps{--aps-band:#14171c;--aps-on-bg:#ffffff;--aps-on-ink:#14171c;--aps-off:#c9ced8;--aps-off-line:rgba(255,255,255,.22);--aps-hover:rgba(255,255,255,.10);--aps-brand:#9aa3b2;" +
    "background:var(--aps-band);font-family:system-ui,-apple-system,'PingFang SC','Microsoft YaHei',sans-serif;position:relative;z-index:30;" +
    "padding-top:env(safe-area-inset-top,0px)}" +
    "@media (prefers-color-scheme:dark){:root:not([data-theme=light]) #aps{--aps-band:#1c2230;--aps-on-bg:#e8eaee;--aps-on-ink:#12151c;--aps-off-line:rgba(255,255,255,.2)}}" +
    ":root[data-theme=dark] #aps{--aps-band:#1c2230;--aps-on-bg:#e8eaee;--aps-on-ink:#12151c;--aps-off-line:rgba(255,255,255,.2)}" +
    "#aps .aps-in{display:flex;align-items:center;gap:8px;height:52px;padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px))}" +
    "#aps .aps-b{font-size:13px;font-weight:600;font-style:italic;color:var(--aps-brand);margin-right:6px;white-space:nowrap;letter-spacing:.02em}" +
    "#aps .aps-seg{display:flex;gap:6px}" +
    "#aps .aps-sp{flex:1}" +
    "#aps a,#aps button.aps-sub{display:flex;align-items:center;gap:7px;height:36px;padding:0 14px;border-radius:9px;text-decoration:none;white-space:nowrap;cursor:pointer;" +
    "font:inherit;font-size:14.5px;font-weight:600;color:var(--aps-off);background:none;border:1px solid var(--aps-off-line);transition:background .15s,color .15s}" +
    "#aps a:hover,#aps button.aps-sub:hover{background:var(--aps-hover);color:#fff}" +
    "#aps a:focus-visible,#aps button.aps-sub:focus-visible{outline:2px solid #7d9bff;outline-offset:2px}" +
    "#aps a[aria-current=page]{background:var(--aps-on-bg);color:var(--aps-on-ink);border-color:var(--aps-on-bg);cursor:default}" +
    "#aps svg{flex:none;display:block;width:16px!important;height:16px!important;max-width:none}" +
    "#aps button.aps-sub{margin-left:auto}" +
    "#aps .aps-ts{display:none}" +
    "@media (max-width:640px){#aps .aps-b{display:none}#aps .aps-seg{flex:1}#aps a{flex:1;justify-content:center;padding:0 6px;font-size:13.5px}#aps a svg{display:none}#aps .aps-t{display:none}#aps .aps-ts{display:inline}" +
    "#aps button.aps-sub{width:36px;padding:0;justify-content:center;margin-left:0}#aps .aps-subt{display:none}}" +
    "@media (max-width:380px){#aps .aps-in{gap:6px}#aps .aps-seg{gap:4px}#aps a{font-size:12.5px;padding:0 3px}}" +
    "@media (prefers-reduced-motion:reduce){#aps a,#aps button.aps-sub{transition:none}}" +
    /* subscribe dialog */
    "#aps-m{position:fixed;inset:0;z-index:90;background:rgba(5,10,20,.66);display:grid;place-items:center;padding:16px;font-family:system-ui,-apple-system,'PingFang SC','Microsoft YaHei',sans-serif;--m-bg:#fff;--m-ink:#14171c;--m-muted:#5d6573;--m-line:#d9dde5;--m-btn:#14171c;--m-btn-ink:#fff}" +
    "@media (prefers-color-scheme:dark){:root:not([data-theme=light]) #aps-m{--m-bg:#1c2230;--m-ink:#e8eaee;--m-muted:#9aa3b2;--m-line:#33405a;--m-btn:#e8eaee;--m-btn-ink:#12151c}}" +
    ":root[data-theme=dark] #aps-m{--m-bg:#1c2230;--m-ink:#e8eaee;--m-muted:#9aa3b2;--m-line:#33405a;--m-btn:#e8eaee;--m-btn-ink:#12151c}" +
    "#aps-m[hidden]{display:none}" +
    "#aps-m .box{position:relative;background:var(--m-bg);color:var(--m-ink);border-radius:18px;padding:26px 22px 20px;width:min(440px,100%);text-align:center;box-shadow:0 20px 60px rgba(0,0,0,.35)}" +
    "#aps-m h2{margin:0 0 8px;font-size:21px;line-height:1.2}" +
    "#aps-m p{margin:0 0 14px;font-size:14.5px;line-height:1.55;color:var(--m-muted)}" +
    "#aps-m p.fine{margin:12px 0 0;font-size:12.5px}" +
    "#aps-m form{display:flex;gap:8px}" +
    "#aps-m input[type=email]{flex:1;min-width:0;font:inherit;font-size:15px;padding:10px 12px;border:1px solid var(--m-line);border-radius:12px;background:transparent;color:var(--m-ink)}" +
    "#aps-m input[type=email]:focus-visible{outline:2px solid #7d9bff;outline-offset:1px}" +
    "#aps-m form button{font:inherit;font-size:14.5px;font-weight:700;padding:10px 16px;border:0;border-radius:12px;background:var(--m-btn);color:var(--m-btn-ink);cursor:pointer;white-space:nowrap}" +
    "#aps-m .x{position:absolute;top:8px;right:8px;border:0;background:none;color:var(--m-muted);font-size:24px;line-height:1;padding:6px 10px;border-radius:10px;cursor:pointer}" +
    "#aps-m .x:focus-visible,#aps-m form button:focus-visible{outline:2px solid #7d9bff;outline-offset:2px}" +
    "@media (max-width:420px){#aps-m form{flex-direction:column}}";
  var st = document.createElement("style");
  st.textContent = css;
  document.head.appendChild(st);

  var ICO = {
    ov: '<svg viewBox="0 0 18 18" aria-hidden="true"><circle cx="9" cy="9" r="7" fill="none" stroke="currentColor" stroke-width="1.6"/><path d="M9 8v4.5" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/><circle cx="9" cy="5.6" r="1.1" fill="currentColor"/></svg>',
    chain: '<svg viewBox="0 0 18 18" aria-hidden="true"><rect x="2" y="2.5" width="14" height="3" rx="1.2" fill="currentColor"/><rect x="2" y="7.5" width="14" height="3" rx="1.2" fill="currentColor" opacity=".75"/><rect x="2" y="12.5" width="14" height="3" rx="1.2" fill="currentColor" opacity=".5"/></svg>',
    ins: '<svg viewBox="0 0 18 18" aria-hidden="true"><rect x="2" y="9" width="3" height="7" rx="1.5" fill="#ff7b72"/><rect x="7.5" y="5" width="3" height="11" rx="1.5" fill="#3ddc9b"/><rect x="13" y="2" width="3" height="14" rx="1.5" fill="#3ddc9b"/></svg>',
    earn: '<svg viewBox="0 0 18 18" aria-hidden="true"><rect x="2.5" y="1.5" width="13" height="15" rx="2.5" fill="none" stroke="currentColor" stroke-width="1.6"/><path d="M5.5 12.5v-2.5M9 12.5v-5M12.5 12.5V9" stroke="#7d9bff" stroke-width="1.8" stroke-linecap="round"/></svg>',
    mkt: '<svg viewBox="0 0 18 18" aria-hidden="true"><path d="M2 13.5l4-4.5 3 2.5 4.5-6 2.5 2.5" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/><path d="M2 16h14" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" opacity=".6"/></svg>',
    mail: '<svg viewBox="0 0 16 16" aria-hidden="true"><rect x="1.5" y="3" width="13" height="10" rx="2" fill="none" stroke="currentColor" stroke-width="1.6"/><path d="M2.5 4.5 8 9l5.5-4.5" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>'
  };
  var HREF = { ov: "/overview/", chain: "/", ins: "/insider/", earn: "/earnings/", mkt: "/market/" };
  var bar = document.createElement("nav");
  bar.id = "aps";
  var seg = "";
  ["ov", "chain", "ins", "earn", "mkt"].forEach(function (k) {
    seg += '<a href="' + HREF[k] + '" data-k="' + k + '"' + (cur === k ? ' aria-current="page"' : "") + ">" + ICO[k] + '<span class="aps-t"></span><span class="aps-ts"></span></a>';
  });
  bar.innerHTML = '<div class="aps-in"><span class="aps-b"></span><div class="aps-seg">' + seg + "</div>" +
    '<button type="button" class="aps-sub" id="aps-open">' + ICO.mail + '<span class="aps-subt"></span></button></div>';
  var me = document.currentScript;
  if (me && me.parentNode) me.parentNode.insertBefore(bar, me.nextSibling);
  else document.body.insertBefore(bar, document.body.firstChild);

  var modal = null, opener = null;
  function buildModal() {
    modal = document.createElement("div");
    modal.id = "aps-m";
    modal.hidden = true;
    modal.innerHTML = '<div class="box" role="dialog" aria-modal="true" aria-labelledby="aps-mt"><button type="button" class="x" data-x></button>' +
      '<h2 id="aps-mt"></h2><p id="aps-md"></p>' +
      '<form action="https://buttondown.com/api/emails/embed-subscribe/april-insider-stock" method="post" target="_blank" rel="noopener">' +
      '<input type="email" name="email" required autocomplete="email"><input type="hidden" name="embed" value="1"><button type="submit"></button></form>' +
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
  bar.querySelector("#aps-open").addEventListener("click", open);

  function paint() {
    var s = L[lang] || L.en;
    bar.querySelector(".aps-b").textContent = s.nav;
    ["ov", "chain", "ins", "earn", "mkt"].forEach(function (k) {
      var a = bar.querySelector('a[data-k="' + k + '"]');
      a.querySelector(".aps-t").textContent = s[k];
      a.querySelector(".aps-ts").textContent = s[k + "S"];
    });
    bar.querySelector(".aps-subt").textContent = s.sub;
    bar.querySelector("#aps-open").setAttribute("aria-label", s.sub);
    if (modal) {
      modal.querySelector(".x").textContent = "×";
      modal.querySelector(".x").setAttribute("aria-label", s.sc);
      modal.querySelector("#aps-mt").textContent = s.st;
      modal.querySelector("#aps-md").textContent = s.sd;
      modal.querySelector("input[type=email]").placeholder = s.sp;
      modal.querySelector("input[type=email]").setAttribute("aria-label", s.sp);
      modal.querySelector("form button").textContent = s.sb;
      modal.querySelector("#aps-mf").textContent = s.sf;
    }
  }
  paint();
  /* follow the page's own language switch (the sites set <html lang> and "sif-lang") */
  new MutationObserver(function () {
    var x = fromTag(document.documentElement.getAttribute("lang"));
    if (x && x !== lang) { lang = x; paint(); }
  }).observe(document.documentElement, { attributes: true, attributeFilter: ["lang"] });

  /* line the bar up with the page's own content column (the sites use .wrap) */
  function align() {
    var w = document.querySelector("body .wrap:not(#aps .wrap)"), inner = bar.firstChild;
    if (!w || innerWidth <= 640) { inner.style.paddingLeft = ""; inner.style.paddingRight = ""; return; }
    var r = w.getBoundingClientRect(), cs = getComputedStyle(w);
    inner.style.paddingLeft = Math.max(16, Math.round(r.left + parseFloat(cs.paddingLeft || 0))) + "px";
    inner.style.paddingRight = Math.max(16, Math.round(innerWidth - r.right + parseFloat(cs.paddingRight || 0))) + "px";
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", align); else align();
  addEventListener("resize", align);
})();
