/* Party page editor: Edit and Remove on each character card, and Add character. Saves to
   data/party.yml through the local save helper (tools/site_helper.py), like the encounter builder.
   Only on the site at home - the online copy (publish) doesn't show the buttons. After a save,
   CampaignCodex5e rebuilds and the page refreshes by itself. The form is card-form.js (the same one
   players get on their own card), and the preview is the card as party-cards.js draws it.

   Players' changes: once the players' site is online, players import their own characters and choose
   what's private there (docs/players/party-live.js). "Get players' changes" brings those into
   data/party.yml (the helper also does it when it starts, and publish before it builds); a card changed
   in both places is shown here to settle. History on each card lists its changes on the players' site,
   with Undo. */
(function () {
  "use strict";
  var HELPER = "http://127.0.0.1:8765";
  // Which campaign this page belongs to (hooks/campaign.py puts it in every page), so saved state
  // stays separate when two campaigns are served on one computer.
  var CAMPAIGN = (document.querySelector('meta[name="codex-campaign"]') || {}).content || "codex";
  var STORE = CAMPAIGN + "-party-editor";
  var ONLINE = location.protocol !== "file:" && !/^(127\.0\.0\.1|localhost|\[::1\])$/.test(location.hostname);
  var OFFLINE = "The save helper isn't running (it starts with <code>CampaignCodex5e</code>).";

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }
  function init() {
    var grid = document.querySelector(".pc-cards");
    if (!grid) return;
    if (ONLINE || grid.getAttribute("data-audience") === "players") return;
    setup(grid);
  }

  function setup(grid) {
    var cards = Array.from(grid.querySelectorAll(".pc-card[data-pc]"));
    var partyLevel = null;

    // ------------------------------------------------------------ buttons
    var bar = document.createElement("div");
    bar.className = "eb pe-bar";
    bar.innerHTML = '<button class="md-button pe-add">Add character</button>' +
      '<button class="md-button pe-import">Import from CCC5e</button>' +
      '<button class="md-button pe-pull" style="display: none" title="Bring what players changed on the players\' site into data/party.yml">' +
      "Get players' changes</button>" + '<span class="pe-msg"></span>';
    grid.parentNode.insertBefore(bar, grid);
    var sugBox = document.createElement("div");
    sugBox.className = "eb pe-sugs";
    grid.parentNode.insertBefore(sugBox, grid);
    cards.forEach(function (card) {
      var tools = document.createElement("div");
      tools.className = "eb eb-sbbar";
      tools.innerHTML = '<button class="eb-act pe-hist-btn" data-pe="history" style="display: none" title="Changes made on the players\' site, with Undo">History</button>' +
        '<button class="eb-act" data-pe="import" title="Update this card from a CCC5e export">Import .ccc5e</button>' +
        '<button class="eb-act" data-pe="edit">Edit</button><button class="eb-act eb-danger" data-pe="remove">Remove</button>';
      card.insertBefore(tools, card.firstChild);
    });
    var box = document.createElement("div");
    box.className = "eb pe-form";
    grid.parentNode.insertBefore(box, grid.nextSibling);

    function msg(html, kind) {
      bar.querySelector(".pe-msg").innerHTML = html ? '<span class="eb-msg eb-' + (kind || "info") + '">' + html + "</span>" : "";
    }
    function call(path, body) {
      var opts = body ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) } : {};
      return fetch(HELPER + path, opts).then(function (r) {
        return r.json().then(function (j) { return { status: r.status, body: j }; });
      });
    }

    // ------------------------------------------------------------ the draft (kept across reloads)
    var draft = null;   // { index: n or null (new), expect: name at n, d: the card as the form has it }
    try { draft = JSON.parse(localStorage.getItem(STORE) || "null"); } catch (e) {}
    if (draft && !draft.d) draft = null;   // one kept by an older version of this page
    function persist() { try { localStorage.setItem(STORE, JSON.stringify(draft)); } catch (e) {} }
    var form = window.codexCardForm;

    // ------------------------------------------------------------ the form (card-form.js) and its preview
    function render() {
      var isNew = draft.index == null;
      box.innerHTML =
        '<div class="eb-cf-head"><span class="eb-cf-title">' + (isNew ? "New character" : "Editing " + esc(draft.expect)) + "</span>" +
        '<span class="eb-cf-btns"><button class="pe-save md-button md-button--primary">' + (isNew ? "Add character" : "Save changes") + "</button>" +
        '<button class="pe-cancel md-button">Cancel</button></span></div>' +
        '<div class="eb-cf-status"></div>' +
        '<div class="eb-cf-cols"><div class="pe-form-body">' + form.html(draft.d, { dm: true, partyLevel: partyLevel }) + "</div>" +
        '<div class="eb-cf-preview"></div></div>';
      form.attach(box.querySelector(".pe-form-body"), draft.d, update);   // a fresh element each time: no doubled listeners
      update();
    }
    function update() {
      var c = form.card(draft.d);
      if (c.level === "" && partyLevel) c.level = partyLevel;
      box.querySelector(".eb-cf-preview").innerHTML = window.codexParty && window.codexParty.preview ? window.codexParty.preview(c) : "";
      persist();
    }
    function status(html, kind) {
      var el = box.querySelector(".eb-cf-status");
      if (el) el.innerHTML = '<div class="eb-msg eb-' + (kind || "info") + '">' + html + "</div>";
      else msg(html, kind);
    }
    function open(d) {
      draft = d;
      grid.style.display = "none"; bar.style.display = "none"; box.style.display = "";
      render();
      box.scrollIntoView({ block: "start" });
    }
    function close() {
      draft = null; persist();
      box.innerHTML = ""; box.style.display = "none"; grid.style.display = ""; bar.style.display = "";
    }

    function loadParty() {
      return call("/party").then(function (res) {
        if (res.status !== 200) throw new Error(res.body.error || "Couldn't read data/party.yml.");
        partyLevel = res.body.level;
        return res.body.members;
      });
    }
    function edit(i) {
      loadParty().then(function (members) {
        var m = members[i];
        if (!m) return msg("data/party.yml has changed since this page loaded - reload the page.", "warn");
        open({ index: i, expect: m.character, d: form.draft(m) });
      }).catch(function (e) { msg(e.message === "Failed to fetch" ? OFFLINE : esc(e.message), "warn"); });
    }
    function add() {
      loadParty().then(function () { open({ index: null, expect: "", d: form.draft({ character: "", player: "", email: "", note: "" }) }); })
        .catch(function (e) { msg(e.message === "Failed to fetch" ? OFFLINE : esc(e.message), "warn"); });
    }
    // A CCC5e export (.ccc5e): onto card i, or (i null) onto the character of that name or a new one.
    function importFile(i) {
      var input = document.createElement("input");
      input.type = "file";
      input.accept = ".ccc5e,.json";
      input.addEventListener("change", function () {
        var file = input.files && input.files[0];
        if (!file) return;
        file.text().then(function (text) {
          return loadParty().then(function (members) {
            var req = { file: text, name: file.name };
            if (i != null) { req.index = i; req.expect = members[i] && members[i].character; }
            return call("/party/import", req).then(function (res) {
              if (res.status !== 200) return msg(esc(res.body.error || "Couldn't read that file."), "warn");
              showImport(req, res.body, i);
            });
          });
        }).catch(function (e) { msg(e.message === "Failed to fetch" ? OFFLINE : esc(e.message), "warn"); });
      });
      input.click();
    }
    // The preview goes where it's about: inside the card being updated, or under the bar for a new one.
    function showImport(req, p, i) {
      var old = document.querySelector(".pe-import-box");
      if (old) old.remove();
      var holder = document.createElement("div");
      var card = i != null ? grid.querySelector('.pc-card[data-pc="' + i + '"]') : null;
      if (card) card.insertBefore(holder, card.querySelector(".pcx-strip") || card.firstChild.nextSibling);
      else bar.parentNode.insertBefore(holder, bar.nextSibling);
      var box = holder;
      var rows = (p.changes || []).map(function (c) {
        return "<tr><td>" + esc(String(c[0]).replace(/_/g, " ")) + '</td><td class="pe-old">' + esc(c[1]) + '</td><td class="pe-new">' + esc(c[2]) + "</td></tr>";
      }).join("");
      var title = p.adding ? "Add " + esc(p.character) + " to the party" :
        p.replacing && p.replacing !== p.character ? "Import " + esc(p.character) + " onto " + esc(p.replacing) + "'s card" : "Update " + esc(p.character);
      box.innerHTML = '<div class="pe-import-box"><p class="pe-sug-title">' + title + "</p>" +
        '<p class="eb-hint">' + esc(p.summary) + (p.portrait ? " · with a portrait" : "") + "</p>" +
        (p.has_sheet ? "" : '<div class="eb-msg eb-warn">This file is from CCC5e before 1.0.21: only the name, race, class and level come in. ' +
          "Export it again from a newer CCC5e for the whole card.</div>") +
        (p.adding ? "" : rows ? '<table class="pe-sug-table"><tr><th>What</th><th>Now</th><th>After the import</th></tr>' + rows + "</table>"
          : '<p class="eb-hint">Nothing changes.</p>') +
        '<p class="eb-hint">Kept as they are: the player, their email, your note, and anything marked private.</p>' +
        '<div class="pe-sug-act"><button class="md-button md-button--primary pe-import-save">' + (p.adding ? "Add character" : "Save the import") +
        '</button><button class="md-button pe-import-cancel">Cancel</button></div></div>';
      box.scrollIntoView({ behavior: "smooth", block: "center" });
      box.querySelector(".pe-import-cancel").addEventListener("click", function () { holder.remove(); });
      box.querySelector(".pe-import-save").addEventListener("click", function (ev) {
        ev.target.disabled = true;
        call("/party/import", Object.assign({}, req, { save: true })).then(function (res) {
          if (res.status !== 200) { ev.target.disabled = false; return msg(esc(res.body.error || "Couldn't save it."), "warn"); }
          holder.remove();
          msg((res.body.added ? "Added " : "Updated ") + esc(res.body.character) +
              " from CCC5e. The page refreshes when the site rebuilds.", "ok");
        }).catch(function () { ev.target.disabled = false; msg(OFFLINE, "warn"); });
      });
    }

    function remove(i) {
      loadParty().then(function (members) {
        var m = members[i];
        if (!m) return msg("data/party.yml has changed since this page loaded - reload the page.", "warn");
        if (!window.confirm("Remove " + m.character + " from the party? A copy of party.yml is kept in sources/backups/party.")) return;
        return call("/party/member/delete", { index: i, expect: m.character }).then(function (res) {
          if (res.status !== 200) return msg(esc(res.body.error || "Couldn't remove them."), "warn");
          msg("Removed " + esc(res.body.removed) + ". The page refreshes when the site rebuilds.", "ok");
        });
      }).catch(function (e) { msg(e.message === "Failed to fetch" ? OFFLINE : esc(e.message), "warn"); });
    }
    // ------------------------------------------------------------ players' changes (the live Party page online)
    function pull(settle) {
      var btn = bar.querySelector(".pe-pull");
      btn.disabled = true;
      return call("/party/pull", settle || {}).then(function (res) {
        btn.disabled = false;
        if (res.status !== 200) {
          // Not online (yet): nothing to get, and not worth a warning.
          if (res.body && res.body.online === false) return;
          btn.style.display = "";
          if (settle || btn.getAttribute("data-asked")) sugBox.innerHTML = '<span class="eb-msg eb-warn">Players\' changes: ' + esc(res.body.error || "couldn't get them.") + "</span>";
          return;
        }
        btn.style.display = "";
        grid.querySelectorAll(".pe-hist-btn").forEach(function (b) { b.style.display = ""; });
        var out = res.body, bits = [];
        if (out.changed && out.changed.length) bits.push('<span class="eb-msg eb-ok">Brought into <code>data/party.yml</code>: ' +
          out.changed.map(esc).join(", ") + ". The page refreshes when the site rebuilds.</span>");
        else if (btn.getAttribute("data-asked")) bits.push('<span class="eb-msg eb-info">No new changes from the players.</span>');
        (out.problems || []).forEach(function (p) { bits.push('<span class="eb-msg eb-warn">' + esc(p) + "</span>"); });
        if (out.conflicts && out.conflicts.length) {
          bits.push('<div class="pe-sug-box"><p class="pe-sug-title">Changed in both places</p>' +
            '<p class="eb-hint">These cards changed here in <code>data/party.yml</code> and on the players\' site since you last got players\' changes. ' +
            "Take theirs (your edit is dropped - make it again after), or keep yours (it replaces theirs when you next publish). " +
            "History on the card shows what they changed.</p>" +
            out.conflicts.map(function (c) {
              return '<div class="pe-sug" data-id="' + esc(c.id) + '"><b>' + esc(c.character) + "</b> " +
                '<span class="pe-sug-when">' + esc(c.by || "") + (c.at ? " · " + esc(new Date(c.at).toLocaleString()) : "") + "</span>" +
                '<div class="pe-sug-act"><button class="eb-act" data-settle="take">Take theirs</button>' +
                '<button class="eb-act" data-settle="keep">Keep mine</button></div></div>';
            }).join("") + "</div>");
        }
        sugBox.innerHTML = bits.join("");
      }).catch(function () { btn.disabled = false; });
    }
    sugBox.addEventListener("click", function (ev) {
      var how = ev.target.getAttribute("data-settle");
      if (!how) return;
      var id = ev.target.closest("[data-id]").getAttribute("data-id"), settle = {};
      settle[how] = [id];
      pull(settle);
    });

    function history(card) {
      var old = card.querySelector(".pe-hist");
      if (old) return old.remove();
      var box = document.createElement("div");
      box.className = "pe-hist pe-import-box";
      box.innerHTML = '<p class="eb-hint">Getting its history from the players\' site…</p>';
      card.insertBefore(box, card.querySelector(".pcx-strip") || null);
      call("/party/history?id=" + encodeURIComponent(card.id)).then(function (res) {
        if (res.status !== 200) { box.innerHTML = '<div class="eb-msg eb-warn">' + esc(res.body.error || "Couldn't get it.") + "</div>"; return; }
        var list = res.body.history || [];
        box.innerHTML = '<p class="pe-sug-title">Changes on the players\' site</p>' + (!list.length ? '<p class="eb-hint">None yet.</p>' :
          '<table class="pe-sug-table pe-hist-table"><tr><th>When</th><th>Who</th><th>What</th><th></th></tr>' + list.map(function (h) {
            return "<tr><td>" + esc(new Date(h.at).toLocaleString()) + "</td><td>" + esc(h.by === "dm" ? "you (publish)" : h.by === "undo" ? "you (undo)" : h.by) +
              "</td><td>" + esc(h.summary) + "</td><td>" + (h.undo ? '<button class="eb-act" data-undo="' + esc(h.key) + '" title="Put the card back as it was before this">Undo</button>' : "") + "</td></tr>";
          }).join("") + "</table>") +
          '<p class="eb-hint">Undo puts the card back as it was just before that change, on the players\' site and in <code>data/party.yml</code>.</p>' +
          '<div class="pe-sug-act"><button class="md-button pe-hist-close">Close</button></div>';
      }).catch(function () { box.innerHTML = '<div class="eb-msg eb-warn">' + OFFLINE + "</div>"; });
      box.addEventListener("click", function (ev) {
        if (ev.target.classList.contains("pe-hist-close")) return box.remove();
        var key = ev.target.getAttribute("data-undo");
        if (!key || !window.confirm("Put " + card.querySelector(".pcx-name").textContent + "'s card back as it was before this change?")) return;
        ev.target.disabled = true;
        call("/party/undo", { id: card.id, key: key }).then(function (res) {
          if (res.status !== 200) { ev.target.disabled = false; return msg(esc(res.body.error || "Couldn't undo it."), "warn"); }
          box.remove();
          msg("Undone. The page refreshes when the site rebuilds.", "ok");
        }).catch(function () { ev.target.disabled = false; msg(OFFLINE, "warn"); });
      });
    }

    function save() {
      var m = form.card(draft.d);
      delete m.rev;   // the helper keeps the card's own
      if (!m.character) return status("Give the character a name.", "warn");
      if (["actions", "bonus_actions", "reactions", "features"].some(function (k) { return m[k].some(function (e) { return !e.name; }); })) {
        return status("Every action and feature needs a name.", "warn");
      }
      call("/party/member", { index: draft.index, expect: draft.expect, member: m }).then(function (res) {
        if (res.status !== 200) return status(esc(res.body.error || "Couldn't save."), "warn");
        var added = draft.index == null;
        close();
        msg((added ? "Added " + esc(res.body.character) + " to" : "Saved " + esc(res.body.character) + " in") +
            " <code>data/party.yml</code>. The page refreshes when the site rebuilds.", "ok");
      }).catch(function () { status(OFFLINE, "warn"); });
    }

    // ------------------------------------------------------------ wiring
    bar.querySelector(".pe-add").addEventListener("click", add);
    bar.querySelector(".pe-import").addEventListener("click", function () { importFile(null); });
    bar.querySelector(".pe-pull").addEventListener("click", function (ev) { ev.target.setAttribute("data-asked", "1"); pull(); });
    grid.addEventListener("click", function (ev) {
      var act = ev.target.getAttribute("data-pe");
      if (!act) return;
      var i = +ev.target.closest("[data-pc]").getAttribute("data-pc");
      if (act === "edit") edit(i); else if (act === "remove") remove(i);
      else if (act === "import") importFile(i);
      else if (act === "history") history(ev.target.closest("[data-pc]"));
    });
    box.addEventListener("click", function (ev) {
      var t = ev.target;
      if (!draft) return;
      if (t.classList.contains("pe-save")) return save();
      if (t.classList.contains("pe-cancel")) {
        if (!window.confirm("Discard " + (draft.index == null ? "this new character" : "your changes to " + draft.expect) + "?")) return;
        return close();
      }
    });

    box.style.display = "none";
    pull();
    if (draft) {   // a character was being edited when the page reloaded
      loadParty().catch(function () {}).then(function () { open(draft); });
    }
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
