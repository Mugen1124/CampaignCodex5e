/* The character card form, shared by both Party pages so they can always change the same things:
   your Edit at home (party-editor.js, which adds the name, player, email and your note) and a player's
   Edit on their own card on the players' site (docs/players/party-live.js). Everything an import from
   CCC5e fills in can be typed here too - spells, inventory, money, persona and backstory included.

     var d = codexCardForm.draft(card)        a copy of the card for the form to change
     box.innerHTML = codexCardForm.html(d, {dm: true, partyLevel: 3})
     codexCardForm.attach(box, d, onChange)   keeps d in step with the form (rows added and removed too)
     codexCardForm.card(d)                    the card to save: every field the form has, empty ones
                                              as "" or [] so that clearing a field clears it */
(function () {
  "use strict";
  var ABIL = ["str", "dex", "con", "int", "wis", "cha"];
  var IDENTITY = [["character", "Character", "", true], ["player", "Player", ""], ["email", "Player's email", "their login for the players' site"]];
  var BASICS = [["race", "Race", ""], ["class", "Class", "Wizard (School of Evocation)"], ["background", "Background", ""], ["level", "Level", "", false, "n"]];
  var DEFENSE = [["ac", "AC", "15", false, "n"], ["ac_note", "AC note", "unarmored defense"], ["hp", "HP (maximum)", "55", false, "n"],
    ["hp_formula", "HP formula", "5d12 + 15"], ["speed", "Speed", "30 ft."], ["initiative", "Initiative (if not Dex)", "", false, "n"],
    ["passive_perception", "Passive Perception", "11", false, "n"]];
  var DETAILS = [["saves", "Saving throws", "Str +7, Con +6"], ["skills", "Skills", "Athletics +7, Survival +4"],
    ["senses", "Senses", "darkvision 60 ft."], ["languages", "Languages", "Common, Dwarvish"], ["resistances", "Damage resistances", ""],
    ["immunities", "Damage immunities", ""], ["condition_immunities", "Condition immunities", ""]];
  var PROFS = [["armor", "Armor proficiencies", "light armor, shields"], ["weapons", "Weapon proficiencies", "simple weapons"],
    ["tools", "Tool proficiencies", "thieves' tools"]];
  var ENTRIES = [["actions", "Actions", "action", "*Melee Weapon Attack:* +7 to hit, reach 5 ft. *Hit:* 10 (1d12 + 4) slashing damage."],
    ["bonus_actions", "Bonus actions", "bonus action", "What it does"], ["reactions", "Reactions", "reaction", "What it does"],
    ["features", "Features & traits", "feature", "What it does"]];
  var COINS = ["pp", "gp", "ep", "sp", "cp"];
  var PERSONA = [["alignment", "Alignment"], ["deity", "Deity"], ["appearance", "Appearance", true], ["ideal", "Ideal", true],
    ["bond", "Bond", true], ["flaw", "Flaw", true], ["allies", "Allies & organizations", true]];
  var NUMBERS = ["level", "ac", "hp", "initiative", "passive_perception"];
  var ORD = ["Cantrip", "1st", "2nd", "3rd", "4th", "5th", "6th", "7th", "8th", "9th"];

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }
  function val(v) { return v == null ? "" : String(v); }
  function squash(s) { return val(s).split(/\s+/).filter(Boolean).join(" "); }
  function int(v) { var n = parseInt(String(v == null ? "" : v).replace("+", ""), 10); return isNaN(n) ? null : n; }
  function copy(x) { return JSON.parse(JSON.stringify(x || {})); }

  // ------------------------------------------------------------ the draft
  function draft(card) {
    var d = copy(card);
    ENTRIES.forEach(function (l) { d[l[0]] = d[l[0]] || []; });
    d.inventory = d.inventory || [];
    d.abilities = d.abilities || {};
    d.proficiencies = d.proficiencies || {};
    d.currency = d.currency || {};
    d.persona = d.persona || {};
    // The first spellcasting (the class's) is the one the form shows; any others are kept as they are.
    var sc = (d.spellcasting || [])[0] || {};
    d._cast = { name: val(sc.name), ability: val(sc.ability), save_dc: val(sc.save_dc), attack: val(sc.attack),
                slots: copy(sc.slots), pact: !!sc.pact };
    d._spells = (sc.cantrips || []).map(function (n) { return { name: n, level: 0 }; })
      .concat((sc.spells || []).map(function (s) { return { name: s.name, level: s.level || 0, prepared: !!s.prepared }; }));
    return d;
  }

  // ------------------------------------------------------------ the form
  function input(path, label, value, hint, wide, kind) {
    return '<label class="' + (wide ? "eb-w2" : "") + '">' + esc(label) + ' <input data-p="' + path + '"' +
      (kind === "n" ? ' type="number"' : "") + ' value="' + esc(val(value)) + '"' + (hint ? ' placeholder="' + esc(hint) + '"' : "") + "></label>";
  }
  function fields(d, list, prefix) {
    return list.map(function (f) {
      var key = f[0], v = prefix ? (d[prefix] || {})[key] : d[key];
      return input((prefix ? prefix + "." : "") + key, f[1], v, f[2], f[3], f[4]);
    }).join("");
  }
  function entryRows(d, key) {
    var l = ENTRIES.filter(function (x) { return x[0] === key; })[0];
    return d[key].map(function (e, i) {
      var at = ' data-l="' + key + '" data-i="' + i + '"';
      return '<div class="eb-cf-entry"><div class="eb-cf-entryhead"><input' + at + ' data-k="name" placeholder="Name" value="' + esc(e.name) + '">' +
        '<button type="button" class="eb-act eb-danger" data-rm="' + key + '" data-i="' + i + '">Remove</button></div>' +
        "<textarea" + at + ' data-k="text" rows="2" placeholder="' + esc(l[3]) + '">' + esc(e.text) + "</textarea></div>";
    }).join("") + '<button type="button" class="eb-act" data-add="' + key + '">+ Add ' + l[2] + "</button>";
  }
  function itemRows(d) {
    return d.inventory.map(function (it, i) {
      var at = ' data-l="inventory" data-i="' + i + '"';
      return '<div class="cf-row cf-item"><input' + at + ' data-k="name" placeholder="Item" value="' + esc(it.name) + '">' +
        '<input' + at + ' data-k="qty" type="number" min="0" title="How many" value="' + esc(it.qty == null ? 1 : it.qty) + '">' +
        '<label><input type="checkbox"' + at + ' data-k="equipped"' + (it.equipped ? " checked" : "") + "> equipped</label>" +
        '<label><input type="checkbox"' + at + ' data-k="magic"' + (it.magic ? " checked" : "") + "> magic</label>" +
        '<label><input type="checkbox"' + at + ' data-k="attuned"' + (it.attuned ? " checked" : "") + "> attuned</label>" +
        '<button type="button" class="eb-act eb-danger" data-rm="inventory" data-i="' + i + '">Remove</button></div>';
    }).join("") + '<button type="button" class="eb-act" data-add="inventory">+ Add item</button>';
  }
  function spellRows(d) {
    return d._spells.map(function (s, i) {
      var at = ' data-l="_spells" data-i="' + i + '"';
      return '<div class="cf-row cf-spell"><input' + at + ' data-k="name" placeholder="Spell" value="' + esc(s.name) + '">' +
        "<select" + at + ' data-k="level">' + ORD.map(function (o, n) {
          return '<option value="' + n + '"' + (+s.level === n ? " selected" : "") + ">" + (n ? o + " level" : o) + "</option>";
        }).join("") + "</select>" +
        '<label title="Prepared (or always known)"><input type="checkbox"' + at + ' data-k="prepared"' + (s.prepared ? " checked" : "") + "> prepared</label>" +
        '<button type="button" class="eb-act eb-danger" data-rm="_spells" data-i="' + i + '">Remove</button></div>';
    }).join("") + '<button type="button" class="eb-act" data-add="_spells">+ Add spell</button>';
  }
  function html(d, opts) {
    opts = opts || {};
    var p = d.persona, c = d._cast;
    var basics = BASICS.map(function (f) {
      return f[0] === "level" && opts.partyLevel ? [f[0], f[1], opts.partyLevel + " (the party's level)", f[3], f[4]] : f;
    });
    return '<div class="eb-cf-form cf-form">' +
      '<fieldset><legend>Character</legend><div class="eb-cf-grid">' + (opts.dm ? fields(d, IDENTITY) : "") + fields(d, basics) + "</div></fieldset>" +
      '<fieldset><legend>Defenses and movement</legend><div class="eb-cf-grid">' + fields(d, DEFENSE) + "</div></fieldset>" +
      '<fieldset><legend>Ability scores</legend><div class="eb-cf-abil">' + ABIL.map(function (a) {
        return "<label>" + a.toUpperCase() + ' <input type="number" min="1" max="30" data-p="abilities.' + a + '" value="' + esc(val(d.abilities[a])) + '"></label>';
      }).join("") + '</div><div class="eb-cf-hint">Leave any blank to show a dash on the card.</div></fieldset>' +
      '<fieldset><legend>Details</legend><div class="eb-cf-grid">' +
      DETAILS.map(function (f) { return input(f[0], f[1], d[f[0]], f[2], true); }).join("") +
      PROFS.map(function (f) { return input("proficiencies." + f[0], f[1], d.proficiencies[f[0]], f[2], true); }).join("") + "</div></fieldset>" +
      ENTRIES.map(function (l) {
        return "<fieldset><legend>" + esc(l[1]) + '</legend><div class="eb-cf-list" data-list="' + l[0] + '">' + entryRows(d, l[0]) + "</div></fieldset>";
      }).join("") +
      '<fieldset><legend>Spellcasting</legend><div class="eb-cf-grid cf-cast">' +
      input("_cast.name", "Spellcasting from", c.name, "Wizard") + input("_cast.ability", "Ability", c.ability, "Intelligence") +
      input("_cast.save_dc", "Spell save DC", c.save_dc, "13", false, "n") + input("_cast.attack", "Spell attack bonus", c.attack, "5", false, "n") +
      "</div>" + '<div class="cf-slots"><span>Slots</span>' + ORD.slice(1).map(function (o, n) {
        return "<label>" + o + ' <input type="number" min="0" max="20" data-p="_cast.slots.' + (n + 1) + '" value="' + esc(val((c.slots || {})[n + 1])) + '"></label>';
      }).join("") + "</div>" +
      '<div class="eb-cf-list" data-list="_spells">' + spellRows(d) + "</div></fieldset>" +
      '<fieldset><legend>Money</legend><div class="cf-coins">' + COINS.map(function (k) {
        return "<label>" + k + ' <input type="number" min="0" data-p="currency.' + k + '" value="' + esc(val(d.currency[k])) + '"></label>';
      }).join("") + "</div></fieldset>" +
      '<fieldset><legend>Inventory</legend><div class="eb-cf-list" data-list="inventory">' + itemRows(d) + "</div></fieldset>" +
      '<fieldset><legend>Persona &amp; backstory</legend><div class="eb-cf-grid">' +
      PERSONA.map(function (f) { return input("persona." + f[0], f[1], p[f[0]], "", f[2]); }).join("") +
      '<label class="eb-w2">Personality traits (one per line) <textarea data-p="persona.traits" rows="2">' + esc((p.traits || []).join("\n")) + "</textarea></label>" +
      '<label class="eb-w2">Backstory (a blank line starts a new paragraph) <textarea data-p="persona.backstory" rows="6">' + esc(p.backstory || "") + "</textarea></label>" +
      "</div></fieldset>" +
      (opts.dm ? '<fieldset><legend>DM note</legend><textarea data-p="note" rows="3" placeholder="Shown at the bottom of the card - never on the players\' site.">' +
        esc(d.note || "") + "</textarea></fieldset>" : "") +
      "</div>";
  }

  // ------------------------------------------------------------ the form into the draft
  function read(box, d) {
    box.querySelectorAll("[data-p]").forEach(function (el) {
      var path = el.getAttribute("data-p").split("."), v = el.value, at = d;
      if (path[0] === "persona" && path[1] === "traits") v = v.split("\n").map(function (x) { return x.trim(); }).filter(Boolean);
      for (var i = 0; i < path.length - 1; i++) {
        if (!at[path[i]] || typeof at[path[i]] !== "object") at[path[i]] = {};
        at = at[path[i]];
      }
      at[path[path.length - 1]] = v;
    });
    box.querySelectorAll("[data-l]").forEach(function (el) {
      var row = d[el.getAttribute("data-l")][+el.getAttribute("data-i")];
      if (row) row[el.getAttribute("data-k")] = el.type === "checkbox" ? el.checked : el.value;
    });
  }
  function rows(d, key) { return key === "inventory" ? itemRows(d) : key === "_spells" ? spellRows(d) : entryRows(d, key); }
  function attach(box, d, onChange) {
    function changed() { read(box, d); if (onChange) onChange(d); }
    box.addEventListener("input", changed);
    box.addEventListener("change", changed);
    box.addEventListener("click", function (ev) {
      var t = ev.target, key = t.getAttribute("data-add") || t.getAttribute("data-rm");
      if (!key || !d[key]) return;
      read(box, d);
      if (t.hasAttribute("data-add")) d[key].push(key === "inventory" ? { name: "", qty: 1 } : key === "_spells" ? { name: "", level: 1 } : { name: "", text: "" });
      else d[key].splice(+t.getAttribute("data-i"), 1);
      var list = box.querySelector('[data-list="' + key + '"]');
      list.innerHTML = rows(d, key);
      if (t.hasAttribute("data-add")) {
        var names = list.querySelectorAll('[data-k="name"]');
        if (names.length) names[names.length - 1].focus();
      }
      if (onChange) onChange(d);
    });
    box.addEventListener("keydown", function (ev) {
      if (ev.key === "Enter" && ev.target.tagName === "INPUT") ev.preventDefault();   // Enter doesn't submit anything here
    });
  }

  // ------------------------------------------------------------ the draft as a card
  function card(d) {
    var out = {};
    IDENTITY.forEach(function (f) { if (f[0] in d) out[f[0]] = squash(d[f[0]]); });   // the DM's form has these
    BASICS.concat(DEFENSE, DETAILS).forEach(function (f) { out[f[0]] = squash(d[f[0]]); });
    NUMBERS.forEach(function (k) { var n = int(out[k]); out[k] = n == null ? "" : n; });
    if ("note" in d) out.note = val(d.note).trim();
    out.abilities = {};
    ABIL.forEach(function (a) { var n = int(d.abilities[a]); if (n != null) out.abilities[a] = n; });
    out.proficiencies = {};
    PROFS.forEach(function (f) { var s = squash(d.proficiencies[f[0]]); if (s) out.proficiencies[f[0]] = s; });
    ENTRIES.forEach(function (l) {
      out[l[0]] = d[l[0]].map(function (e) { return { name: squash(e.name), text: squash(e.text) }; })
        .filter(function (e) { return e.name || e.text; });
    });
    out.currency = {};
    COINS.forEach(function (k) { var n = int(d.currency[k]); if (n) out.currency[k] = n; });
    out.inventory = d.inventory.filter(function (i) { return squash(i.name); }).map(function (i) {
      var item = { name: squash(i.name) }, q = int(i.qty);
      if (q != null && q !== 1) item.qty = q;
      ["equipped", "magic", "attuned", "private"].forEach(function (k) { if (i[k]) item[k] = true; });
      return item;
    });
    out.persona = {};
    Object.keys(d.persona).forEach(function (k) {
      var v = d.persona[k];
      if (k === "traits") { if (v && v.length) out.persona.traits = v; }
      else if (k === "backstory") { if (val(v).trim()) out.persona.backstory = val(v).trim(); }
      else if (squash(v)) out.persona[k] = squash(v);
    });
    // Spellcasting: the form's one, then any others the card had.
    var c = d._cast, cast = { name: squash(c.name) || squash(d["class"]).replace(/\s*\(.*$/, "") || "Spellcasting" };
    if (squash(c.ability)) cast.ability = squash(c.ability);
    if (int(c.save_dc) != null) cast.save_dc = int(c.save_dc);
    if (int(c.attack) != null) cast.attack = int(c.attack);
    var slots = {};
    Object.keys(c.slots || {}).forEach(function (l) { var n = int(c.slots[l]); if (n) slots[l] = n; });
    if (Object.keys(slots).length) cast.slots = slots;
    if (c.pact) cast.pact = true;
    var spells = d._spells.filter(function (s) { return squash(s.name); });
    var cantrips = spells.filter(function (s) { return !+s.level; }).map(function (s) { return squash(s.name); });
    var leveled = spells.filter(function (s) { return +s.level; }).map(function (s) {
      var x = { name: squash(s.name), level: +s.level };
      if (s.prepared) x.prepared = true;
      return x;
    });
    if (cantrips.length) cast.cantrips = cantrips;
    if (leveled.length) cast.spells = leveled;
    var any = cast.ability || cast.save_dc != null || cast.attack != null || cast.slots || cantrips.length || leveled.length || squash(c.name);
    out.spellcasting = (any ? [cast] : []).concat((d.spellcasting || []).slice(1));
    // Untouched by the form: kept as they were (the portrait, privacy marks, where it came from, its version).
    ["portrait", "private", "source", "rev"].forEach(function (k) { if (d[k] !== undefined) out[k] = d[k]; });
    return out;
  }

  window.codexCardForm = { draft: draft, html: html, attach: attach, read: read, card: card };
})();
