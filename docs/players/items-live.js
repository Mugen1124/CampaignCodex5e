/* Players' site, Items page: "Claim" on each item that's up for grabs (found, nobody's yet).
 * A claim goes to the players' worker (publish/players/worker.js); the DM approves it at home, and
 * the item shows on that character's card once the site is next updated. Players see who else has
 * asked for an item, and can take their own claim back while it's waiting. */
(function () {
  var spots = Array.from(document.querySelectorAll(".item-claim[data-item]"));
  if (!spots.length) return;

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }
  function get(url) { return fetch(url, { cache: "no-store" }).then(function (r) { return r.ok ? r.json() : {}; }); }
  var me = {}, claims = [];

  function render() {
    spots.forEach(function (spot) {
      var id = spot.getAttribute("data-item");
      var here = claims.filter(function (c) { return c.item === id; });
      var mine = me.character && here.filter(function (c) { return c.character === me.character; })[0];
      var others = here.filter(function (c) { return c !== mine && c.status === "pending"; })
        .map(function (c) { return esc(c.character); });
      var html = "";
      if (mine && mine.status === "pending") {
        html = '<span class="item-claim-status">You asked for it — waiting for the DM.</span> ' +
               '<button type="button" class="item-claim-undo" data-act="withdraw">Take it back</button>';
      } else if (mine && mine.status === "approved") {
        html = '<span class="item-claim-status">Yours — it shows on your card once the site is next updated.</span>';
      } else if (me.character) {
        html = (mine && mine.status === "rejected" ? '<span class="item-claim-status">The DM gave it elsewhere.</span> ' : "") +
               '<button type="button" data-act="claim">Claim for ' + esc(me.character) + "</button>";
      }
      if (others.length) html += '<span class="item-claim-others">Also asked: ' + others.join(", ") + "</span>";
      spot.innerHTML = html;
    });
  }
  function load() {
    return Promise.all([get("/api/me"), get("/api/items/claims")]).then(function (res) {
      me = res[0] || {};
      claims = (res[1] && res[1].claims) || [];
      render();
    }).catch(function () {});
  }
  document.addEventListener("click", function (ev) {
    var act = ev.target.getAttribute && ev.target.getAttribute("data-act");
    var spot = act && ev.target.closest(".item-claim[data-item]");
    if (!spot) return;
    ev.target.disabled = true;
    fetch("/api/items/claim", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ item: spot.getAttribute("data-item"), withdraw: act === "withdraw" }) })
      .then(function (r) { return r.json().then(function (j) { return { ok: r.ok, body: j }; }); })
      .then(function (res) {
        if (!res.ok) { spot.innerHTML = '<span class="item-claim-status">' + esc(res.body.error || "Couldn't do that.") + "</span>"; return; }
        return load();
      }).catch(function () { ev.target.disabled = false; });
  });
  load();
})();
