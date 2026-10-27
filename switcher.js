/* April's product switcher — shared by the AI supply-chain home (/), Insider Flow (/insider/) and Earnings Lens (/earnings/).
   Loaded as a blocking <script> at the start of <body>; inserts the bar right after itself so it paints with the page.
   Design: a dark full-width band (clearly separate from either site's own header) with a three-button segmented control;
   the current product is a solid light button, the other is an outlined, clearly clickable button. */
(function () {
  if (document.getElementById("aps")) return;
  var path = location.pathname;
  var cur = path.indexOf("/earnings") === 0 ? "earn"
    : /^\/(insider|en|zh|tw|s|subscribed)(\/|\.|$)/.test(path) ? "ins" : "chain";
  var css =
    "#aps{--aps-band:#14171c;--aps-on-bg:#ffffff;--aps-on-ink:#14171c;--aps-off:#c9ced8;--aps-off-line:rgba(255,255,255,.22);--aps-hover:rgba(255,255,255,.10);--aps-brand:#9aa3b2;" +
    "background:var(--aps-band);font-family:system-ui,-apple-system,'PingFang SC','Microsoft YaHei',sans-serif;position:relative;z-index:30;" +
    "padding-top:env(safe-area-inset-top,0px)}" +
    "@media (prefers-color-scheme:dark){:root:not([data-theme=light]) #aps{--aps-band:#1c2230;--aps-on-bg:#e8eaee;--aps-on-ink:#12151c;--aps-off-line:rgba(255,255,255,.2)}}" +
    ":root[data-theme=dark] #aps{--aps-band:#1c2230;--aps-on-bg:#e8eaee;--aps-on-ink:#12151c;--aps-off-line:rgba(255,255,255,.2)}" +
    "#aps .aps-in{display:flex;align-items:center;gap:8px;height:52px;padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px))}" +
    "#aps .aps-b{font-size:13px;font-weight:600;font-style:italic;color:var(--aps-brand);margin-right:6px;white-space:nowrap;letter-spacing:.02em}" +
    "#aps .aps-seg{display:flex;gap:6px}" +
    "#aps a{display:flex;align-items:center;gap:7px;height:36px;padding:0 14px;border-radius:9px;text-decoration:none;white-space:nowrap;" +
    "font-size:14.5px;font-weight:600;color:var(--aps-off);border:1px solid var(--aps-off-line);transition:background .15s,color .15s}" +
    "#aps a:hover{background:var(--aps-hover);color:#fff}" +
    "#aps a:focus-visible{outline:2px solid #7d9bff;outline-offset:2px}" +
    "#aps a[aria-current=page]{background:var(--aps-on-bg);color:var(--aps-on-ink);border-color:var(--aps-on-bg);cursor:default}" +
    "#aps a svg{flex:none;display:block;width:16px!important;height:16px!important;max-width:none}" +
    "#aps small{font-size:12px;font-weight:400;opacity:.75}" +
    "#aps .t-tw,html[lang^=zh-TW] #aps .t-cn,html[lang^=zh-Hant] #aps .t-cn{display:none}" +
    "html[lang^=zh-TW] #aps .t-tw,html[lang^=zh-Hant] #aps .t-tw{display:inline}" +
    "html[lang^=en] #aps small{display:none}" +
    "@media (max-width:520px){#aps small{display:none}}" +
    "@media (max-width:520px){#aps .aps-b{display:none}#aps .aps-seg{flex:1}#aps a{flex:1;justify-content:center;padding:0 6px;font-size:13.5px}#aps a svg{display:none}}" +
    "@media (max-width:380px){#aps .aps-in{gap:0}#aps .aps-seg{gap:4px}#aps a{font-size:12.5px;padding:0 4px}}" +
    "@media (prefers-reduced-motion:reduce){#aps a{transition:none}}";
  var st = document.createElement("style");
  st.textContent = css;
  document.head.appendChild(st);
  var icoInsider = '<svg width="16" height="16" viewBox="0 0 18 18" aria-hidden="true"><rect x="2" y="9" width="3" height="7" rx="1.5" fill="#ff7b72"/><rect x="7.5" y="5" width="3" height="11" rx="1.5" fill="#3ddc9b"/><rect x="13" y="2" width="3" height="14" rx="1.5" fill="#3ddc9b"/></svg>';
  var icoEarnings = '<svg width="16" height="16" viewBox="0 0 18 18" aria-hidden="true"><rect x="2.5" y="1.5" width="13" height="15" rx="2.5" fill="none" stroke="currentColor" stroke-width="1.6"/><path d="M5.5 12.5v-2.5M9 12.5v-5M12.5 12.5V9" stroke="#7d9bff" stroke-width="1.8" stroke-linecap="round"/></svg>';
  var icoChain = '<svg width="16" height="16" viewBox="0 0 18 18" aria-hidden="true"><rect x="2" y="2.5" width="14" height="3" rx="1.2" fill="currentColor"/><rect x="2" y="7.5" width="14" height="3" rx="1.2" fill="currentColor" opacity=".75"/><rect x="2" y="12.5" width="14" height="3" rx="1.2" fill="currentColor" opacity=".5"/></svg>';
  function item(href, ico, name, cn, tw, on) {
    return '<a href="' + href + '"' + (on ? ' aria-current="page"' : "") + ">" + ico + name +
      '<small><span class="t-cn">' + cn + '</span><span class="t-tw">' + tw + "</span></small></a>";
  }
  var bar = document.createElement("nav");
  bar.id = "aps";
  bar.setAttribute("aria-label", "April's");
  bar.innerHTML = '<div class="aps-in"><span class="aps-b">April’s</span><div class="aps-seg">' +
    item("/", icoChain, "Supply Chain", "AI 产业链", "AI 產業鏈", cur === "chain") +
    item("/insider/", icoInsider, "Insider Flow", "内部人动向", "內部人動向", cur === "ins") +
    item("/earnings/", icoEarnings, "Earnings Lens", "财报解读", "財報解讀", cur === "earn") +
    "</div></div>";
  var me = document.currentScript;
  if (me && me.parentNode) me.parentNode.insertBefore(bar, me.nextSibling);
  else document.body.insertBefore(bar, document.body.firstChild);
  /* line the bar up with the page's own content column (both sites use .wrap) */
  function align() {
    var w = document.querySelector("body .wrap:not(#aps .wrap)"), inner = bar.firstChild;
    if (!w || innerWidth <= 400) { inner.style.paddingLeft = ""; return; }
    var r = w.getBoundingClientRect(), cs = getComputedStyle(w);
    inner.style.paddingLeft = Math.max(16, Math.round(r.left + parseFloat(cs.paddingLeft || 0))) + "px";
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", align); else align();
  addEventListener("resize", align);
})();
