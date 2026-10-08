/* The Spells and Magic Items pages' filter: text, dropdowns (level, class, school, rarity, type) and
   checkboxes (concentration, ritual, attunement). Entries are <div class="rules-entry <kind>"> blocks
   with data- attributes, written by codex/rules.py; headings with nothing left under them are hidden. */
(function () {
  function init() {
    document.querySelectorAll(".rules-filter").forEach(function (bar) {
      var kind = bar.getAttribute("data-for");
      var entries = Array.prototype.slice.call(document.querySelectorAll(".rules-entry." + kind));
      if (!entries.length) return;
      var text = bar.querySelector(".rf-text");
      var sels = Array.prototype.slice.call(bar.querySelectorAll(".rf-sel"));
      var checks = Array.prototype.slice.call(bar.querySelectorAll("input[type=checkbox]"));
      var count = bar.querySelector(".rf-count");
      var content = bar.closest("article") || document.body;
      var heads = Array.prototype.slice.call(content.querySelectorAll("h2"));

      function apply() {
        var q = (text.value || "").trim().toLowerCase();
        var shown = 0;
        entries.forEach(function (e) {
          var ok = !q || e.getAttribute("data-name").indexOf(q) >= 0 || e.textContent.toLowerCase().indexOf(q) >= 0;
          sels.forEach(function (s) {
            if (!ok || !s.value) return;
            var have = (e.getAttribute("data-" + s.getAttribute("data-key")) || "").split(" ");
            ok = have.indexOf(s.value) >= 0 || (s.getAttribute("data-key") !== "classes" && have.join(" ") === s.value);
          });
          checks.forEach(function (c) {
            if (ok && c.checked) ok = e.getAttribute("data-" + c.getAttribute("data-key")) === "1";
          });
          e.hidden = !ok;
          if (ok) shown++;
        });
        // a heading stays only while something under it (before the next heading) is showing
        heads.forEach(function (h) {
          var n = h.nextElementSibling, any = false, isGroup = false;
          while (n && n.tagName !== "H2") {
            if (n.classList && n.classList.contains("rules-entry")) { isGroup = true; if (!n.hidden) any = true; }
            n = n.nextElementSibling;
          }
          if (isGroup) h.hidden = !any;
        });
        count.textContent = shown === entries.length ? entries.length + " in all" : shown + " of " + entries.length;
      }
      text.addEventListener("input", apply);
      sels.concat(checks).forEach(function (el) { el.addEventListener("change", apply); });
      apply();
    });
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
