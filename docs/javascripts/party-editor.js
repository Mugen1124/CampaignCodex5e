/* Party page editor: Edit and Remove on each character card, and Add character. Saves to
   data/party.yml through the local save helper (tools/site_helper.py), like the encounter builder.
   Only on the site at home - the online copy (publish) doesn't show the buttons. After a save,
   CampaignCodex5e rebuilds and the page refreshes by itself. The preview is built the same way
   hooks/campaign.py builds the cards (render_pc_card).

   Card suggestions: on the players' site (cards marked data-audience="players"), each player gets
   "Suggest changes" on their own card - the same form, less the name, player, email, and DM note -
   sent to the players' worker (publish/players/worker.js) for the DM to approve. On the DM's site at
   home, waiting suggestions show above the cards with what would change, and Approve / Decline. */
(function () {
  "use strict";
  var HELPER = "http://127.0.0.1:8765";
  // Which campaign this page belongs to (hooks/campaign.py puts it in every page), so saved state
  // stays separate when two campaigns are served on one computer.
  var CAMPAIGN = (document.querySelector('meta[name="codex-campaign"]') || {}).content || "codex";
  var STORE = CAMPAIGN + "-party-editor";   // the players' site keeps its draft under its own name
  var ONLINE = location.protocol !== "file:" && !/^(127\.0\.0\.1|localhost|\[::1\])$/.test(location.hostname);
  var OFFLINE = "The save helper isn't running (it starts with <code>CampaignCodex5e</code>).";

  var ABIL = ["str", "dex", "con", "int", "wis", "cha"];
  var IDENTITY = [["character", "Character", "", "pe-w2"], ["player", "Player", ""], ["race", "Race", ""],
                  ["class", "Class", ""], ["level", "Level", ""],
                  ["email", "Player's email", "their login for the players' site", "pe-w2"]];
  var PLAYER_IDENTITY = [["race", "Race", ""], ["class", "Class", ""], ["level", "Level", ""]];
  var DEFENSE = [["ac", "AC", "15"], ["ac_note", "AC note", "unarmored defense"], ["hp", "HP", "55"],
                 ["hp_formula", "HP formula", "5d12 + 15"], ["speed", "Speed", "30 ft."],
                 ["initiative", "Initiative (if not Dex)", ""], ["passive_perception", "Passive Perception", "11"]];
  var DETAILS = [["saves", "Saving throws", "Str +7, Con +6"], ["skills", "Skills", "Athletics +7, Survival +4"],
                 ["resistances", "Damage resistances", "poison"], ["immunities", "Damage immunities", ""],
                 ["condition_immunities", "Condition immunities", ""], ["senses", "Senses", "darkvision 60 ft."],
                 ["languages", "Languages", "Common, Dwarvish"]];
  var LISTS = [["features", "Features", "feature"], ["actions", "Actions", "action"],
               ["bonus_actions", "Bonus Actions", "bonus action"], ["reactions", "Reactions", "reaction"]];
  var TEXT_FIELDS = IDENTITY.concat(DEFENSE).concat(DETAILS).map(function (f) { return f[0]; }).concat(["note"]);

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }
  function squash(s) { return String(s == null ? "" : s).split(/\s+/).join(" ").trim(); }
  function inlineMd(s) {
    return esc(squash(s)).replace(/\*\*\*(.+?)\*\*\*/g, "<strong><em>$1</em></strong>")
      .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>").replace(/\*(.+?)\*/g, "<em>$1</em>")
      .replace(/`(.+?)`/g, "<code>$1</code>");
  }
  function mod(n) { return Math.floor((n - 10) / 2); }
  function signed(n) { return n >= 0 ? "+" + n : "−" + Math.abs(n); }
  function num(v) { var n = parseInt(String(v).replace("+", ""), 10); return isNaN(n) ? null : n; }

  function init() {
    var grid = document.querySelector(".pc-cards");
    if (!grid) return;
    var PLAYER = grid.getAttribute("data-audience") === "players";   // the players' site: suggestions only
    if (ONLINE && !PLAYER) return;
    if (PLAYER) {
      // Only the signed-in player's own card gets the button (the worker knows who's signed in).
      return fetch("/api/me", { cache: "no-store" }).then(function (r) { return r.ok ? r.json() : {}; })
        .then(function (me) { if (me && me.character) setup(grid, me); }).catch(function () {});
    }
    setup(grid, null);
  }

  function setup(grid, me) {
    var PLAYER = !!me;
    var cards = Array.from(grid.querySelectorAll(".pc-card[data-pc]"));
    var partyLevel = PLAYER ? me.level : null;
    if (PLAYER) STORE = CAMPAIGN + "-card-suggestion";

    // ------------------------------------------------------------ buttons
    var bar = document.createElement("div");
    bar.className = "eb pe-bar";
    bar.innerHTML = (PLAYER ? "" : '<button class="md-button pe-add">Add character</button>') + '<span class="pe-msg"></span>';
    grid.parentNode.insertBefore(bar, grid);
    var sugBox = document.createElement("div");
    sugBox.className = "eb pe-sugs";
    grid.parentNode.insertBefore(sugBox, grid);
    cards.forEach(function (card) {
      if (PLAYER && +card.getAttribute("data-pc") !== me.index) return;
      var tools = document.createElement("div");
      tools.className = "eb eb-sbbar";
      tools.innerHTML = PLAYER
        ? '<button class="eb-act" data-pe="suggest">' + (me.suggestion && me.suggestion.status === "pending" ? "Edit my suggestion" : "Suggest changes") + "</button>"
        : '<button class="eb-act" data-pe="edit">Edit</button><button class="eb-act eb-danger" data-pe="remove">Remove</button>';
      card.insertBefore(tools, card.firstChild);
    });
    var box = document.createElement("div");
    box.className = "eb pe-form";
    grid.parentNode.insertBefore(box, grid.nextSibling);

    // A player's latest suggestion and what became of it.
    if (PLAYER && me.suggestion) {
      var st = me.suggestion.status;
      setTimeout(function () {
        msg(st === "pending" ? "Your suggested changes are waiting for the DM."
          : st === "approved" ? "The DM approved your suggested changes — they show on your card once the site is next updated."
          : "The DM didn't take your last suggested changes.", st === "rejected" ? "warn" : st === "approved" ? "ok" : "info");
      }, 0);
    }
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
    var draft = null;   // { index: n or null (new), expect: name at n, m: {...form values} }
    try { draft = JSON.parse(localStorage.getItem(STORE) || "null"); } catch (e) {}
    function persist() { try { localStorage.setItem(STORE, JSON.stringify(draft)); } catch (e) {} }

    function formValues(raw) {
      var m = {};
      TEXT_FIELDS.forEach(function (f) { m[f] = raw[f] == null ? "" : String(raw[f]); });
      var scores = raw.abilities || {};
      m.abilities = {};
      ABIL.forEach(function (a) { m.abilities[a] = scores[a] == null ? "" : String(scores[a]); });
      LISTS.forEach(function (l) {
        m[l[0]] = (raw[l[0]] || []).map(function (e) { return { name: String(e.name || ""), text: squash(e.text) }; });
      });
      return m;
    }
    // The form's values as a party.yml member, the way the helper will save it.
    function toMember(v) {
      var out = {};
      TEXT_FIELDS.forEach(function (f) { var s = f === "note" ? v[f].trim() : squash(v[f]); if (s) out[f] = s; });
      ["level", "ac", "hp", "initiative", "passive_perception"].forEach(function (f) {
        if (out[f] != null && num(out[f]) != null) out[f] = num(out[f]);
      });
      var scores = {};
      ABIL.forEach(function (a) { if (num(v.abilities[a]) != null) scores[a] = num(v.abilities[a]); });
      if (Object.keys(scores).length) out.abilities = scores;
      LISTS.forEach(function (l) {
        var rows = v[l[0]].map(function (e) { return { name: squash(e.name), text: squash(e.text) }; })
          .filter(function (e) { return e.name || e.text; });
        if (rows.length) out[l[0]] = rows;
      });
      return out;
    }

    // ------------------------------------------------------------ preview (as render_pc_card)
    function cardHtml(p) {
      var dash = "—", s = p.abilities || {};
      var what = [p.race, p["class"]].filter(Boolean).join(" ");
      var level = p.level != null ? p.level : partyLevel;
      var sub = what + (level ? ", level " + level : "") + (p.player ? " — " + p.player : "");
      var init = p.initiative != null ? p.initiative : (s.dex != null ? mod(s.dex) : null);
      var head = ["<strong>Armor Class</strong> " + esc(p.ac != null ? p.ac : dash) + (p.ac_note ? " (" + esc(p.ac_note) + ")" : ""),
        "<strong>Hit Points</strong> " + esc(p.hp != null ? p.hp : dash) + (p.hp_formula ? " (" + esc(p.hp_formula) + ")" : ""),
        "<strong>Speed</strong> " + esc(p.speed || dash),
        "<strong>Initiative</strong> " + (init != null ? signed(init) : dash)];
      if (p.passive_perception != null) head.push("<strong>Passive Perception</strong> " + esc(p.passive_perception));
      var h = '<div class="statblock pc-card"><h3>' + esc(p.character || "New character") + "</h3>" +
        "<p><em>" + esc(sub) + "</em></p><hr><p>" + head.join("<br>\n") + "</p>" +
        "<table><thead><tr>" + ABIL.map(function (a) { return '<th style="text-align: center;">' + a.toUpperCase() + "</th>"; }).join("") +
        "</tr></thead><tbody><tr>" + ABIL.map(function (a) {
          return '<td style="text-align: center;">' + (s[a] != null ? s[a] + " (" + signed(mod(s[a])) + ")" : dash) + "</td>";
        }).join("") + "</tr></tbody></table>";
      var details = [["Saving Throws", "saves"], ["Skills", "skills"], ["Damage Resistances", "resistances"],
        ["Damage Immunities", "immunities"], ["Condition Immunities", "condition_immunities"], ["Senses", "senses"],
        ["Languages", "languages"]].filter(function (x) { return p[x[1]]; })
        .map(function (x) { return "<strong>" + x[0] + "</strong> " + esc(p[x[1]]); });
      if (details.length) h += "<p>" + details.join("<br>\n") + "</p>";
      h += "<hr>";
      var body = "";
      LISTS.forEach(function (l, i) {
        if (!p[l[0]]) return;
        if (i > 0) body += '<p class="sb-section">' + l[1] + "</p>";
        p[l[0]].forEach(function (e) { body += "<p><strong><em>" + inlineMd(e.name) + ".</em></strong> " + inlineMd(e.text) + "</p>"; });
      });
      h += body || "<p><em>Nothing here yet — fill it in with Edit on the Party page (on the site at home), or under this character in <code>data/party.yml</code>.</em></p>";
      if (p.note) h += "<hr><p><em>" + inlineMd(p.note) + "</em></p>";
      return h + "</div>";
    }

    // ------------------------------------------------------------ the form
    function listRows(key, noun) {
      return draft.m[key].map(function (e, i) {
        var at = ' data-l="' + key + '" data-i="' + i + '"';
        return '<div class="eb-cf-entry"><div class="eb-cf-entryhead"><input' + at + ' data-k="name" placeholder="Name" value="' + esc(e.name) + '">' +
          '<button class="eb-act eb-danger" data-rm="' + key + '" data-i="' + i + '">Remove</button></div>' +
          "<textarea" + at + ' data-k="text" rows="2" placeholder="' +
          (key === "actions" ? "*Melee Weapon Attack:* +7 to hit, reach 5 ft. *Hit:* 10 (1d12 + 4) slashing damage." : "What it does") +
          '">' + esc(e.text) + "</textarea></div>";
      }).join("") + '<button class="eb-act" data-addl="' + key + '">+ Add ' + noun + "</button>";
    }
    function inputs(fields) {
      return fields.map(function (f) {
        return '<label class="' + (f[3] || (f[0] === "speed" || f[0] === "senses" || f[0] === "resistances" ? "eb-w2" : "")) + '">' + f[1] +
          ' <input data-f="' + f[0] + '" value="' + esc(draft.m[f[0]]) + '"' +
          (f[0] === "level" ? ' placeholder="' + esc(partyLevel || "") + ' (party level)"' : f[2] ? ' placeholder="' + esc(f[2]) + '"' : "") + "></label>";
      }).join("").replace(/pe-w2/g, "eb-w2");
    }
    function render() {
      var m = draft.m, isNew = draft.index == null;
      box.innerHTML =
        '<div class="eb-cf-head"><span class="eb-cf-title">' + (PLAYER ? "Suggest changes to " + esc(draft.expect) : isNew ? "New character" : "Editing " + esc(draft.expect)) + "</span>" +
        '<span class="eb-cf-btns"><button class="pe-save md-button md-button--primary">' + (PLAYER ? "Send to the DM" : isNew ? "Add character" : "Save changes") + "</button>" +
        '<button class="pe-cancel md-button">Cancel</button></span></div>' +
        '<div class="eb-cf-status"></div>' +
        (PLAYER ? '<p class="eb-hint">Your changes go to the DM, who approves them; they show on your card once the site is next updated.</p>' : "") +
        '<div class="eb-cf-cols"><div class="eb-cf-form">' +
        '<fieldset><legend>Character</legend><div class="eb-cf-grid">' + inputs(PLAYER ? PLAYER_IDENTITY : IDENTITY) + "</div></fieldset>" +
        '<fieldset><legend>Defenses and movement</legend><div class="eb-cf-grid">' + inputs(DEFENSE) + "</div></fieldset>" +
        '<fieldset><legend>Ability scores</legend><div class="eb-cf-abil">' + ABIL.map(function (a) {
          return "<label>" + a.toUpperCase() + ' <input type="number" min="1" max="30" data-a="' + a + '" value="' + esc(m.abilities[a]) + '">' +
            '<span class="eb-cf-mod" data-mod="' + a + '"></span></label>';
        }).join("") + '</div><div class="eb-cf-hint">Leave any blank to show a dash on the card.</div></fieldset>' +
        '<fieldset><legend>Details</legend><div class="eb-cf-grid">' + inputs(DETAILS) + "</div></fieldset>" +
        LISTS.map(function (l) {
          return "<fieldset><legend>" + l[1] + '</legend><div class="eb-cf-list" data-list="' + l[0] + '">' + listRows(l[0], l[2]) + "</div></fieldset>";
        }).join("") +
        (PLAYER ? "" : '<fieldset><legend>DM note</legend><textarea data-f="note" rows="3" placeholder="Shown at the bottom of the card.">' + esc(m.note) + "</textarea></fieldset>") +
        '</div><div class="eb-cf-preview"></div></div>';
      update();
    }
    function update() {
      var m = toMember(draft.m);
      box.querySelector(".eb-cf-preview").innerHTML = cardHtml(m);
      ABIL.forEach(function (a) {
        var n = num(draft.m.abilities[a]);
        box.querySelector('[data-mod="' + a + '"]').textContent = n != null ? signed(mod(n)) : "";
      });
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
        open({ index: i, expect: m.character, m: formValues(m) });
      }).catch(function (e) { msg(e.message === "Failed to fetch" ? OFFLINE : esc(e.message), "warn"); });
    }
    function add() {
      loadParty().then(function () { open({ index: null, expect: "", m: formValues({}) }); })
        .catch(function (e) { msg(e.message === "Failed to fetch" ? OFFLINE : esc(e.message), "warn"); });
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
    function suggest() {
      var m = toMember(draft.m);
      ["character", "player", "email", "note"].forEach(function (k) { delete m[k]; });
      fetch("/api/cards/suggest", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ member: m }) })
        .then(function (r) { return r.json().then(function (j) { return { status: r.status, body: j }; }); })
        .then(function (res) {
          if (res.status !== 200) return status(esc(res.body.error || "Couldn't send it."), "warn");
          me.suggestion = { status: "pending", member: m };
          close();
          msg("Sent to the DM. Your card changes once they approve it and the site is next updated.", "ok");
          var b = grid.querySelector('[data-pe="suggest"]');
          if (b) b.textContent = "Edit my suggestion";
        }).catch(function () { status("Couldn't reach the site - check your connection and try again.", "warn"); });
    }
    function startSuggest() {
      var from = me.suggestion && me.suggestion.status === "pending" ? me.suggestion.member : me.card;
      if (!draft || draft.expect !== me.character) open({ index: me.index, expect: me.character, m: formValues(Object.assign({ character: me.character }, from)) });
      else open(draft);
    }

    // ------------------------------------------------------------ DM: suggestions from the players' site
    function loadSuggestions() {
      call("/party/suggestions").then(function (res) {
        if (res.status !== 200) {
          sugBox.innerHTML = res.body && res.body.error && !/missing/.test(res.body.error)
            ? '<span class="eb-msg eb-warn">Players\' suggestions: ' + esc(res.body.error) + "</span>" : "";
          return;
        }
        var list = res.body.suggestions || [];
        sugBox.innerHTML = !list.length ? "" : '<div class="pe-sug-box"><p class="pe-sug-title">Changes players suggested for their cards</p>' +
          list.map(function (s) {
            return '<div class="pe-sug" data-id="' + esc(s.id) + '"><div class="pe-sug-head"><b>' + esc(s.character) + "</b> " +
              '<span class="pe-sug-when">' + esc(s.email || "") + (s.at ? " · " + esc(new Date(s.at).toLocaleString()) : "") + "</span></div>" +
              (s.missing ? '<p class="eb-hint">No character by that name in party.yml any more.</p>' :
               !s.changes.length ? '<p class="eb-hint">No differences from the card as it is now.</p>' :
               '<table class="pe-sug-table"><thead><tr><th>Field</th><th>Now</th><th>Suggested</th></tr></thead><tbody>' +
               s.changes.map(function (c) {
                 return "<tr><td>" + esc(c.field) + "</td><td>" + esc(c.old) + "</td><td>" + esc(c["new"]) + "</td></tr>";
               }).join("") + "</tbody></table>") +
              '<div class="pe-sug-act"><button class="eb-act" data-sa="approve"' + (s.missing ? " disabled" : "") + '>Approve</button>' +
              '<button class="eb-act eb-danger" data-sa="reject">Decline</button><span class="pe-sug-msg"></span></div></div>';
          }).join("") + "</div>";
      }).catch(function () {});
    }
    sugBox.addEventListener("click", function (ev) {
      var a = ev.target.getAttribute("data-sa");
      if (!a) return;
      var row = ev.target.closest(".pe-sug"), out = row.querySelector(".pe-sug-msg");
      call("/party/suggestion", { id: row.getAttribute("data-id"), action: a }).then(function (res) {
        if (res.status !== 200) { out.innerHTML = '<span class="eb-msg eb-warn">' + esc(res.body.error || "Couldn't do that.") + "</span>"; return; }
        row.classList.add("pe-sug-done");
        row.querySelector(".pe-sug-act").innerHTML = '<span class="eb-msg eb-ok">' + (a === "approve"
          ? "Approved — saved to <code>data/party.yml</code>. Run <code>publish</code> to show it on the players' site."
          : "Declined.") + "</span>";
      }).catch(function () { out.innerHTML = '<span class="eb-msg eb-warn">' + OFFLINE + "</span>"; });
    });

    function save() {
      if (PLAYER) return suggest();
      var m = toMember(draft.m);
      if (!m.character) return status("Give the character a name.", "warn");
      call("/party/member", { index: draft.index, expect: draft.expect, member: m }).then(function (res) {
        if (res.status !== 200) return status(esc(res.body.error || "Couldn't save."), "warn");
        var added = draft.index == null;
        close();
        msg((added ? "Added " + esc(res.body.character) + " to" : "Saved " + esc(res.body.character) + " in") +
            " <code>data/party.yml</code>. The page refreshes when the site rebuilds.", "ok");
      }).catch(function () { status(OFFLINE, "warn"); });
    }

    // ------------------------------------------------------------ wiring
    if (!PLAYER) bar.querySelector(".pe-add").addEventListener("click", add);
    grid.addEventListener("click", function (ev) {
      var act = ev.target.getAttribute("data-pe");
      if (!act) return;
      var i = +ev.target.closest("[data-pc]").getAttribute("data-pc");
      if (act === "suggest") startSuggest(); else if (act === "edit") edit(i); else if (act === "remove") remove(i);
    });
    box.addEventListener("input", function (ev) {
      var t = ev.target;
      if (!draft) return;
      var f = t.getAttribute("data-f"), a = t.getAttribute("data-a"), l = t.getAttribute("data-l");
      if (f) draft.m[f] = t.value;
      else if (a) draft.m.abilities[a] = t.value;
      else if (l) draft.m[l][+t.getAttribute("data-i")][t.getAttribute("data-k")] = t.value;
      update();
    });
    box.addEventListener("click", function (ev) {
      var t = ev.target;
      if (!draft) return;
      if (t.classList.contains("pe-save")) return save();
      if (t.classList.contains("pe-cancel")) {
        if (!window.confirm("Discard " + (PLAYER ? "these suggested changes" : draft.index == null ? "this new character" : "your changes to " + draft.expect) + "?")) return;
        return close();
      }
      var key = t.getAttribute("data-addl") || t.getAttribute("data-rm");
      if (!key) return;
      if (t.hasAttribute("data-addl")) draft.m[key].push({ name: "", text: "" });
      else draft.m[key].splice(+t.getAttribute("data-i"), 1);
      var noun = LISTS.filter(function (x) { return x[0] === key; })[0][2];
      box.querySelector('[data-list="' + key + '"]').innerHTML = listRows(key, noun);
      if (t.hasAttribute("data-addl")) box.querySelector('[data-list="' + key + '"] .eb-cf-entry:last-of-type input').focus();
      update();
    });
    box.addEventListener("keydown", function (ev) {
      if (ev.key === "Enter" && ev.target.tagName === "INPUT") ev.preventDefault();   // Enter doesn't submit anything here
    });

    box.style.display = "none";
    if (PLAYER) {
      if (draft && draft.expect === me.character) open(draft);   // a suggestion was being written when the page reloaded
    } else {
      loadSuggestions();
      if (draft) {   // a character was being edited when the page reloaded
        loadParty().catch(function () {}).then(function () { open(draft); });
      }
    }
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
