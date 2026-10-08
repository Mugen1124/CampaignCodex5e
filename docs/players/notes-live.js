/* Players' site, My Notes: one private notepad per signed-in player, kept by the players' worker
 * (publish/players/worker.js, /api/notes). It saves a moment after typing stops, when the page is
 * left, and before it closes. Each save says which version it started from; if the notes were
 * changed on another device in the meantime, nothing is overwritten - the player chooses. */
(function () {
  var box = document.querySelector(".player-notes");
  if (!box) return;

  var MAX = 100000;           // bytes, as the worker allows
  var rev = 0, saved = "", timer = null, busy = false, again = false;
  var area, status;

  function bytes(s) { return new TextEncoder().encode(s).length; }
  function when(iso) {
    if (!iso) return "";
    var d = new Date(iso);
    return d.toLocaleDateString(undefined, { month: "short", day: "numeric" }) + ", " +
           d.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
  }
  function say(text, kind) {
    status.textContent = text;
    status.className = "pn-status" + (kind ? " pn-" + kind : "");
  }
  function dirty() { return area && area.value !== saved; }

  function unavailable() {
    box.innerHTML = '<p class="pn-wait">Your notes live on the online players\' site — open it there to read and write them.</p>';
  }

  function build(note) {
    box.innerHTML = '<textarea class="pn-text" spellcheck="true" aria-label="My notes" ' +
      'placeholder="Names, clues, plans, who owes you money…"></textarea>' +
      '<div class="pn-bar"><span class="pn-status"></span><span class="pn-count"></span></div>' +
      '<div class="pn-conflict" hidden></div>';
    area = box.querySelector(".pn-text");
    status = box.querySelector(".pn-status");
    take(note);
    area.addEventListener("input", function () {
      count();
      say("Not saved yet…");
      clearTimeout(timer);
      timer = setTimeout(save, 1200);
    });
    area.addEventListener("blur", function () { if (dirty()) save(); });
  }

  function take(note) {
    rev = note.rev || 0;
    saved = note.text || "";
    area.value = saved;
    count();
    say(note.saved ? "Saved " + when(note.saved) : "Nothing here yet — start typing.");
  }

  function count() {
    var b = bytes(area.value), el = box.querySelector(".pn-count");
    el.textContent = b > MAX * 0.8 ? Math.round(b / 1000) + "k of " + MAX / 1000 + "k" : "";
    el.className = "pn-count" + (b > MAX ? " pn-bad" : "");
  }

  function save() {
    clearTimeout(timer);
    if (!dirty()) return;
    if (busy) { again = true; return; }
    if (bytes(area.value) > MAX) { say("Too long to save — trim some notes first.", "bad"); return; }
    busy = true;
    var text = area.value;
    say("Saving…");
    fetch("/api/notes", { method: "PUT", headers: { "Content-Type": "application/json" },
                          body: JSON.stringify({ text: text, rev: rev }), keepalive: bytes(text) < 60000 })
      .then(function (r) { return r.json().then(function (j) { return { status: r.status, body: j }; }); })
      .then(function (res) {
        if (res.status === 409) { conflict(res.body); return; }
        if (res.status !== 200) { say(res.body.error || "Couldn't save — your notes are still here; it'll try again.", "bad"); return; }
        rev = res.body.rev;
        saved = text;
        say(dirty() ? "Not saved yet…" : "Saved " + when(res.body.saved));
      })
      .catch(function () { say("Couldn't save — check your connection. Your notes are still here; it'll try again.", "bad"); })
      .then(function () {
        busy = false;
        if (again || dirty()) { again = false; timer = setTimeout(save, 3000); }
      });
  }

  // Saved from another device since this page loaded them: show both choices, overwrite nothing.
  function conflict(theirs) {
    clearTimeout(timer);
    var c = box.querySelector(".pn-conflict");
    c.hidden = false;
    c.innerHTML = '<p>These notes were changed on another device (' + when(theirs.saved) + ') since you opened this page.</p>' +
      '<button type="button" data-pn="theirs">Load the newer notes</button> ' +
      '<button type="button" data-pn="mine">Keep what\'s here</button>';
    say("Not saved — choose which notes to keep.", "bad");
    c.onclick = function (ev) {
      var pick = ev.target.getAttribute && ev.target.getAttribute("data-pn");
      if (!pick) return;
      c.hidden = true;
      if (pick === "theirs") { take(theirs); return; }
      rev = theirs.rev;      // overwrite the newer version with what's on this screen
      saved = theirs.text || "";
      if (dirty()) save(); else say("Saved " + when(theirs.saved));
    };
  }

  // Back on this tab (another device may have saved meanwhile): pick up newer notes if nothing's typed here.
  document.addEventListener("visibilitychange", function () {
    if (!area) return;
    if (document.visibilityState === "hidden") { if (dirty()) save(); return; }
    if (dirty() || busy) return;
    fetch("/api/notes", { cache: "no-store" }).then(function (r) { return r.ok ? r.json() : null; }).then(function (n) {
      if (n && n.rev !== rev && !dirty()) take(n);
    }).catch(function () {});
  });
  window.addEventListener("beforeunload", function (ev) {
    if (!dirty()) return;
    save();
    ev.preventDefault();
    ev.returnValue = "";
  });

  fetch("/api/notes", { cache: "no-store" })
    .then(function (r) {
      var json = (r.headers.get("Content-Type") || "").indexOf("application/json") >= 0;
      if (!json) return null;
      return r.json().then(function (j) { return { ok: r.ok, body: j }; });
    })
    .then(function (res) {
      if (!res) { unavailable(); return; }
      if (!res.ok) { box.innerHTML = '<p class="pn-wait"></p>'; box.firstChild.textContent = res.body.error || "Couldn't open your notes."; return; }
      build(res.body);
    })
    .catch(unavailable);
})();
