/* The Party page: the party table and one full-width card per character, drawn from the data
   hooks/campaign.py embeds ({{ party-cards }}: a <script class="party-data"> block). On the players'
   site that data has already lost the DM's notes and anything a player marked private.
   Items a character carries (data/items, holder:) are written into the page as [[mentions]] so they
   keep their hover cards; this moves them into the cards. party-editor.js (Edit, on the site at home)
   runs after this and finds the cards by .pc-card[data-pc].
   On the players' site online, docs/players/party-live.js swaps in the live cards from the players'
   worker and calls window.codexParty.draw(data) again whenever one changes; each draw ends with a
   "codex:party-drawn" event on the cards' container.
   Live status (data.status, by card id): current HP, temporary HP, conditions, inspiration, spell slots
   and hit dice used, death saves - shown under each card's numbers; with the treasury (data.treasury)
   at the top. Whoever may change them (a player on their own card, the DM at home: data.dm_live) gets
   the controls, and each change goes to window.codexParty.send(kind, change), which the page sets:
   party-live.js (the players' site) or party-editor.js (the DM's site, through the save helper). */
(function () {
  var ABIL = ["str", "dex", "con", "int", "wis", "cha"];
  var ABIL_NAME = { str: "Str", dex: "Dex", con: "Con", int: "Int", wis: "Wis", cha: "Cha" };
  var drawCard = null;   // the last render's card(), for previews (codexParty.preview)
  var CONDITIONS = ["Blinded", "Charmed", "Deafened", "Frightened", "Grappled", "Incapacitated", "Invisible", "Paralyzed",
    "Petrified", "Poisoned", "Prone", "Restrained", "Stunned", "Unconscious", "Exhaustion", "Concentrating"];
  var HIT_DIE = { barbarian: 12, fighter: 10, paladin: 10, ranger: 10, sorcerer: 6, wizard: 6 };
  var ORD = ["", "1st", "2nd", "3rd", "4th", "5th", "6th", "7th", "8th", "9th"];
  var COINS = ["pp", "gp", "ep", "sp", "cp"];

  // As publish/players/party.mjs works them out.
  function hitDie(c) {
    var m = String(c.hp_formula || "").match(/d(\d+)/);
    if (m) return +m[1];
    return HIT_DIE[String(c["class"] || "").toLowerCase().split(/[\s(]/)[0]] || 8;
  }
  function slotTotals(c) {
    var out = {};
    (c.spellcasting || []).forEach(function (sc, i) {
      Object.keys(sc.slots || {}).forEach(function (l) { if (+sc.slots[l] > 0) out[i + ":" + l] = +sc.slots[l]; });
    });
    return out;
  }

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }
  // The little Markdown card text uses: **bold**, *italic*, and paragraphs.
  function md(s) {
    return esc(s).replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>").replace(/\*([^*]+)\*/g, "<em>$1</em>");
  }
  function paras(s) {
    return String(s || "").split(/\n\s*\n/).filter(function (p) { return p.trim(); })
      .map(function (p) { return "<p>" + md(p.trim()) + "</p>"; }).join("");
  }
  function signed(n) { n = +n; return (n >= 0 ? "+" : "−") + Math.abs(n); }
  function mod(score) { return Math.floor((+score - 10) / 2); }
  function prof(level) { return 2 + Math.floor((Math.max(1, +level || 1) - 1) / 4); }
  function initials(name) {
    return String(name || "?").replace(/"[^"]*"/g, "").split(/\s+/).filter(Boolean)
      .map(function (w) { return w[0]; }).slice(0, 2).join("").toUpperCase();
  }

  // carried: the campaign's items for each card, by index ("party" for what the party shares) - see init.
  function render(root, data, carried) {
    var dm = data.audience !== "players";
    var cards = data.cards || [];

    // Locks show to those who see the private parts: the DM, and the card's own player (live, data.me).
    function isPrivate(c, path) { return (dm || c.id === data.me) && (c.private || []).indexOf(path) >= 0; }
    function lock(c, path) { return isPrivate(c, path) ? ' <span class="pcx-lock" title="Private: only the player and the DM see this">🔒</span>' : ""; }

    // ------------------------------------------------------------ the roster: a tile per character
    function avatar(c, cls) {
      return c.portrait ? '<img class="' + cls + '" src="' + esc(c.portrait) + '" alt="">' :
        '<span class="' + cls + ' pcx-initials">' + esc(initials(c.character)) + "</span>";
    }
    function pill(k, v, title) {
      return '<span class="pcx-pill" title="' + esc(title) + '"><i>' + k + "</i>" + esc(v != null && v !== "" ? v : "\u2014") + "</span>";
    }
    // "17/24" when the current HP is known to this viewer and not full; the card's HP otherwise.
    function hpText(c, st) {
      if (!st || st.hp === undefined || st.hp === null || c.hp == null) return c.hp;
      return st.hp + "/" + c.hp;
    }
    var table = '<div class="pcx-roster">' + cards.map(function (c) {
      var what = [c.race, c["class"]].filter(Boolean).join(" ");
      return '<a class="pcx-tile" href="#' + esc(c.id) + '" data-go="' + esc(c.id) + '">' + avatar(c, "pcx-av") +
        '<span class="pcx-tile-who"><b>' + esc(c.character) + "</b>" +
        '<span class="pcx-dim">' + esc(what) + (c.level ? " \u00b7 level " + esc(c.level) : "") + "</span>" +
        (c.player ? '<span class="pcx-dim">' + esc(c.player) + "</span>" : "") + "</span>" +
        '<span class="pcx-pills">' + pill("AC", c.ac, "Armor Class") + pill("HP", hpText(c, (data.status || {})[c.id]), "Hit points") + pill("Perc.", c.passive_perception, "Passive Perception") + "</span></a>";
    }).join("") + "</div>";

    // ------------------------------------------------------------ a card
    function stat(k, v, s) {
      return '<div class="pcx-stat"><div class="k">' + k + '</div><div class="v">' + esc(v) + '</div><div class="s">' + (s ? esc(s) : "&nbsp;") + "</div></div>";
    }
    function section(title, count, body, open) {
      return body ? '<details class="pcx-sec" data-sec="' + esc(title) + '"' + (open ? " open" : "") + "><summary>" + title +
        (count ? ' <span class="pcx-count">· ' + count + "</span>" : "") + '</summary><div class="pcx-sec-body">' + body + "</div></details>" : "";
    }
    function entries(list) {
      return (list || []).map(function (e) {
        return '<div class="pcx-feat"><b>' + esc(e.name) + ".</b> " + md(e.text) + "</div>";
      }).join("");
    }

    // ------------------------------------------------------------ live status (see the comment at the top)
    function canChange(c) { return !!(data.dm_live || (data.live && data.me && c.id === data.me)); }
    function pips(n, used, attrs, title) {
      var out = "";
      for (var i = 0; i < n; i++) {
        var spent = i >= n - used;
        out += '<button type="button" class="pcx-pip' + (spent ? " used" : "") + '"' + attrs + ' data-n="' + i + '" title="' + esc(title) +
          (spent ? " (used)" : "") + '"' + (attrs ? "" : " disabled") + "></button>";
      }
      return out;
    }
    function live(c) {
      var st = (data.status || {})[c.id];
      if (!st) return "";
      var edit = canChange(c), at = edit ? ' data-st-id="' + esc(c.id) + '"' : "";
      var bits = [];
      if (st.hp !== undefined && c.hp != null) {
        var cur = st.hp == null ? c.hp : st.hp, pct = Math.max(0, Math.min(100, Math.round(100 * cur / (c.hp || 1))));
        var state = cur === 0 ? " down" : cur <= c.hp / 2 ? " bloodied" : "";
        bits.push('<div class="pcx-hp' + state + '"><div class="pcx-hp-text"><b>' + cur + "</b> / " + c.hp + " HP" +
          (st.temp ? ' <span class="pcx-temp">+' + st.temp + " temp</span>" : "") + (cur === 0 ? ' <span class="pcx-down">down</span>' : "") +
          '</div><div class="pcx-hp-bar"><span style="width: ' + pct + '%"></span></div></div>');
        if (cur === 0) {
          bits.push('<div class="pcx-death"><span>Death saves</span> <span class="pcx-dlbl">✓</span>' +
            pips(3, (st.death || {}).s || 0, edit ? at + ' data-st="death" data-kind="s"' : "", "success") +
            ' <span class="pcx-dlbl">✗</span>' + pips(3, (st.death || {}).f || 0, edit ? at + ' data-st="death" data-kind="f"' : "", "failure") + "</div>");
        }
      }
      var conds = (st.conds || []).map(function (cd, i) {
        return '<span class="pcx-cond">' + esc(cd.n) + (cd.r ? " · " + cd.r + " rd" : "") +
          (edit ? '<button type="button" class="pcx-x"' + at + ' data-st="cond-rm" data-i="' + i + '" title="Remove">×</button>' : "") + "</span>";
      }).join("");
      var insp = st.insp || edit ? '<button type="button" class="pcx-insp' + (st.insp ? " on" : "") + '"' + (edit ? at + ' data-st="insp"' : " disabled") +
        ' title="' + (st.insp ? "Has inspiration" : "No inspiration") + '">★ Inspiration</button>' : "";
      if (conds || insp) bits.push('<div class="pcx-conds">' + insp + conds + "</div>");
      var totals = st.slots ? slotTotals(c) : {};
      var slots = Object.keys(totals).sort().map(function (k) {
        var l = +k.split(":")[1];
        return '<span class="pcx-slot"><i>' + ORD[l] + (((c.spellcasting || [])[+k.split(":")[0]] || {}).pact ? " (pact)" : "") + "</i>" +
          pips(totals[k], (st.slots || {})[k] || 0, edit ? at + ' data-st="slot" data-key="' + k + '"' : "", "spell slot") + "</span>";
      }).join("");
      var hd = c.level ? '<span class="pcx-slot"><i>Hit dice d' + hitDie(c) + "</i>" +
        pips(+c.level, st.hd || 0, edit ? at + ' data-st="hd"' : "", "hit die") + "</span>" : "";
      if (slots || (edit && hd)) bits.push('<div class="pcx-slots">' + (slots ? "<b>Spell slots</b> " + slots : "") + (edit ? hd : "") + "</div>");
      if (edit) {
        bits.push('<div class="pcx-ctl">' +
          '<input type="number" min="0" class="pcx-amt" placeholder="HP" aria-label="Amount"' + at + ">" +
          '<button type="button" class="eb-act"' + at + ' data-st="dmg">Damage</button>' +
          '<button type="button" class="eb-act"' + at + ' data-st="heal">Heal</button>' +
          '<button type="button" class="eb-act"' + at + ' data-st="temp" title="Set temporary HP to the amount">Temp HP</button>' +
          '<select class="pcx-addcond"' + at + ' aria-label="Add a condition"><option value="">+ Condition</option>' +
          CONDITIONS.map(function (n) { return "<option>" + n + "</option>"; }).join("") + "</select>" +
          '<span class="pcx-rests"><button type="button" class="eb-act"' + at + ' data-st="short" title="Spend hit dice to heal (rolled for you)">Short rest</button>' +
          '<button type="button" class="eb-act"' + at + ' data-st="long" title="Full HP, spell slots back, half your hit dice back">Long rest</button></span>' +
          "</div>");
      }
      return bits.length ? '<div class="pcx-live eb">' + bits.join("") + "</div>" : "";
    }

    function card(c) {
      var scores = c.abilities || {};
      var saveText = c.saves || "";
      var saveProf = {};
      saveText.split(",").forEach(function (part) {
        var m = part.trim().match(/^(\w+)\s+([+−-]?\d+)/);
        if (m) saveProf[m[1].slice(0, 3).toLowerCase()] = m[2].replace("−", "-");
      });
      var pb = prof(c.level || data.level);
      var init = c.initiative != null ? c.initiative : (scores.dex != null ? mod(scores.dex) : null);
      var portrait = c.portrait ? '<img class="pcx-portrait" src="' + esc(c.portrait) + '" alt="">' :
        '<div class="pcx-portrait pcx-initials">' + esc(initials(c.character)) + "</div>";
      var sub = [[c.race, c["class"]].filter(Boolean).join(" ") + (c.level ? " " + c.level : ""), c.background].filter(Boolean).join(" · ");
      var meta = [c.player, c.source && c.source.from ? "imported from " + c.source.from + (c.source.imported ? ", " + c.source.imported : "") : ""].filter(Boolean).join(" · ");

      var head = '<div class="pcx-head">' + portrait + '<div class="pcx-who"><h3 class="pcx-name">' + esc(c.character) + "</h3>" +
        '<div class="pcx-sub">' + esc(sub) + "</div>" + (meta ? '<div class="pcx-dim">' + esc(meta) + "</div>" : "") + "</div></div>";
      var strip = '<div class="pcx-strip">' +
        stat("AC", c.ac != null ? c.ac : "—", c.ac_note) + stat("HP", c.hp != null ? c.hp : "—", c.hp_formula) +
        stat("Speed", String(c.speed || "—").split(",")[0].replace(" ft.", ""), (c.speed || "").indexOf(",") > 0 ? c.speed.split(",").slice(1).join(",").trim() : "ft.") +
        stat("Init", init != null ? signed(init) : "—") +
        stat("Passive Perc.", c.passive_perception != null ? c.passive_perception : "—") + stat("Prof.", signed(pb)) + "</div>";

      var abil = '<div class="pcx-abil">' + ABIL.map(function (a) {
        var s = scores[a], saved = saveProf[a];
        return '<div class="pcx-ab"><div class="k">' + a.toUpperCase() + '</div><div class="m">' + (s != null ? signed(mod(s)) : "—") +
          '</div><div class="sc">' + (s != null ? s : "") + '</div><div class="sv' + (saved ? " p" : "") + '">save ' +
          (saved ? signed(+saved) : s != null ? signed(mod(s)) : "—") + "</div></div>";
      }).join("") + "</div>";
      var facts = [["Senses", "senses"], ["Languages", "languages"], ["Resistances", "resistances"], ["Immunities", "immunities"],
                   ["Condition immunities", "condition_immunities"]]
        .filter(function (f) { return c[f[1]]; })
        .map(function (f) { return '<div><b>' + f[0] + "</b> " + esc(c[f[1]]) + lock(c, f[1]) + "</div>"; }).join("");
      var profs = c.proficiencies || {};
      ["armor", "weapons", "tools"].forEach(function (k) {
        if (profs[k]) facts += '<div><b>' + k.charAt(0).toUpperCase() + k.slice(1) + "</b> " + esc(profs[k]) + "</div>";
      });
      var skills = (c.skills || "").split(",").map(function (s) { return s.trim(); }).filter(Boolean).map(function (s) {
        var m = s.match(/^(.*?)\s+([+−-]?\d+)$/);
        return m ? '<div><span>' + esc(m[1]) + "</span><span>" + esc(m[2]) + "</span></div>" : "<div><span>" + esc(s) + "</span></div>";
      }).join("");
      var body = '<div class="pcx-body"><div class="pcx-col">' + abil + '<div class="pcx-facts">' + facts + "</div></div>" +
        '<div class="pcx-col"><div class="pcx-lbl">Skills' + lock(c, "skills") + "</div>" +
        (skills ? '<div class="pcx-skills">' + skills + "</div>" : '<div class="pcx-dim">—</div>') + "</div></div>";

      // Actions, bonus actions and reactions together; features; spellcasting; inventory; persona.
      var acts = entries(c.actions) +
        (c.bonus_actions && c.bonus_actions.length ? '<div class="pcx-lbl">Bonus actions</div>' + entries(c.bonus_actions) : "") +
        (c.reactions && c.reactions.length ? '<div class="pcx-lbl">Reactions</div>' + entries(c.reactions) : "");
      var nActs = (c.actions || []).length + (c.bonus_actions || []).length + (c.reactions || []).length;

      var spells = (c.spellcasting || []).map(function (sc) {
        var slots = sc.slots ? Object.keys(sc.slots).sort(function (a, b) { return a - b; }).map(function (l) {
          return '<span class="pcx-chip">' + l + (l == 1 ? "st" : l == 2 ? "nd" : l == 3 ? "rd" : "th") + " ×" + sc.slots[l] + "</span>";
        }).join(" ") : "";
        var byLevel = {};
        (sc.spells || []).forEach(function (s) { (byLevel[s.level] = byLevel[s.level] || []).push(s); });
        var lists = (sc.cantrips && sc.cantrips.length ? "<div><b>Cantrips</b> " + esc(sc.cantrips.join(", ")) + "</div>" : "") +
          Object.keys(byLevel).sort(function (a, b) { return a - b; }).map(function (l) {
            return "<div><b>" + (l == 0 ? "Cantrips" : l + (l == 1 ? "st" : l == 2 ? "nd" : l == 3 ? "rd" : "th") + " level") + "</b> " +
              byLevel[l].map(function (s) { return esc(s.name) + (s.prepared ? '<span class="pcx-prep" title="prepared">●</span>' : ""); }).join(", ") + "</div>";
          }).join("");
        return '<div class="pcx-cast"><div class="pcx-cast-head"><b>' + esc(sc.name) + "</b>" +
          (sc.ability ? " · " + esc(sc.ability) : "") + (sc.save_dc ? " · save DC " + esc(sc.save_dc) : "") +
          (sc.attack != null ? " · " + signed(sc.attack) + " to hit" : "") + (slots ? '<span class="pcx-slots">' + slots + "</span>" : "") +
          "</div>" + lists + "</div>";
      }).join("");
      var nSpells = (c.spellcasting || []).reduce(function (n, sc) { return n + (sc.spells || []).length + (sc.cantrips || []).length; }, 0);

      var inv = c.inventory || [];
      var key = inv.filter(function (i) { return i.equipped || i.magic || i.attuned; });
      var rest = inv.filter(function (i) { return !(i.equipped || i.magic || i.attuned); });
      function item(i) {
        return "<li><span>" + esc(i.name) +
          (i.attuned ? ' <span class="pcx-tag gold">attuned</span>' : i.magic ? ' <span class="pcx-tag gold">magic</span>' : "") +
          (i.equipped ? ' <span class="pcx-tag">equipped</span>' : "") +
          ((dm || c.id === data.me) && i.private ? ' <span class="pcx-lock" title="Private: only the player and the DM see this">🔒</span>' : "") +
          "</span><span>" + (i.qty && i.qty !== 1 ? "×" + esc(i.qty) : "") + "</span></li>";
      }
      var money = c.currency ? ["pp", "gp", "ep", "sp", "cp"].filter(function (k) { return c.currency[k]; })
        .map(function (k) { return '<span class="pcx-coin"><b>' + esc(c.currency[k]) + "</b> " + k + "</span>"; }).join("") : "";
      var campaign = carried[String(c.index)];
      var invBody = (campaign ? '<div class="pcx-lbl">From the campaign</div><div class="pcx-campaign" data-from="' + esc(c.index) + '"></div>' : "") +
        (money ? '<div class="pcx-coins">' + money + lock(c, "currency") + "</div>" : "") +
        (key.length ? '<ul class="pcx-inv">' + key.map(item).join("") + "</ul>" : "") +
        (rest.length ? '<details class="pcx-more"><summary>' + rest.length + " more item" + (rest.length === 1 ? "" : "s") +
          "</summary><ul class=\"pcx-inv\">" + rest.map(item).join("") + "</ul></details>" : "");
      var nInv = inv.length + (campaign ? campaign.querySelectorAll("a, .ref").length : 0);

      var p = c.persona || {};
      var personaBody = [["Alignment", "alignment"], ["Appearance", "appearance"], ["Ideal", "ideal"], ["Bond", "bond"],
                         ["Flaw", "flaw"], ["Allies", "allies"], ["Deity", "deity"]]
        .filter(function (f) { return p[f[1]]; })
        .map(function (f) { return "<div><b>" + f[0] + "</b> " + md(p[f[1]]) + lock(c, "persona." + f[1]) + "</div>"; }).join("");
      if (p.traits && p.traits.length) personaBody = "<div><b>Personality</b> " + p.traits.map(md).join(" ") + lock(c, "persona.traits") + "</div>" + personaBody;
      if (p.backstory) personaBody += '<div class="pcx-lbl">Backstory' + lock(c, "persona.backstory") + '</div><div class="pcx-story">' + paras(p.backstory) + "</div>";

      var note = dm && c.note ? '<div class="pcx-note"><b>DM note</b> ' + md(c.note) + "</div>" : "";
      var empty = !c.ac && !c.hp && !acts && !(c.features || []).length ?
        '<div class="pcx-empty">' + (dm ? "No card details yet — import a CCC5e character, or fill it in with Edit." :
          "This card hasn't been filled in yet.") + "</div>" : "";

      return head + strip + live(c) + body + empty +
        section("Actions", nActs, acts) +
        section("Features &amp; traits", (c.features || []).length, entries(c.features)) +
        section("Spellcasting", nSpells ? nSpells + " spells" : "", spells) +
        section("Inventory", nInv ? nInv + " items" : "", invBody) +
        section("Persona &amp; backstory", "", personaBody) + note;
    }

    drawCard = card;

    function treasury() {
      var t = data.treasury;
      if (!t) return "";
      var edit = !!(data.dm_live || (data.live && data.me));
      var coins = COINS.filter(function (k) { return (t.coins || {})[k]; }).map(function (k) {
        return '<span class="pcx-coin"><b>' + esc(t.coins[k]) + "</b> " + k + "</span>";
      }).join("") || '<span class="pcx-dim">No coin yet.</span>';
      var items = (t.items || []).map(function (i) {
        return "<li><span>" + esc(i.name) + "</span><span>" + (i.qty > 1 ? "×" + esc(i.qty) : "") +
          (edit ? ' <button type="button" class="pcx-x" data-tr="take" data-name="' + esc(i.name) + '" title="Take one out">−</button>' : "") + "</span></li>";
      }).join("");
      var log = (data.treasury_log || []).map(function (l) {
        return "<li>" + esc(new Date(l.at).toLocaleDateString()) + " · <b>" + esc(l.by) + "</b> " + esc(l.text) + "</li>";
      }).join("");
      var form = edit ? '<div class="pcx-tr-form eb">' + COINS.map(function (k) {
          return '<label>' + k + ' <input type="number" min="0" data-coin="' + k + '"></label>';
        }).join("") + '<input class="pcx-tr-note" placeholder="What for (optional)">' +
        '<button type="button" class="eb-act" data-tr="in">Put in</button><button type="button" class="eb-act" data-tr="out">Take out</button>' +
        '<span class="pcx-tr-item"><input class="pcx-tr-name" placeholder="Add an item"><input type="number" min="1" value="1" class="pcx-tr-qty" aria-label="How many">' +
        '<button type="button" class="eb-act" data-tr="add">Add</button></span></div>' : "";
      var showHp = data.dm_live ? '<label class="pcx-showhp eb"><input type="checkbox" data-st="show-hp"' + (data.show_hp ? " checked" : "") +
        "> Players see each other's current HP</label>" : "";
      return showHp + '<details class="pcx-sec pcx-treasury" data-sec="treasury"' + (treasuryOpen ? " open" : "") + '><summary>Party treasury' +
        ' <span class="pcx-count">· ' + COINS.filter(function (k) { return (t.coins || {})[k]; }).map(function (k) { return t.coins[k] + " " + k; }).join(", ") +
        "</span></summary>" + '<div class="pcx-sec-body"><div class="pcx-coins">' + coins + "</div>" +
        (items ? '<ul class="pcx-inv">' + items + "</ul>" : "") + form +
        (log ? '<details class="pcx-more"><summary>What changed</summary><ul class="pcx-log">' + log + "</ul></details>" : "") +
        "</div></details>";
    }
    var shared = carried.party ? '<div class="pcx-shared"><b>Shared by the party:</b> <span class="pcx-shared-items"></span></div>' : "";
    var top = root.querySelector(".pcx-top");
    var wasOpen = top && top.querySelector(".pcx-treasury");
    var treasuryOpen = wasOpen ? wasOpen.open : false;
    if (!top) {
      top = document.createElement("div");
      top.className = "pcx-top";
      root.insertBefore(top, root.firstChild);
    }
    top.innerHTML = table + shared + treasury();
    // Each card into its placeholder (hooks/campaign.py writes one per character, with its anchor),
    // keeping which sections were open when it's drawn again.
    cards.forEach(function (c) {
      var slot = root.querySelector('section.pcx[data-pc="' + c.index + '"]');
      if (!slot) {
        slot = document.createElement("section");
        slot.className = "pc-card pcx";
        slot.id = c.id;
        slot.setAttribute("data-pc", c.index);
        root.appendChild(slot);
      }
      var open = {}, drawn = slot.querySelector(".pcx-head");
      slot.querySelectorAll("details[data-sec]").forEach(function (d) { open[d.getAttribute("data-sec")] = d.open; });
      slot.innerHTML = card(c);
      if (drawn) slot.querySelectorAll("details[data-sec]").forEach(function (d) {
        var was = open[d.getAttribute("data-sec")];
        if (was !== undefined) d.open = was;
      });
    });
    // The campaign's items, with their hover cards, into their cards.
    cards.forEach(function (c) {
      var from = carried[String(c.index)], to = root.querySelector('#' + CSS.escape(c.id) + " .pcx-campaign");
      if (from && to) while (from.firstChild) to.appendChild(from.firstChild);
    });
    if (carried.party) {
      var to = root.querySelector(".pcx-shared-items");
      while (carried.party.firstChild) to.appendChild(carried.party.firstChild);
    }
    // Unwrap the single <p> Markdown put around each list of mentions.
    root.querySelectorAll(".pcx-campaign > p, .pcx-shared-items > p").forEach(function (p) {
      while (p.firstChild) p.parentNode.insertBefore(p.firstChild, p);
      p.remove();
    });
    root.dispatchEvent(new CustomEvent("codex:party-drawn", { detail: data }));
  }

  // Before drawing again: the campaign's items back where they came from, to be moved in afresh.
  function gather(root, carried) {
    root.querySelectorAll(".pcx-campaign[data-from], .pcx-shared-items").forEach(function (el) {
      var home = carried[el.getAttribute("data-from") || "party"];
      if (home) while (el.firstChild) home.appendChild(el.firstChild);
    });
  }

  function go(id) {
    var card = document.getElementById(id);
    if (!card) return;
    card.scrollIntoView({ behavior: "smooth", block: "start" });
    card.classList.remove("pcx-flash");
    void card.offsetWidth;
    card.classList.add("pcx-flash");
  }

  function init() {
    var blob = document.querySelector("script.party-data");
    var root = document.querySelector(".pc-cards.party");
    if (!blob || !root || root.querySelector(".pcx-head")) return;
    var data;
    try { data = JSON.parse(blob.textContent); } catch (e) { return; }
    var carried = {};
    var held = root.querySelector(".party-carried");
    if (held) held.querySelectorAll("[data-carried]").forEach(function (el) { carried[el.getAttribute("data-carried")] = el; });
    render(root, data, carried);
    window.codexParty = {
      data: data,
      draw: function (next) {
        gather(root, carried);
        window.codexParty.data = next;
        render(root, next, carried);
      },
      // One card's HTML as the page would draw it (the Edit form's preview).
      preview: function (c) {
        return drawCard ? '<section class="pc-card pcx">' + drawCard(Object.assign({ index: "preview", id: "pcx-preview" }, c)) + "</section>" : "";
      },
    };
    // ------------------------------------------------------------ the live controls -> codexParty.send
    function send(kind, change) {
      var to = window.codexParty.send;
      if (!to) return;
      root.classList.add("pcx-busy");
      Promise.resolve(to(kind, change)).catch(function () {}).then(function () { root.classList.remove("pcx-busy"); });
    }
    function cardOf(id) { return (window.codexParty.data.cards || []).filter(function (c) { return c.id === id; })[0]; }
    function statusOf(id) { return ((window.codexParty.data.status || {})[id]) || {}; }
    function amount(el) {
      var box = el.closest(".pcx-live"), n = parseInt((box && box.querySelector(".pcx-amt") || {}).value, 10);
      return isNaN(n) || n < 0 ? null : n;
    }
    function statusAction(el) {
      var id = el.getAttribute("data-st-id"), what = el.getAttribute("data-st"), c = cardOf(id), st = statusOf(id), n;
      if (!c && what !== "show-hp") return;
      if (what === "show-hp") return send("settings", { show_hp: el.checked });
      if (what === "dmg" || what === "heal") {
        n = amount(el);
        if (n == null) return el.closest(".pcx-live").querySelector(".pcx-amt").focus();
        return send("status", { id: id, change: { hp_delta: what === "dmg" ? -n : n } });
      }
      if (what === "temp") { n = amount(el); return send("status", { id: id, change: { temp: n || 0 } }); }
      if (what === "insp") return send("status", { id: id, change: { insp: !st.insp } });
      if (what === "cond-rm") {
        return send("status", { id: id, change: { conds: (st.conds || []).filter(function (x, i) { return i !== +el.getAttribute("data-i"); }) } });
      }
      // A pip: tap a full one to spend it, a spent one to get it back.
      if (what === "slot" || what === "hd") {
        var key = el.getAttribute("data-key"), used = what === "hd" ? st.hd || 0 : (st.slots || {})[key] || 0;
        used += el.classList.contains("used") ? -1 : 1;
        if (what === "hd") return send("status", { id: id, change: { hd: used } });
        var slots = Object.assign({}, st.slots);
        slots[key] = used;
        return send("status", { id: id, change: { slots: slots } });
      }
      if (what === "death") {
        var kind = el.getAttribute("data-kind"), d = Object.assign({ s: 0, f: 0 }, st.death);
        d[kind] += el.classList.contains("used") ? -1 : 1;
        return send("status", { id: id, change: { death: d } });
      }
      if (what === "short") {
        var die = hitDie(c), left = (+c.level || 0) - (st.hd || 0);
        if (left <= 0) return window.alert("No hit dice left - they come back with a long rest.");
        var spend = parseInt(window.prompt("How many hit dice (d" + die + ") to spend? " + left + " left.", "1"), 10);
        if (!(spend > 0)) return;
        spend = Math.min(spend, left);
        var con = Math.floor((((c.abilities || {}).con || 10) - 10) / 2), rolls = [], healed = 0;
        for (var i = 0; i < spend; i++) {
          var r = 1 + Math.floor(Math.random() * die);
          rolls.push(r);
          healed += Math.max(0, r + con);
        }
        var change = { hd: (st.hd || 0) + spend, hp_delta: healed };
        // Pact magic comes back on a short rest.
        var pact = {};
        Object.keys(st.slots || {}).forEach(function (k) { if (!((c.spellcasting || [])[+k.split(":")[0]] || {}).pact) pact[k] = st.slots[k]; });
        if (Object.keys(pact).length !== Object.keys(st.slots || {}).length) change.slots = pact;
        window.alert("Rolled " + rolls.join(" + ") + (con ? " with " + (con > 0 ? "+" : "") + con + " Con each" : "") + ": +" + healed + " HP.");
        return send("status", { id: id, change: change });
      }
      if (what === "long") {
        if (!window.confirm("Long rest for " + c.character + "? Full HP, spell slots back, and half their hit dice back.")) return;
        return send("status", { id: id, change: { hp: null, temp: 0, slots: {}, hd: Math.max(0, (st.hd || 0) - Math.max(1, Math.floor((+c.level || 1) / 2))),
                                                  death: { s: 0, f: 0 } } });
      }
    }
    function treasuryAction(el) {
      var box = el.closest(".pcx-sec-body"), what = el.getAttribute("data-tr");
      var note = (box.querySelector(".pcx-tr-note") || {}).value || "";
      if (what === "in" || what === "out") {
        var coins = {}, any = false;
        box.querySelectorAll("[data-coin]").forEach(function (x) {
          var n = parseInt(x.value, 10);
          if (n > 0) { coins[x.getAttribute("data-coin")] = what === "in" ? n : -n; any = true; }
        });
        if (!any) return box.querySelector("[data-coin]").focus();
        return send("treasury", { coins: coins, note: note });
      }
      if (what === "add") {
        var name = box.querySelector(".pcx-tr-name").value.trim();
        if (!name) return box.querySelector(".pcx-tr-name").focus();
        return send("treasury", { add: { name: name, qty: parseInt(box.querySelector(".pcx-tr-qty").value, 10) || 1 }, note: note });
      }
      if (what === "take") return send("treasury", { take: { name: el.getAttribute("data-name"), qty: 1 }, note: note });
    }
    root.addEventListener("change", function (ev) {
      var el = ev.target;
      if (el.matches("[data-st=show-hp]")) return statusAction(el);
      if (el.classList.contains("pcx-addcond") && el.value) {
        var id = el.getAttribute("data-st-id"), st = statusOf(id);
        var conds = (st.conds || []).filter(function (x) { return x.n !== el.value; }).concat([{ n: el.value, r: null }]);
        send("status", { id: id, change: { conds: conds } });
      }
    });
    root.addEventListener("keydown", function (ev) {   // Enter in the amount: damage (the likelier one at the table)
      if (ev.key === "Enter" && ev.target.classList.contains("pcx-amt")) {
        ev.preventDefault();
        statusAction(ev.target.closest(".pcx-live").querySelector('[data-st="dmg"]'));
      }
    });
    root.addEventListener("click", function (ev) {
      var st = ev.target.closest("button[data-st]");
      if (st) return statusAction(st);
      var tr = ev.target.closest("[data-tr]");
      if (tr) return treasuryAction(tr);
      var row = ev.target.closest("[data-go]");
      if (!row) return;
      ev.preventDefault();
      history.replaceState(null, "", "#" + row.getAttribute("data-go"));
      go(row.getAttribute("data-go"));
    });
    if (location.hash) setTimeout(function () { go(location.hash.slice(1)); }, 50);
    document.dispatchEvent(new CustomEvent("codex:party-ready"));
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
