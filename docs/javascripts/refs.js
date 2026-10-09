/* Hover cards for [[mentions]]. Card HTML is embedded in each page at build time
   (a JSON block with id "ref-data"), so this works offline. */
(function () {
  function init() {
    var dataEl = document.getElementById("ref-data");
    if (!dataEl || document.querySelector(".ref-card")) return;
    var cards = JSON.parse(dataEl.textContent);
    var box = document.createElement("div");
    box.className = "ref-card";
    box.hidden = true;
    document.body.appendChild(box);
    var hideTimer = null;

    function show(a) {
      var content = cards[a.getAttribute("data-ref")];
      if (!content) return;
      clearTimeout(hideTimer);
      box.innerHTML = content;
      box.hidden = false;
      var r = a.getBoundingClientRect();
      var w = box.offsetWidth, h = box.offsetHeight;
      var maxLeft = document.documentElement.clientWidth - w - 12;
      var left = Math.max(8, Math.min(r.left, maxLeft));
      var top = r.bottom + 6;
      if (r.bottom + h + 12 > window.innerHeight && r.top > h + 12) top = r.top - h - 6;  // flip above
      box.style.left = (window.scrollX + left) + "px";
      box.style.top = (window.scrollY + top) + "px";
    }
    function hideSoon() {
      hideTimer = setTimeout(function () { box.hidden = true; }, 150);
    }
    // Listened for on the whole page, so links drawn after it loads (the Party page's cards) work too.
    function refOf(ev) { return ev.target.closest && ev.target.closest("a.ref"); }
    document.addEventListener("mouseover", function (ev) {
      var a = refOf(ev);
      if (a && !(ev.relatedTarget && a.contains(ev.relatedTarget))) show(a);
    });
    document.addEventListener("mouseout", function (ev) {
      var a = refOf(ev);
      if (a && !(ev.relatedTarget && a.contains(ev.relatedTarget))) hideSoon();
    });
    document.addEventListener("focusin", function (ev) { var a = refOf(ev); if (a) show(a); });
    document.addEventListener("focusout", function (ev) { if (refOf(ev)) hideSoon(); });
    // Moving the mouse onto the card keeps it open (for scrolling long item text).
    box.addEventListener("mouseenter", function () { clearTimeout(hideTimer); });
    box.addEventListener("mouseleave", hideSoon);
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
