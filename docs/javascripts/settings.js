/* The settings menu: a cog at the top right of every page, on both sites. Its sections:
     Colours   - the site's palette for this browser, starting from the campaign's (campaign.yml palette:);
                 theme.css has them, and hooks/campaign.py puts the choice on the page before it draws
     Text size - smaller, normal or larger, for this browser
     View as…  - DM site only (javascripts/view-as.js adds it)
     Guide     - DM site only: the engine's guide
   Other scripts add a section with window.codexSettings.section(title, order). */
(function () {
  "use strict";
  var CAMPAIGN = (document.querySelector('meta[name="codex-campaign"]') || {}).content || "codex";
  var PALETTE_KEY = CAMPAIGN + "-palette", TEXT_KEY = CAMPAIGN + "-text";
  var DEFAULT = (document.querySelector('meta[name="codex-palette"]') || {}).content || "original";
  var DM = !!document.querySelector('meta[name="codex-view-as"]');
  // [id, name, page, panel, accent] - the chips are drawn from these; the colours themselves are in theme.css.
  var PALETTES = [
    ["original", "Original", "#101010", "#212a2e", "#d0a650"],
    ["abyss", "Abyss", "#081112", "#122325", "#8fc1c9"],
    ["ember", "Ember", "#120e0b", "#241c16", "#d98c3a"],
    ["arcane", "Arcane", "#0e0c14", "#1c1828", "#b48cf0"],
  ];
  var COG = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12,15.5A3.5,3.5 0 0,1 8.5,12A3.5,3.5 0 0,1 12,8.5A3.5,3.5 0 0,1 15.5,12A3.5,3.5 0 0,1 12,15.5M19.43,12.97C19.47,12.65 19.5,12.33 19.5,12C19.5,11.67 19.47,11.34 19.43,11L21.54,9.37C21.73,9.22 21.78,8.95 21.66,8.73L19.66,5.27C19.54,5.05 19.27,4.96 19.05,5.05L16.56,6.05C16.04,5.66 15.5,5.32 14.87,5.07L14.5,2.42C14.46,2.18 14.25,2 14,2H10C9.75,2 9.54,2.18 9.5,2.42L9.13,5.07C8.5,5.32 7.96,5.66 7.44,6.05L4.95,5.05C4.73,4.96 4.46,5.05 4.34,5.27L2.34,8.73C2.21,8.95 2.27,9.22 2.46,9.37L4.57,11C4.53,11.34 4.5,11.67 4.5,12C4.5,12.33 4.53,12.65 4.57,12.97L2.46,14.63C2.27,14.78 2.21,15.05 2.34,15.27L4.34,18.73C4.46,18.95 4.73,19.03 4.95,18.95L7.44,17.94C7.96,18.34 8.5,18.68 9.13,18.93L9.5,21.58C9.54,21.82 9.75,22 10,22H14C14.25,22 14.46,21.82 14.5,21.58L14.87,18.93C15.5,18.67 16.04,18.34 16.56,17.94L19.05,18.95C19.27,19.03 19.54,18.95 19.66,18.73L21.66,15.27C21.78,15.05 21.73,14.78 21.54,14.63L19.43,12.97Z"/></svg>';

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }
  function get(key) { try { return localStorage.getItem(key) || ""; } catch (e) { return ""; } }
  function put(key, value) { try { if (value) localStorage.setItem(key, value); else localStorage.removeItem(key); } catch (e) {} }
  function attr(name, value) {
    if (value) document.documentElement.setAttribute(name, value);
    else document.documentElement.removeAttribute(name);
  }
  function palette() { return get(PALETTE_KEY) || DEFAULT; }
  // id "" = back to the campaign's colours
  function setPalette(id) {
    put(PALETTE_KEY, id);
    var now = id || DEFAULT;
    attr("data-cx-palette", now === "original" ? "" : now);
  }

  var box, menu, btn;
  var sections = [];
  function section(title, order) {
    var el = document.createElement("div");
    el.className = "cx-set-sec";
    el.innerHTML = '<div class="cx-set-head">' + esc(title) + '</div><div class="cx-set-body"></div>';
    var at = { el: el, order: order == null ? 50 : order };
    sections.push(at);
    sections.sort(function (a, b) { return a.order - b.order; });
    if (menu) {
      var next = sections[sections.indexOf(at) + 1];
      menu.insertBefore(el, next ? next.el : null);
    }
    return el.querySelector(".cx-set-body");
  }
  function show(open) {
    menu.hidden = !open;
    btn.setAttribute("aria-expanded", open ? "true" : "false");
  }
  function close() { show(false); }

  function init() {
    var spot = document.querySelector(".md-header__inner .md-search") || document.querySelector(".md-header__inner");
    if (!spot || document.querySelector(".cx-set")) return;
    box = document.createElement("div");
    box.className = "cx-set";
    box.innerHTML = '<button class="cx-set-btn" type="button" aria-haspopup="true" aria-expanded="false" title="Settings">' + COG + "</button>" +
      '<div class="cx-set-menu" role="menu" hidden></div>';
    spot.parentNode.insertBefore(box, spot);
    btn = box.querySelector(".cx-set-btn");
    menu = box.querySelector(".cx-set-menu");
    sections.forEach(function (s) { menu.appendChild(s.el); });
    btn.addEventListener("click", function (ev) { ev.stopPropagation(); show(menu.hidden); });
    document.addEventListener("click", function (ev) { if (!box.contains(ev.target)) close(); });
    document.addEventListener("keydown", function (ev) { if (ev.key === "Escape") close(); });

    // ---------------------------------------------------------------- Colours
    var colours = section("Colours", 10);
    colours.innerHTML = '<div class="cx-pal">' + PALETTES.map(function (p) {
      return '<button type="button" class="cx-pal-opt" data-pal="' + p[0] + '" title="' + esc(p[1]) + '">' +
        '<span class="cx-pal-chip" style="background:' + p[2] + '"><span style="background:' + p[3] + '"></span>' +
        '<span style="background:' + p[4] + '"></span></span>' + esc(p[1]) + "</button>";
    }).join("") + '</div><div class="cx-set-note"></div>';
    var campaignName = (PALETTES.filter(function (p) { return p[0] === DEFAULT; })[0] || PALETTES[0])[1];
    function mark() {
      var cur = palette();
      colours.querySelectorAll(".cx-pal-opt").forEach(function (b) {
        b.classList.toggle("cx-on", b.getAttribute("data-pal") === cur);
      });
      colours.querySelector(".cx-set-note").innerHTML = get(PALETTE_KEY) && get(PALETTE_KEY) !== DEFAULT
        ? "For this browser only. <a class=\"cx-set-link\" data-pal=\"\">Back to the campaign's (" + esc(campaignName) + ")</a>"
        : "For this browser only. The campaign's colours: " + esc(campaignName) + ".";
    }
    colours.addEventListener("click", function (ev) {
      var b = ev.target.closest("[data-pal]");
      if (!b) return;
      setPalette(b.getAttribute("data-pal"));
      mark();
    });
    mark();

    // ---------------------------------------------------------------- Text size
    var sizes = section("Text size", 15);
    sizes.innerHTML = '<div class="cx-seg">' + [["small", "Smaller"], ["", "Normal"], ["large", "Larger"]].map(function (s) {
      return '<button type="button" data-text="' + s[0] + '">' + s[1] + "</button>";
    }).join("") + "</div>";
    function markText() {
      var cur = get(TEXT_KEY);
      sizes.querySelectorAll("[data-text]").forEach(function (b) { b.classList.toggle("cx-on", b.getAttribute("data-text") === cur); });
    }
    sizes.addEventListener("click", function (ev) {
      var b = ev.target.closest("[data-text]");
      if (!b) return;
      put(TEXT_KEY, b.getAttribute("data-text"));
      attr("data-cx-text", b.getAttribute("data-text"));
      markText();
    });
    markText();

    // ---------------------------------------------------------------- Guide (DM site)
    if (DM) {
      var guide = section("Help", 90);
      var href = new URL("guide/index.html", window.__md_scope || new URL(".", location)).href;
      guide.innerHTML = '<div class="cx-va"><a href="' + esc(href) + '">The guide - how everything works</a></div>';
    }
  }

  window.codexSettings = { section: section, close: close };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
