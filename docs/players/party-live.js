/* Players' site, Party page: the cards live from the players' worker (publish/players/worker.js).
 * Everyone sees the party's latest cards - other players' without what they marked private - and the
 * page redraws by itself when any card changes (a WebSocket that says "changed").
 * On your own card: Edit (javascripts/card-form.js - all of it but the name), Import .ccc5e (an export from the CCC5e character builder; a preview of what
 * changes first, the portrait shrunk to 320 px here before it's sent) and Privacy (what only you and
 * the DM see). Changes go live at once; the DM keeps a history of them and can undo any.
 * party-cards.js draws the cards; this gives it the live ones (window.codexParty.draw). Opened from
 * disk, or with the worker out of reach, the page keeps the cards it was built with. */
(function () {
  "use strict";
  if (location.protocol === "file:") return;

  // What a player may mark private (publish/players/party.mjs PRIVATE_PATHS), as the card names them.
  var PRIVATE = [["persona.traits", "Personality"], ["persona.ideal", "Ideal"], ["persona.bond", "Bond"], ["persona.flaw", "Flaw"],
    ["persona.appearance", "Appearance"], ["persona.alignment", "Alignment"], ["persona.allies", "Allies"], ["persona.deity", "Deity"],
    ["persona.backstory", "Backstory"], ["skills", "Skills"], ["saves", "Saving throws"], ["senses", "Senses"], ["languages", "Languages"],
    ["resistances", "Damage resistances"], ["immunities", "Damage immunities"], ["condition_immunities", "Condition immunities"],
    ["proficiencies", "Proficiencies"], ["features", "Features & traits"], ["actions", "Actions"], ["bonus_actions", "Bonus actions"],
    ["reactions", "Reactions"], ["spellcasting", "Spellcasting"], ["currency", "Money"], ["inventory", "The whole inventory"],
    ["portrait", "Portrait"]];
  var LABEL = { hp: "HP", ac: "AC", ac_note: "AC note", hp_formula: "HP formula", passive_perception: "passive Perception" };
  var PORTRAIT_PX = 320;

  var root, base, live = null, ws = null, retry = 1000, pinger = null, busy = false, stale = false, timer = null;

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }
  function post(path, body) {
    return fetch(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) })
      .then(function (r) { return r.json().catch(function () { return {}; }).then(function (j) { return { status: r.status, body: j }; }); });
  }

  // ------------------------------------------------------------ the live cards
  function load() {
    return fetch("/api/party", { cache: "no-store" }).then(function (r) { return r.ok ? r.json() : null; }).then(function (p) {
      if (!p || !Array.isArray(p.cards)) return;
      live = p;
      if (busy) { stale = true; return; }   // not while a preview or the privacy list is open - after it
      draw();
    }).catch(function () {});
  }
  function draw() {
    stale = false;
    var cards = live.cards.slice().sort(function (a, b) { return a.index - b.index; });
    window.codexParty.draw(Object.assign({}, base, { cards: cards, me: live.me, live: true }));
  }
  function soon() {   // several changes at once fetch once
    clearTimeout(timer);
    timer = setTimeout(load, 250);
  }

  function connect() {
    if (ws && (ws.readyState === 0 || ws.readyState === 1)) return;
    try {
      ws = new WebSocket((location.protocol === "https:" ? "wss://" : "ws://") + location.host + "/api/party/ws");
    } catch (e) { return later(); }
    ws.onopen = function () {
      retry = 1000;
      clearInterval(pinger);
      pinger = setInterval(function () { if (ws.readyState === 1) ws.send("ping"); }, 25000);
    };
    ws.onmessage = function (ev) { if (ev.data !== "pong") soon(); };
    ws.onclose = function () {
      clearInterval(pinger);
      later();
    };
  }
  function later() {
    setTimeout(function () { soon(); connect(); }, retry);   // and catch up on what was missed meanwhile
    retry = Math.min(retry * 2, 15000);
  }

  // ------------------------------------------------------------ your own card
  function mine() {
    return live && live.me ? live.cards.filter(function (c) { return c.id === live.me; })[0] : null;
  }
  function tools() {
    var c = mine();
    if (!c) return;
    var slot = root.querySelector('section.pcx[data-pc="' + c.index + '"]');
    if (!slot || slot.querySelector(".pl-tools")) return;
    var bar = document.createElement("div");
    bar.className = "eb eb-sbbar pl-tools";
    bar.innerHTML = '<span class="pl-msg"></span><button class="eb-act" data-pl="edit" title="Change anything on your card">Edit</button>' +
      '<button class="eb-act" data-pl="import" title="Update your card from a CCC5e export">Import .ccc5e</button>' +
      '<button class="eb-act" data-pl="privacy" title="Choose what only you and the DM see">Privacy</button>';
    slot.insertBefore(bar, slot.firstChild);
  }
  function say(html, kind) {
    var el = root.querySelector(".pl-tools .pl-msg");
    if (el) el.innerHTML = html ? '<span class="eb-msg eb-' + (kind || "info") + '">' + html + "</span>" : "";
  }
  // A panel inside your card (an import preview, or the privacy list); the page waits to redraw until it closes.
  function panel(html, whole) {
    closePanel();
    var c = mine(), slot = c && root.querySelector('section.pcx[data-pc="' + c.index + '"]');
    if (!slot) return null;
    var box = document.createElement("div");
    box.className = "eb pl-panel pe-import-box";
    if (whole) slot.classList.add("pl-editing");   // the form stands in for the card while it's open
    box.innerHTML = html;
    var at = slot.querySelector(".pcx-strip");
    slot.insertBefore(box, at || null);
    busy = true;
    box.scrollIntoView({ behavior: "smooth", block: "center" });
    return box;
  }
  function closePanel() {
    var old = root.querySelector(".pl-panel");
    if (old) old.remove();
    root.querySelectorAll(".pl-editing").forEach(function (s) { s.classList.remove("pl-editing"); });
    busy = false;
    if (stale && live) draw();
  }

  // The portrait in a CCC5e export, made small enough to keep (it's shown at 4 rem; 320 px covers sharp screens).
  function shrink(dataUrl) {
    return new Promise(function (done) {
      if (!/^data:image\//.test(dataUrl || "")) return done(dataUrl);
      var img = new Image();
      img.onload = function () {
        var k = Math.min(1, PORTRAIT_PX / Math.max(img.width, img.height));
        var cv = document.createElement("canvas");
        cv.width = Math.max(1, Math.round(img.width * k));
        cv.height = Math.max(1, Math.round(img.height * k));
        cv.getContext("2d").drawImage(img, 0, 0, cv.width, cv.height);
        done(cv.toDataURL("image/jpeg", 0.85));
      };
      img.onerror = function () { done(""); };
      img.src = dataUrl;
    });
  }
  function importFile() {
    var input = document.createElement("input");
    input.type = "file";
    input.accept = ".ccc5e,.json";
    input.addEventListener("change", function () {
      var file = input.files && input.files[0];
      if (!file) return;
      file.text().then(function (text) {
        var data;
        try { data = JSON.parse(text); } catch (e) { return say(esc(file.name) + " isn't a CCC5e character file.", "warn"); }
        var sheet = data && data.Sheet;
        return shrink(sheet && sheet.portrait).then(function (pic) {
          if (sheet && sheet.portrait) sheet.portrait = pic;
          var d = new Date(), today = d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") + "-" + String(d.getDate()).padStart(2, "0");
          var req = { file: JSON.stringify(data), name: file.name, today: today };
          return post("/api/party/import", req).then(function (res) {
            if (res.status !== 200) return say(esc(res.body.error || "Couldn't read that file."), "warn");
            preview(req, res.body);
          });
        });
      }).catch(function () { say("Couldn't reach the site - check your connection and try again.", "warn"); });
    });
    input.click();
  }
  function preview(req, p) {
    var rows = (p.changes || []).map(function (c) {
      return "<tr><td>" + esc(LABEL[c[0]] || String(c[0]).replace(/_/g, " ")) + '</td><td class="pe-old">' + esc(c[1]) + '</td><td class="pe-new">' + esc(c[2]) + "</td></tr>";
    }).join("");
    var named = p.file && p.file !== p.character ? " (the file says " + esc(p.file) + "; your card keeps its name)" : "";
    var box = panel('<p class="pe-sug-title">Update ' + esc(p.character) + " from " + esc(req.name) + "</p>" +
      '<p class="eb-hint">' + (p.portrait ? "With its portrait." : "No portrait in the file - your card keeps the one it has.") + named + "</p>" +
      (p.has_sheet ? "" : '<div class="eb-msg eb-warn">This file is from CCC5e before 1.0.21: only the race, class and level come in. ' +
        "Export it again from a newer CCC5e for the whole card.</div>") +
      (rows ? '<table class="pe-sug-table"><tr><th>What</th><th>Now</th><th>After the import</th></tr>' + rows + "</table>"
        : '<p class="eb-hint">Nothing changes.</p>') +
      '<p class="eb-hint">Kept as they are: your name, and what you\'ve marked private. Everyone sees the new card at once; the DM can undo it.</p>' +
      '<div class="pe-sug-act"><button class="md-button md-button--primary" data-pl="import-save">Save the import</button>' +
      '<button class="md-button" data-pl="close">Cancel</button></div>');
    if (!box) return;
    box.querySelector('[data-pl="import-save"]').addEventListener("click", function (ev) {
      ev.target.disabled = true;
      post("/api/party/import", Object.assign({}, req, { save: true, rev: mine().rev })).then(function (res) {
        if (res.status !== 200) { ev.target.disabled = false; return say(esc(res.body.error || "Couldn't save it."), "warn"); }
        closePanel();
        load().then(function () { say("Your card is updated.", "ok"); });
      }).catch(function () { ev.target.disabled = false; say("Couldn't reach the site - check your connection and try again.", "warn"); });
    });
  }

  function privacy() {
    var c = mine(), p = c.persona || {};
    var marked = c.private || [];
    var has = function (path) {
      var bits = path.split(".");
      var v = bits.length > 1 ? p[bits[1]] : c[path];
      return v != null && v !== "" && !(Array.isArray(v) && !v.length) && !(typeof v === "object" && !Array.isArray(v) && !Object.keys(v).length);
    };
    var opts = PRIVATE.filter(function (f) { return has(f[0]) || marked.indexOf(f[0]) >= 0; }).map(function (f) {
      return '<label class="pl-opt"><input type="checkbox" data-path="' + esc(f[0]) + '"' + (marked.indexOf(f[0]) >= 0 ? " checked" : "") + "> " + esc(f[1]) + "</label>";
    }).join("");
    var items = (c.inventory || []).map(function (i) {
      return '<label class="pl-opt"><input type="checkbox" data-item="' + esc(i.name) + '"' + (i.private ? " checked" : "") + "> " +
        esc(i.name) + (i.qty && i.qty !== 1 ? " ×" + esc(i.qty) : "") + "</label>";
    }).join("");
    var box = panel('<p class="pe-sug-title">What only you and the DM see</p>' +
      '<p class="eb-hint">Ticked parts of your card are hidden from the other players. The DM always sees your whole card.</p>' +
      '<div class="pl-opts">' + opts + "</div>" +
      (items ? '<p class="pe-sug-title pl-sub">Items to keep to yourself</p><div class="pl-opts">' + items + "</div>" : "") +
      '<div class="pe-sug-act"><button class="md-button md-button--primary" data-pl="privacy-save">Save</button>' +
      '<button class="md-button" data-pl="close">Cancel</button></div>');
    if (!box) return;
    box.querySelector('[data-pl="privacy-save"]').addEventListener("click", function (ev) {
      var paths = [], hidden = [];
      box.querySelectorAll("input[data-path]:checked").forEach(function (x) { paths.push(x.getAttribute("data-path")); });
      box.querySelectorAll("input[data-item]:checked").forEach(function (x) { hidden.push(x.getAttribute("data-item")); });
      ev.target.disabled = true;
      post("/api/party/private", { "private": paths, hidden: hidden, rev: mine().rev }).then(function (res) {
        if (res.status !== 200) { ev.target.disabled = false; return say(esc(res.body.error || "Couldn't save that."), "warn"); }
        closePanel();
        load().then(function () { say("Saved. 🔒 marks what the others don't see.", "ok"); });
      }).catch(function () { ev.target.disabled = false; say("Couldn't reach the site - check your connection and try again.", "warn"); });
    });
  }

  // ------------------------------------------------------------ Edit: your card in a form
  // The same form as the DM's (javascripts/card-form.js), less the name, player, email and DM note.
  // Kept in this browser as you type, in case the page reloads; Save puts it live (the DM can undo it).
  var draft = null;   // the card as the form has it

  function draftKey() { return "codex-party-edit:" + location.pathname + ":" + (live && live.me); }
  function keepDraft() { try { localStorage.setItem(draftKey(), JSON.stringify(draft)); } catch (e) {} }
  function dropDraft() { try { localStorage.removeItem(draftKey()); } catch (e) {} }

  function edit() {
    var c = mine(), form = window.codexCardForm;
    if (!c || !form) return;
    var saved = null;
    try { saved = JSON.parse(localStorage.getItem(draftKey()) || "null"); } catch (e) {}
    draft = saved && saved.rev === c.rev && saved._cast ? saved : form.draft(c);
    var box = panel('<div class="eb-cf-head"><span class="eb-cf-title">Editing ' + esc(c.character) + "</span>" +
      '<span class="eb-cf-btns"><button type="button" class="md-button md-button--primary" data-pl="edit-save">Save</button>' +
      '<button type="button" class="md-button" data-pl="edit-cancel">Cancel</button></span></div>' +
      '<p class="eb-hint">Everyone sees your card as soon as you save (except what you\'ve marked private). The DM can undo any change. ' +
      "To change your character's name, ask the DM.</p>" +
      '<div class="pl-form-body">' + form.html(draft) + "</div>" +
      '<div class="eb-cf-btns pl-edit-foot"><button type="button" class="md-button md-button--primary" data-pl="edit-save">Save</button>' +
      '<button type="button" class="md-button" data-pl="edit-cancel">Cancel</button></div>', true);
    if (!box) return;
    box.classList.add("pl-edit");
    form.attach(box.querySelector(".pl-form-body"), draft, keepDraft);
  }
  function saveEdit(btn) {
    if (!draft) return;
    var card = window.codexCardForm.card(draft);
    if (["actions", "bonus_actions", "reactions", "features"].some(function (k) { return card[k].some(function (e) { return !e.name; }); })) {
      return say("Every action and feature needs a name.", "warn");
    }
    ["character", "player", "portrait", "private", "source", "rev"].forEach(function (k) { delete card[k]; });   // not the form's to change
    btn.disabled = true;
    post("/api/party/save", { card: card, rev: mine().rev }).then(function (res) {
      btn.disabled = false;
      if (res.status !== 200) return say(esc(res.body.error || "Couldn't save it."), "warn");
      dropDraft();
      draft = null;
      closePanel();
      load().then(function () { say(res.body.unchanged ? "Nothing had changed." : "Saved - everyone sees it now.", "ok"); });
    }).catch(function () { btn.disabled = false; say("Couldn't reach the site - check your connection; your edits are kept here.", "warn"); });
  }

  // ------------------------------------------------------------ wiring
  function start() {
    root = document.querySelector(".pc-cards.party");
    if (!root || !window.codexParty || window.codexParty.data.audience !== "players") return;
    base = window.codexParty.data;
    root.addEventListener("codex:party-drawn", tools);
    root.addEventListener("click", function (ev) {
      var act = ev.target.getAttribute && ev.target.getAttribute("data-pl");
      if (!act) return;
      if (act === "import") importFile();
      else if (act === "privacy") privacy();
      else if (act === "edit") edit();
      else if (act === "edit-save") saveEdit(ev.target);
      else if (act === "edit-cancel") {
        if (!window.confirm("Throw away your edits?")) return;
        dropDraft();
        draft = null;
        closePanel();
      }
      else if (act === "close") closePanel();
    });
    load().then(connect);
    document.addEventListener("visibilitychange", function () {
      if (document.visibilityState !== "visible") return;
      retry = 1000;
      soon();
      connect();
    });
  }
  if (window.codexParty) start();
  else document.addEventListener("codex:party-ready", start);
})();
