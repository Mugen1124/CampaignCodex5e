/* "View as…", top right of the DM site: the players' site as one player sees it - their own card editable,
   everything else as they'd find it - so you can show a player how to do something, or do it for them.
   It opens <the DM site online>/as/<their card's id>/ in a new tab (publish/dm/worker.js), where a banner
   says whose eyes these are; anything changed there is saved as that player, and their card's history
   says it was you. Only on the DM site, and only once it's online with the players' site behind it
   (hooks/campaign.py puts the address and the party in the page). */
(function () {
  "use strict";
  var ONLINE = location.protocol !== "file:" && !/^(127\.0\.0\.1|localhost|\[::1\])$/.test(location.hostname);

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }
  function init() {
    var meta = document.querySelector('meta[name="codex-view-as"]');
    var spot = document.querySelector(".md-header__inner .md-search") || document.querySelector(".md-header__inner");
    if (!meta || !spot || document.querySelector(".va")) return;
    var cfg;
    try { cfg = JSON.parse(meta.content); } catch (e) { return; }
    // Online, the DM site itself; at home, the DM site online (none: not online yet, so nothing to show).
    var base = ONLINE ? "/" : cfg.url;
    if (!base) return;
    if (ONLINE) {
      // Only where the DM site has its live line to the players' site (an older publish doesn't).
      fetch("/api/me").then(function (r) { if (r.ok && /json/.test(r.headers.get("Content-Type") || "")) draw(); }).catch(function () {});
    } else draw();

    function draw() {
      var box = document.createElement("div");
      box.className = "va";
      box.innerHTML = '<button class="va-btn" type="button" aria-haspopup="true" aria-expanded="false" title="See the players\' site as one of them">' +
        "View as…</button>" +
        '<div class="va-menu" role="menu" hidden><div class="va-head">The players\' site, as…</div>' +
        (cfg.party || []).map(function (p) {
          return '<a role="menuitem" data-as="' + esc(p[0]) + '">' + esc(p[1]) + "</a>";
        }).join("") +
        '<a role="menuitem" data-as="players" title="Signed in, but without a character">Any player</a>' +
        '<div class="va-foot">Opens in a new tab. Changes you make there are saved as them.</div></div>';
      spot.parentNode.insertBefore(box, spot);
      var btn = box.querySelector(".va-btn"), menu = box.querySelector(".va-menu");
      function show(open) { menu.hidden = !open; btn.setAttribute("aria-expanded", open ? "true" : "false"); }
      btn.addEventListener("click", function (ev) { ev.stopPropagation(); show(menu.hidden); });
      document.addEventListener("click", function (ev) { if (!box.contains(ev.target)) show(false); });
      document.addEventListener("keydown", function (ev) { if (ev.key === "Escape") show(false); });
      menu.addEventListener("click", function (ev) {
        var a = ev.target.closest("[data-as]");
        if (!a) return;
        // The same page on the players' site (the worker falls back to its home page if they don't have it).
        var page = location.pathname.replace(/^\//, "") + location.hash;
        window.open(base.replace(/\/?$/, "/") + "as/" + a.getAttribute("data-as") + "/" + page, "_blank", "noopener");
        show(false);
      });
    }
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
