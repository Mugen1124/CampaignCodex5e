/* Encounter builder. Creature data, stat blocks, the party, and the difficulty tables are
   embedded in the page at build time (a JSON block with id "eb-data"), so this works offline.
   Saving goes through the local save helper (tools/site_helper.py), which serve starts;
   without it, the builder shows the encounter as text to copy instead. */
(function () {
  "use strict";
  var HELPER = "http://127.0.0.1:8765";
  // Which campaign this page belongs to (hooks/campaign.py puts it in every page), so saved state
  // stays separate when two campaigns are served on one computer.
  var CAMPAIGN = (document.querySelector('meta[name="codex-campaign"]') || {}).content || "codex";
  // The online copy (publish) can't save: saving happens on the site at home. Served from
  // anywhere but this computer, the page doesn't try to reach the helper at all.
  var ONLINE = location.protocol !== "file:" && !/^(127\.0\.0\.1|localhost|\[::1\])$/.test(location.hostname);
  function helperFetch(url, opts) {
    return ONLINE ? Promise.reject(new Error("online copy")) : fetch(url, opts);
  }
  var STORE = CAMPAIGN + "-encounter-builder";

  function init() {
    var root = document.getElementById("eb-root");
    var dataEl = document.getElementById("eb-data");
    if (!root || !dataEl) return;
    var D = JSON.parse(dataEl.textContent);
    var byId = {};
    D.creatures.forEach(function (c) { byId[c.id] = c; });

    // ------------------------------------------------------------ state (kept across reloads)
    var state = { tray: [], level: D.party.level, size: D.party.size, name: "", location: "", id: "",
                  view: "active", editing: null, flash: null, cdraft: null, combat: null, initGroup: true };
    try { Object.assign(state, JSON.parse(localStorage.getItem(STORE) || "{}")); } catch (e) {}
    state.tray = state.tray.filter(function (t) { return byId[t.id]; });
    function persist() { try { localStorage.setItem(STORE, JSON.stringify(state)); } catch (e) {} }

    // ------------------------------------------------------------ helpers
    function crValue(cr) {
      if (String(cr).indexOf("/") > -1) { var p = cr.split("/"); return p[0] / p[1]; }
      return parseFloat(cr) || 0;
    }
    function esc(s) {
      return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) {
        return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
      });
    }
    function slug(s) { return String(s).toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, ""); }
    var SOURCE_NAMES = { campaign: "Campaign", custom: "Custom", tob: "Tome of Beasts", tob2: "Tome of Beasts 2", tob3: "Tome of Beasts 3", cc: "Creature Codex",
                         vgm: "Volo's", mtf: "Mordenkainen's", foes: "5e Foes" };
    Object.keys(D.sources || {}).forEach(function (k) {   // a monster sheet's own title names its source
      if (!SOURCE_NAMES[k] && k !== "srd") SOURCE_NAMES[k] = D.sources[k];
    });
    function sourceLabel(s) { return SOURCE_NAMES[s] || String(s).toUpperCase(); }
    function el(html) { var d = document.createElement("div"); d.innerHTML = html; return d.firstElementChild; }
    var CRS = ["0", "1/8", "1/4", "1/2"].concat(Array.from({ length: 30 }, function (_, i) { return String(i + 1); }));
    var types = Array.from(new Set(D.creatures.map(function (c) { return c.type; }).filter(Boolean))).sort();
    var sizes = ["Tiny", "Small", "Medium", "Large", "Huge", "Gargantuan"];

    // ------------------------------------------------------------ difficulty (2014 DMG)
    function multiplier(count, partySize) {
      var step = count <= 1 ? 1 : count === 2 ? 2 : count <= 6 ? 3 : count <= 10 ? 4 : count <= 14 ? 5 : 6;
      if (partySize < 3) step += 1; else if (partySize >= 6) step -= 1;
      step = Math.max(0, Math.min(step, D.multipliers.length - 1));
      return D.multipliers[step];
    }
    function difficulty() {
      var base = 0, count = 0;
      state.tray.forEach(function (t) { base += byId[t.id].xp * t.count; count += t.count; });
      var mult = multiplier(count, state.size);
      var adjusted = Math.floor(base * mult);
      var per = D.thresholds[String(state.level)] || [0, 0, 0, 0];
      var totals = per.map(function (x) { return x * state.size; });
      var label = count ? "Trivial" : "—";
      ["Easy", "Medium", "Hard", "Deadly"].forEach(function (n, i) { if (count && adjusted >= totals[i]) label = n; });
      return { base: base, count: count, mult: mult, adjusted: adjusted, totals: totals, label: label };
    }

    // ------------------------------------------------------------ layout
    root.innerHTML =
      '<div class="eb-top">' +
      ' <div class="eb-views">' +
      '  <button class="eb-vbtn" data-view="active">Active</button>' +
      '  <button class="eb-vbtn" data-view="archive">Archive</button>' +
      '  <button class="eb-vbtn" data-view="builder">Builder</button>' +
      '  <button class="eb-vbtn" data-view="initiative">Initiative</button>' +
      ' </div>' +
      ' <div class="eb-party">Party: <input type="number" class="eb-psize" min="1" max="10"> characters of level ' +
      '  <input type="number" class="eb-plevel" min="1" max="20"></div>' +
      '</div>' +
      '<div class="eb-flash"></div>' +
      '<div class="eb-listview">' +
      ' <div class="eb-listbar"><input type="search" class="eb-lq" placeholder="Search encounters…">' +
      '  <button class="eb-new md-button md-button--primary">New encounter</button></div>' +
      ' <div class="eb-enclist"></div>' +
      '</div>' +
      '<div class="eb-cols">' +
      ' <section class="eb-search">' +
      '  <div class="eb-filters">' +
      '   <input type="search" class="eb-q" placeholder="Search creatures…">' +
      '   <label>CR <select class="eb-crmin"></select> to <select class="eb-crmax"></select></label>' +
      '   <select class="eb-type"><option value="">Any type</option></select>' +
      '   <select class="eb-size"><option value="">Any size</option></select>' +
      '   <select class="eb-env"><option value="">Any environment</option></select>' +
      '   <select class="eb-source"><option value="">All sources</option><option value="campaign">Campaign</option>' +
      '    <option value="custom">Custom</option></select>' +
      '  </div>' +
      '  <div class="eb-countbar"><span class="eb-count"></span><button class="eb-newc md-button">New creature</button></div>' +
      '  <div class="eb-list">' +
      '   <div class="eb-row eb-head"><span></span><span>Name</span><span>CR</span><span>Size</span><span>Type</span><span>Source</span></div>' +
      '   <div class="eb-rows"></div>' +
      '  </div>' +
      ' </section>' +
      ' <section class="eb-side">' +
      '  <div class="eb-editing"></div>' +
      '  <div class="eb-gen">' +
      '   <div class="eb-gen-title">Generate an encounter</div>' +
      '   <div class="eb-gen-grid">' +
      '    <select class="eb-g-diff"><option>Easy</option><option selected>Medium</option><option>Hard</option><option>Deadly</option></select>' +
      '    <select class="eb-g-env"><option value="">Any environment</option></select>' +
      '    <select class="eb-g-fam"><option value="">Any family</option></select>' +
      '    <select class="eb-g-mix"><option value="balanced">Balanced mix</option><option value="melee">Mostly melee</option>' +
      '     <option value="ranged">Mostly ranged</option><option value="casters">With spellcasters</option></select>' +
      '   </div>' +
      '   <button class="eb-g-go md-button md-button--primary">Generate</button><span class="eb-g-note"></span>' +
      '  </div>' +
      '  <div class="eb-tray"></div>' +
      '  <div class="eb-diff"></div>' +
      '  <div class="eb-save">' +
      '   <input class="eb-name" placeholder="Encounter name">' +
      '   <input class="eb-loc" placeholder="Where it happens (optional)">' +
      '   <div class="eb-saverow"><input class="eb-id" placeholder="file-id"><button class="eb-savebtn md-button md-button--primary">Save</button>' +
      '    <button class="eb-runtray md-button" title="Roll initiative for these creatures and the party">Run</button>' +
      '    <button class="eb-clear md-button">Clear</button></div>' +
      '   <div class="eb-status"></div>' +
      '  </div>' +
      '  <div class="eb-sb"><p class="eb-hint">Click a creature\'s name to see its stat block here.</p></div>' +
      ' </section>' +
      '</div>' +
      '<div class="eb-cform"></div>' +
      '<div class="eb-initview"></div>';
    function $(sel) { return root.querySelector(sel); }

    CRS.forEach(function (cr) {
      $(".eb-crmin").appendChild(el('<option value="' + cr + '">' + cr + "</option>"));
      $(".eb-crmax").appendChild(el('<option value="' + cr + '">' + cr + "</option>"));
    });
    $(".eb-crmax").value = "30";
    types.forEach(function (t) { $(".eb-type").appendChild(el('<option value="' + esc(t) + '">' + esc(t) + "</option>")); });
    sizes.forEach(function (s) { $(".eb-size").appendChild(el('<option value="' + s + '">' + s + "</option>")); });
    Array.from(new Set([].concat.apply([], D.creatures.map(function (c) { return c.env || []; })))).sort()
      .forEach(function (e) { $(".eb-env").appendChild(el('<option value="' + esc(e) + '">' + esc(e) + "</option>")); });
    Array.from(new Set([].concat.apply([], D.creatures.map(function (c) { return c.env || []; })))).sort()
      .forEach(function (e) { $(".eb-g-env").appendChild(el('<option value="' + esc(e) + '">' + esc(e) + "</option>")); });
    function fillFamilies() {   // the generator's family list (again after a family is added in the builder)
      var keep = $(".eb-g-fam").value;
      $(".eb-g-fam").innerHTML = '<option value="">Any family</option>';
      (D.families || []).map(function (f) { return f.name; }).sort()
        .forEach(function (f) { $(".eb-g-fam").appendChild(el('<option value="' + esc(f) + '">' + esc(f) + "</option>")); });
      $(".eb-g-fam").value = keep;
    }
    fillFamilies();
    Array.from(new Set(D.creatures.map(function (c) { return c.source; })))
      .filter(function (s) { return s !== "campaign" && s !== "custom"; })
      .forEach(function (s) { $(".eb-source").appendChild(el('<option value="' + esc(s) + '">' + esc(sourceLabel(s)) + "</option>")); });

    // ------------------------------------------------------------ creature list
    function renderList() {
      var q = $(".eb-q").value.trim().toLowerCase();
      var lo = crValue($(".eb-crmin").value), hi = crValue($(".eb-crmax").value);
      var type = $(".eb-type").value, size = $(".eb-size").value, source = $(".eb-source").value;
      var env = $(".eb-env").value;
      var rows = D.creatures.filter(function (c) {
        var v = crValue(c.cr);
        return (!q || c.name.toLowerCase().indexOf(q) > -1) && v >= lo && v <= hi &&
          (!type || c.type === type) && (!size || c.size === size) && (!source || c.source === source) &&
          (!env || (c.env || []).indexOf(env) > -1);
      });
      $(".eb-count").textContent = rows.length + " of " + D.creatures.length + " creatures";
      $(".eb-rows").innerHTML = rows.slice(0, 300).map(function (c) {
        return '<div class="eb-row" data-id="' + esc(c.id) + '"' +
          ((c.env || []).length ? ' title="' + esc(c.env.join(", ")) + '"' : "") + ">" +
          '<button class="eb-add" title="Add to encounter">+</button>' +
          '<a class="eb-name-link">' + esc(c.name) + "</a>" +
          '<span class="eb-cr">' + esc(c.cr) + "</span>" +
          '<span class="eb-meta">' + esc(c.size || "—") + "</span>" +
          '<span class="eb-meta eb-type-col">' + esc(c.type || "—") + "</span>" +
          '<span><span class="eb-src eb-src-' + esc(c.source) + '">' + esc(sourceLabel(c.source)) + "</span>" +
          (c.source === "custom" ? '<button class="eb-cedit" data-cact="edit" data-cid="' + esc(c.id) + '" title="Edit this creature">✎</button>' : "") +
          "</span></div>";
      }).join("") + (rows.length > 300 ? '<p class="eb-hint">Showing the first 300 — narrow the search to see more.</p>' : "");
    }

    // ------------------------------------------------------------ tray + difficulty
    function renderTray() {
      var tray = $(".eb-tray");
      if (!state.tray.length) {
        tray.innerHTML = '<p class="eb-hint">Add creatures with the + buttons.</p>';
      } else {
        tray.innerHTML = state.tray.map(function (t) {
          var c = byId[t.id];
          return '<div class="eb-trow" data-id="' + esc(t.id) + '">' +
            '<button class="eb-minus">−</button><span class="eb-n">' + t.count + '</span><button class="eb-plus">+</button>' +
            '<a class="eb-name-link">' + esc(c.name) + "</a>" +
            '<span class="eb-cr">CR ' + esc(c.cr) + " · " + (c.xp * t.count).toLocaleString() + " XP</span>" +
            '<button class="eb-remove" title="Remove">×</button></div>';
        }).join("");
      }
      var d = difficulty();
      var cls = "eb-" + d.label.toLowerCase().replace("—", "none");
      $(".eb-diff").innerHTML =
        '<div class="eb-label ' + cls + '">' + d.label + "</div>" +
        "<div>" + d.count + " creatures · base " + d.base.toLocaleString() + " XP · ×" + d.mult +
        " → <b>" + d.adjusted.toLocaleString() + " adjusted XP</b></div>" +
        '<div class="eb-thresh">Easy ' + d.totals[0].toLocaleString() + " · Medium " + d.totals[1].toLocaleString() +
        " · Hard " + d.totals[2].toLocaleString() + " · Deadly " + d.totals[3].toLocaleString() + "</div>";
      persist();
    }

    function add(id) {
      var t = state.tray.filter(function (x) { return x.id === id; })[0];
      if (t) t.count += 1; else state.tray.push({ id: id, count: 1 });
      renderTray();
    }
    // ------------------------------------------------------------ families (data/families.yml), from the stat block panel
    // Which families a creature belongs to, and adding it to one (or a new one) - so creatures made
    // here can join the generator without editing families.yml by hand.
    function familiesHtml(id) {
      var mine = [];
      (D.families || []).forEach(function (f) {
        if (f.members.indexOf(id) > -1) mine.push([f.name, "members"]);
        if (f.leaders.indexOf(id) > -1) mine.push([f.name, "leaders"]);
      });
      return '<div class="eb-fams" data-cid="' + esc(id) + '"><span class="eb-fams-label">Families</span>' +
        (mine.length ? mine.map(function (m) {
          return '<span class="ei-chip">' + esc(m[0]) + (m[1] === "leaders" ? " · leader" : "") +
            '<button data-famact="remove" data-fam="' + esc(m[0]) + '" data-role="' + m[1] + '" title="Take it out of this family">×</button></span>';
        }).join("") : '<span class="eb-meta">None yet, so the generator won\'t use it.</span>') +
        '<select class="eb-famadd"><option value="">+ Add to a family…</option>' +
        (D.families || []).map(function (f) { return f.name; }).sort().map(function (n) {
          return '<option value="' + esc(n) + '">' + esc(n) + "</option>";
        }).join("") + '<option value="__new">New family…</option></select>' +
        '<select class="eb-famrole"><option value="members">as a member</option><option value="leaders">as a leader</option></select>' +
        '<span class="eb-fams-msg"></span></div>';
    }
    // families.yml names creatures by name; a name two creatures share is written as the id instead.
    function familyRef(id) {
      var name = byId[id].name;
      return D.creatures.filter(function (c) { return c.name.toLowerCase() === name.toLowerCase(); }).length > 1 ? id : name;
    }
    function familyChange(id, family, role, add, isNew) {
      var box = $(".eb-fams-msg");
      helperPost("/family", { family: family, creature: familyRef(id), role: role, action: add ? "add" : "remove", "new": isNew })
        .then(function (res) {
          if (res.status !== 200) { if (box) box.textContent = res.body.error || "Couldn't change it."; return; }
          var toIds = function (refs) {
            return refs.map(function (r) {
              if (byId[r]) return r;
              var c = D.creatures.filter(function (x) { return x.name.toLowerCase() === String(r).toLowerCase(); })[0];
              return c && c.id;
            }).filter(Boolean);
          };
          var f = (D.families || []).filter(function (x) { return x.name.toLowerCase() === res.body.family.toLowerCase(); })[0];
          if (!f) { f = { name: res.body.family, members: [], leaders: [], allies: [] }; D.families.push(f); }
          f.members = toIds(res.body.members); f.leaders = toIds(res.body.leaders);
          fillFamilies();
          showStatblock(id);
          var done = $(".eb-fams-msg");
          if (done) done.textContent = (add ? "Added to " : "Taken out of ") + res.body.family + ".";
        })
        .catch(function () { if (box) box.innerHTML = OFFLINE; });
    }

    function showStatblock(id) {
      // Custom creatures can be edited or deleted; SRD and campaign ones only copied.
      var actions = byId[id].source === "custom"
        ? '<button class="eb-act" data-cact="edit">Edit</button><button class="eb-act eb-danger" data-cact="delete">Delete</button>'
        : '<button class="eb-act" data-cact="copy">Copy to custom</button>';
      $(".eb-sb").innerHTML = '<div class="eb-sbbar" data-cid="' + esc(id) + '">' + actions + "</div>" + familiesHtml(id) + byId[id].sb;
      // Side-by-side: the stat block fills in below the tray, nothing moves.
      // Stacked (narrow screens): bring it into view, since it's far down the page.
      if (window.matchMedia("(max-width: 1100px)").matches) {
        $(".eb-sb").scrollIntoView({ block: "start", behavior: "smooth" });
      }
    }

    // ------------------------------------------------------------ generator
    // Builds encounters from data/families.yml the way a DM would: a leader with followers,
    // a pack, a boss with minions, or a mixed squad - sometimes with an allied family. It tries
    // many combinations, keeps those that land in the chosen difficulty band and match the
    // requested mix, and picks one of those at random.
    var famByName = {};
    (D.families || []).forEach(function (f) { famByName[f.name] = f; });

    function pick(list, weight) {
      if (!list.length) return null;
      var ws = list.map(function (x) { return Math.max(0.0001, weight ? weight(x) : 1); });
      var total = ws.reduce(function (a, b) { return a + b; }, 0), r = Math.random() * total;
      for (var i = 0; i < list.length; i++) { r -= ws[i]; if (r <= 0) return list[i]; }
      return list[list.length - 1];
    }
    function uniq(ids) {
      return Array.from(new Set(ids)).map(function (id) { return byId[id]; }).filter(function (c) { return c && c.xp > 0; });
    }
    function adjustedXp(counts) {
      var base = 0, n = 0;
      Object.keys(counts).forEach(function (id) { base += byId[id].xp * counts[id]; n += counts[id]; });
      return { adjusted: Math.floor(base * multiplier(n, state.size)), count: n };
    }
    function mixWeight(mix) {
      return function (c) {
        if (mix === "melee") return c.role === "melee" ? 3 : 0.5;
        if (mix === "ranged") return c.rc ? 3 : 0.4;
        if (mix === "casters") return c.role === "caster" ? 4 : 1;
        return 1;
      };
    }
    function mixOk(counts, mix, pool) {
      var bodies = [], n = 0;
      Object.keys(counts).forEach(function (id) { for (var i = 0; i < counts[id]; i++) bodies.push(byId[id]); });
      n = bodies.length;
      var melee = bodies.filter(function (c) { return c.role === "melee"; }).length;
      var shoot = bodies.filter(function (c) { return c.rc; }).length;
      var casters = bodies.filter(function (c) { return c.role === "caster"; }).length;
      if (mix === "melee") return melee / n >= 0.6;
      if (mix === "ranged") return shoot / n >= 0.5;
      if (mix === "casters") return casters >= 1;
      // Balanced: if the pool can do both, the encounter should too.
      var poolMelee = pool.some(function (c) { return c.role === "melee"; });
      var poolShoot = pool.some(function (c) { return c.rc; });
      return !(poolMelee && poolShoot) || (melee >= 1 && shoot >= 1) || n === 1;
    }

    var MAX_BODIES = 8;   // more than this is a slog to run, whatever the XP says

    // Environment: when one is chosen, only creatures that live there are used. Homebrew
    // creatures without environments only join when you pick their family yourself.
    function envOk(c, env, famPicked) {
      if (!env) return true;
      if (!(c.env || []).length) return famPicked;
      return c.env.indexOf(env) > -1;
    }

    function attempt(fams, lo, hi, mix, env, famPicked) {
      var fam = pick(fams);
      var ally = null;
      if (fam.allies.length && Math.random() < 0.35) ally = famByName[pick(fam.allies)] || null;
      var levelCap = state.level + 3;   // no single creature far above the party, except a boss
      var fits = function (c) { return c.xp <= hi && envOk(c, env, famPicked); };
      var members = uniq(fam.members).filter(fits);
      var leaders = uniq(fam.leaders).filter(fits);
      var allyPool = ally ? uniq(ally.members).filter(function (c) { return fits(c) && c.xp <= hi * 0.5; }) : [];
      var pool = members.concat(leaders).concat(allyPool);
      var counts = {}, template = pick(["leader", "pack", "boss", "squad"]);
      var w = mixWeight(mix);

      function add(c) { counts[c.id] = (counts[c.id] || 0) + 1; }
      function fill(types, maxCount) {
        types = types.filter(Boolean);
        for (var guard = 0; guard < 40; guard++) {
          var now = adjustedXp(counts);
          if (now.adjusted >= lo && Math.random() < 0.55) break;
          var fits = types.filter(function (c) {
            var trial = Object.assign({}, counts); trial[c.id] = (trial[c.id] || 0) + 1;
            var t = adjustedXp(trial);
            return t.adjusted <= hi && t.count <= maxCount;
          });
          if (!fits.length) break;
          // Favor cheaper creatures a little, so groups have bodies rather than one big hitter.
          add(pick(fits, function (c) { return w(c) / Math.pow(c.xp, 0.3); }));
        }
      }

      if (template === "leader") {
        var lead = pick(leaders.filter(function (c) { return c.xp <= hi * 0.6 && crValue(c.cr) <= levelCap; }), w);
        if (!lead) return null;
        add(lead);
        var followers = members.concat(allyPool).filter(function (c) { return c.id !== lead.id && c.xp <= lead.xp * 0.6; });
        fill([pick(followers, w), pick(followers, w)], MAX_BODIES);
      } else if (template === "boss") {
        var bosses = leaders.concat(members).filter(function (c) { return c.xp >= lo * 0.45 && c.xp <= hi * 0.85; });
        var boss = pick(bosses, w);
        if (!boss) return null;
        add(boss);
        var minions = members.concat(allyPool).filter(function (c) { return c.id !== boss.id && c.xp <= boss.xp * 0.25; });
        fill([pick(minions, w)], 5);
      } else if (template === "pack") {
        var packable = members.filter(function (c) { return crValue(c.cr) <= levelCap; });
        var first = pick(packable, w);
        if (!first) return null;
        var second = Math.random() < 0.5 ? pick(packable.filter(function (c) { return c.id !== first.id; }), w) : null;
        fill([first, second], MAX_BODIES);
      } else {
        var squadPool = members.concat(allyPool).filter(function (c) { return crValue(c.cr) <= levelCap; });
        var a = pick(squadPool, w);
        if (!a) return null;
        var others = squadPool.filter(function (c) { return c.id !== a.id; });
        var b = pick(others, function (c) { return w(c) * (c.role !== a.role || c.rc !== a.rc ? 3 : 1); });
        var c3 = Math.random() < 0.4 ? pick(others.filter(function (c) { return !b || c.id !== b.id; }), w) : null;
        fill([a, b, c3], MAX_BODIES);
      }

      var result = adjustedXp(counts);
      if (!result.count || result.adjusted < lo || result.adjusted > hi) return null;
      if (Object.keys(counts).length > 4 || !mixOk(counts, mix, pool)) return null;
      return { counts: counts, fam: fam, ally: ally && Object.keys(counts).some(function (id) {
        return ally.members.indexOf(id) > -1 && fam.members.indexOf(id) < 0 && fam.leaders.indexOf(id) < 0;
      }) ? ally : null, template: template, adjusted: result.adjusted };
    }

    var TEMPLATE_LABEL = { leader: "Leader and followers", pack: "Pack", boss: "Boss and minions", squad: "Mixed squad" };

    function generate() {
      var diffNames = ["Easy", "Medium", "Hard", "Deadly"];
      var di = diffNames.indexOf($(".eb-g-diff").value);
      var totals = (D.thresholds[String(state.level)] || [0, 0, 0, 0]).map(function (x) { return x * state.size; });
      var lo = totals[di], hi = di < 3 ? totals[di + 1] - 1 : Math.floor(totals[3] * 1.5);
      var env = $(".eb-g-env").value, famName = $(".eb-g-fam").value, mix = $(".eb-g-mix").value;

      if (!(D.families || []).length) {
        $(".eb-g-note").textContent = "The family table isn't loaded. If serve was running when the site's " +
          "hooks changed, close it and start it again.";
        return;
      }

      var fams = (D.families || []).filter(function (f) {
        if (famName) return f.name === famName;
        var cs = uniq(f.members.concat(f.leaders));
        if (env) {
          // The family has to belong there: at least half its tagged creatures live in it.
          var tagged = cs.filter(function (c) { return (c.env || []).length; });
          var here = tagged.filter(function (c) { return c.env.indexOf(env) > -1; });
          if (!tagged.length || here.length < Math.max(1, tagged.length / 2)) return false;
        }
        return cs.some(function (c) { return c.xp <= hi && envOk(c, env, false); });
      });
      if (!fams.length) {
        $(".eb-g-note").textContent = "No families fit those settings.";
        return;
      }
      var found = [];
      for (var i = 0; i < 600 && found.length < 25; i++) {
        var r = attempt(fams, lo, hi, mix, env, !!famName);
        if (r) found.push(r);
      }
      if (!found.length) {
        $(".eb-g-note").textContent = "Couldn't build a " + diffNames[di].toLowerCase() +
          " encounter with those settings - try another family, mix, or difficulty.";
        return;
      }
      var r = pick(found);
      state.tray = Object.keys(r.counts).map(function (id) { return { id: id, count: r.counts[id] }; })
        .sort(function (a, b) { return byId[b.id].xp - byId[a.id].xp; });
      state.name = r.fam.name + (r.ally ? " with " + r.ally.name : "") + (env ? " (" + env + ")" : "");
      state.location = env ? env : "";
      $(".eb-name").value = state.name;
      $(".eb-loc").value = state.location;
      delete $(".eb-id").dataset.edited;
      $(".eb-id").value = state.id = slug(state.name);
      $(".eb-status").innerHTML = "";
      $(".eb-g-note").textContent = TEMPLATE_LABEL[r.template] + " · " + r.fam.name +
        (r.ally ? " + " + r.ally.name : "") + ". Generate again for another.";
      renderTray();
    }

    // ------------------------------------------------------------ saving
    function encounterData() {
      // Difficulty follows the party set on this page, so new encounters don't pin a level.
      // (When editing one that does, the helper keeps its level.)
      return {
        id: $(".eb-id").value.trim() || slug($(".eb-name").value),
        name: $(".eb-name").value.trim(),
        location: $(".eb-loc").value.trim(),
        creatures: state.tray.map(function (t) { return { id: t.id, count: t.count }; })
      };
    }
    function asYaml(e) {
      var lines = ["id: " + e.id, "name: " + JSON.stringify(e.name)];
      if (e.location) lines.push("location: " + JSON.stringify(e.location));
      lines.push("creatures:");
      e.creatures.forEach(function (c) { lines.push("  - {id: " + c.id + ", count: " + c.count + "}"); });
      return lines.join("\n") + "\n";
    }
    function status(html, kind) { $(".eb-status").innerHTML = '<div class="eb-msg eb-' + (kind || "info") + '">' + html + "</div>"; }

    function save(overwrite) {
      var e = encounterData();
      if (state.editing && state.editing === e.id) overwrite = true;   // updating the one we opened
      if (!e.creatures.length) return status("Add some creatures first.", "warn");
      if (!e.name) return status("Give the encounter a name.", "warn");
      if (!/^[a-z0-9][a-z0-9-]*$/.test(e.id)) return status("The file id can only use lowercase letters, numbers, and dashes.", "warn");
      helperFetch(HELPER + "/encounter", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ encounter: e, overwrite: !!overwrite })
      }).then(function (r) { return r.json().then(function (j) { return { status: r.status, body: j }; }); })
        .then(function (res) {
          if (res.status === 200) {
            var list = D.encounters, entry = list.filter(function (x) { return x.id === e.id; })[0];
            if (entry) { entry.name = e.name; entry.location = e.location; entry.creatures = e.creatures; }
            else list.push({ id: e.id, name: e.name, location: e.location, creatures: e.creatures,
                             archived: false, page: "", used_on: [] });
            var verb = res.body.updated ? "Updated" : "Saved";
            clearBuilder();
            flash(verb + " \u201c" + esc(e.name) + "\u201d.", "ok");
            setView(entry && entry.archived ? "archive" : "active");
          } else if (res.status === 409) {
            status(esc(res.body.error) + ' <button class="eb-overwrite md-button">Replace it</button>', "warn");
          } else {
            status(esc(res.body.error || "Couldn't save."), "warn");
          }
        })
        .catch(function () {
          status(OFFLINE + " To keep it, copy this into a new file named <code>data/encounters/" + esc(e.id) + ".yml</code>:" +
                 '<textarea class="eb-yaml" readonly rows="8">' + esc(asYaml(e)) + "</textarea>", "warn");
        });
    }

    // ------------------------------------------------------------ encounter lists (Active / Archive)
    function flash(html, kind) {
      state.flash = html ? { html: html, kind: kind || "info" } : null;
      persist();
      $(".eb-flash").innerHTML = html ? '<div class="eb-msg eb-' + (kind || "info") + '">' + html + "</div>" : "";
    }

    function encDifficulty(enc) {
      var level = enc.party_level || state.level, size = enc.party_size || state.size;
      var base = 0, n = 0;
      enc.creatures.forEach(function (c) { if (byId[c.id]) { base += byId[c.id].xp * c.count; n += c.count; } });
      var adjusted = Math.floor(base * multiplier(n, size));
      var totals = (D.thresholds[String(level)] || [0, 0, 0, 0]).map(function (x) { return x * size; });
      var label = n ? "Trivial" : "—";
      ["Easy", "Medium", "Hard", "Deadly"].forEach(function (name, i) { if (n && adjusted >= totals[i]) label = name; });
      return { label: label, adjusted: adjusted, pinned: !!enc.party_level, level: level };
    }

    function creatureSummary(enc) {
      return enc.creatures.map(function (c) {
        var name = byId[c.id] ? byId[c.id].name : c.id + " (?)";
        return (c.count > 1 ? c.count + "× " : "") + name;
      }).join(", ");
    }

    function renderEncList() {
      var archived = state.view === "archive";
      var q = ($(".eb-lq").value || "").trim().toLowerCase();
      var rows = (D.encounters || []).filter(function (e) {
        return !!e.archived === archived &&
          (!q || (e.name + " " + (e.location || "") + " " + creatureSummary(e)).toLowerCase().indexOf(q) > -1);
      });
      $(".eb-new").style.display = archived ? "none" : "";
      if (!rows.length) {
        $(".eb-enclist").innerHTML = '<p class="eb-hint">' + (q ? "No encounters match." : archived ?
          "Nothing archived yet. Archive encounters from the Active list once you're done with them." :
          "No active encounters. Build one, or generate one, in the Builder.") + "</p>";
        return;
      }
      $(".eb-enclist").innerHTML =
        '<div class="eb-erow eb-head"><span>Encounter</span><span>Where</span><span>Creatures</span><span>Difficulty</span><span></span></div>' +
        rows.map(function (e) {
          var d = encDifficulty(e);
          var name = e.page ? '<a href="' + esc(e.page) + '">' + esc(e.name) + "</a>" : esc(e.name);
          var actions = '<button class="eb-act eb-run" data-act="run" title="Roll initiative for this encounter">Run</button>' + (archived
            ? '<button class="eb-act" data-act="restore">Restore</button><button class="eb-act" data-act="duplicate">Duplicate</button>' +
              '<button class="eb-act eb-danger" data-act="delete">Delete</button>'
            : '<button class="eb-act" data-act="edit">Edit</button><button class="eb-act" data-act="duplicate">Duplicate</button>' +
              '<button class="eb-act" data-act="archive">Archive</button>');
          return '<div class="eb-erow" data-enc="' + esc(e.id) + '">' +
            '<span class="eb-ename">' + name + "</span>" +
            '<span class="eb-meta">' + esc(e.location || "—") + "</span>" +
            '<span class="eb-meta eb-ecreatures" title="' + esc(creatureSummary(e)) + '">' + esc(creatureSummary(e)) + "</span>" +
            '<span><b class="eb-' + d.label.toLowerCase().replace("—", "none") + '">' + d.label + "</b> " +
            '<span class="eb-meta">' + d.adjusted.toLocaleString() + " XP" + (d.pinned ? " · level " + d.level : "") + "</span></span>" +
            '<span class="eb-actions">' + actions + "</span></div>";
        }).join("");
    }

    function setView(view) {
      state.view = view;
      persist();
      if (view === "initiative" && !state.combat) view = state.view = "active";
      root.querySelectorAll(".eb-vbtn").forEach(function (b) { b.classList.toggle("eb-on", b.getAttribute("data-view") === view); });
      // The Initiative tab opens once an encounter is being run.
      var ib = $('.eb-vbtn[data-view="initiative"]');
      ib.disabled = !state.combat;
      ib.title = state.combat ? "" : "Run an encounter (Active, Archive, or the Builder) to use the tracker";
      $(".eb-initview").style.display = view === "initiative" ? "" : "none";
      if (view === "initiative") renderInit();
      $(".eb-listview").style.display = view === "builder" || view === "initiative" ? "none" : "";
      // In the Builder, the New creature form (while open) takes the place of the search and tray.
      $(".eb-cols").style.display = view === "builder" && !state.cdraft ? "" : "none";
      $(".eb-cform").style.display = view === "builder" && state.cdraft ? "" : "none";
      if (view === "active" || view === "archive") renderEncList();
      renderEditing();
    }

    function renderEditing() {
      var e = state.editing && (D.encounters || []).filter(function (x) { return x.id === state.editing; })[0];
      $(".eb-editing").innerHTML = e ? '<div class="eb-msg eb-info">Editing <b>' + esc(e.name) +
        "</b> - Save updates it. <a class=\"eb-stop\">Start a new encounter instead</a></div>" : "";
    }

    function clearBuilder() {
      state.tray = []; state.name = state.location = state.id = ""; state.editing = null;
      $(".eb-name").value = $(".eb-loc").value = $(".eb-id").value = "";
      delete $(".eb-id").dataset.edited;
      $(".eb-status").innerHTML = "";
      $(".eb-g-note").textContent = "";
      renderTray();
      renderEditing();
    }

    function loadInto(e, asCopy) {
      state.tray = e.creatures.filter(function (c) { return byId[c.id]; })
        .map(function (c) { return { id: c.id, count: c.count }; });
      state.name = asCopy ? e.name + " (copy)" : e.name;
      state.location = e.location || "";
      state.id = asCopy ? slug(state.name) : e.id;
      state.editing = asCopy ? null : e.id;
      $(".eb-name").value = state.name;
      $(".eb-loc").value = state.location;
      $(".eb-id").value = state.id;
      if (asCopy) delete $(".eb-id").dataset.edited; else $(".eb-id").dataset.edited = "1";
      $(".eb-status").innerHTML = "";
      renderTray();
      flash("");
      setView("builder");
      draftNotice();
    }
    function draftNotice() {
      if (state.cdraft) flash("You're partway through a creature - the encounter shows once you save or cancel it.", "info");
    }

    function helperPost(path, body) {
      return helperFetch(HELPER + path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) })
        .then(function (r) { return r.json().then(function (j) { return { status: r.status, body: j }; }); });
    }
    var OFFLINE = ONLINE
      ? "This is the online copy, which can't save. Make changes on the site at home (<code>serve</code>), then run <code>publish</code>."
      : "The save helper isn't running (it starts with <code>serve</code>).";

    function setArchived(e, archived) {
      helperPost("/encounter/archive", { id: e.id, archived: archived }).then(function (res) {
        if (res.status !== 200) return flash(esc(res.body.error || "Couldn't update it."), "warn");
        e.archived = archived;
        flash((archived ? "Archived" : "Restored") + " \u201c" + esc(e.name) + "\u201d.", "ok");
        renderEncList();
      }).catch(function () { flash(OFFLINE, "warn"); });
    }

    function deleteEnc(e) {
      if (!window.confirm("Delete \u201c" + e.name + "\u201d? The file is moved to sources/backups/encounters, not erased.")) return;
      helperPost("/encounter/delete", { id: e.id }).then(function (res) {
        if (res.status !== 200) return flash(esc(res.body.error || "Couldn't delete it."), "warn");
        D.encounters = D.encounters.filter(function (x) { return x.id !== e.id; });
        flash("Deleted \u201c" + esc(e.name) + "\u201d. A copy is in <code>" + esc(res.body.backup) + "</code>.", "ok");
        renderEncList();
      }).catch(function () { flash(OFFLINE, "warn"); });
    }

    // ------------------------------------------------------------ initiative tracker
    // Run an encounter (its Run button, the builder's Run, or ?run=<id> from a story page) and the
    // Initiative tab lists the party and every creature. Creatures roll d20 + their initiative bonus
    // (one roll per creature type, or each on its own); the players' rolls are typed in. The combat
    // is kept with the rest of the builder's state, so a reload mid-fight picks up where it was.
    function d20() { return Math.floor(Math.random() * 20) + 1; }
    function num(v) { var n = parseInt(v, 10); return isNaN(n) ? null : n; }

    function rollFoes(combat) {
      var byType = {};
      combat.list.forEach(function (x) {
        if (x.kind !== "foe") return;
        var die = state.initGroup && byType[x.cid] ? byType[x.cid] : d20();
        byType[x.cid] = die;
        x.die = die;
        x.init = die + x.bonus;
      });
    }

    // ------------------------------------------------------------ turn log
    // What happens in a fight - turns, damage, conditions - for the session write-up. While the
    // recorder is running (it says so every second on a BroadcastChannel), each entry gets the
    // recording's own clock - the time the transcript shows - and is saved next to the recording as
    // "<recording>.turns.txt"; tools/transcribe.py weaves those lines into the transcript.
    var recNow = null;
    if (window.BroadcastChannel) {
      new BroadcastChannel(CAMPAIGN + "-recorder").addEventListener("message", function (ev) {
        if (ev.data && ev.data.state) recNow = Object.assign({ at: Date.now() }, ev.data);
      });
    }
    function recClock() {
      if (!recNow || !recNow.file || Date.now() - recNow.at > 5000 ||
          ["recording", "paused", "failing"].indexOf(recNow.state) < 0) return null;
      var s = Math.floor((recNow.elapsed + (recNow.state === "paused" ? 0 : Date.now() - recNow.at)) / 1000);
      return [Math.floor(s / 3600), Math.floor(s % 3600 / 60), s % 60].map(function (n) { return n < 10 ? "0" + n : n; }).join(":");
    }
    function logEvent(text) {
      var c = state.combat;
      if (!c) return;
      var rec = recClock();
      (c.log = c.log || []).push({ time: new Date().toTimeString().slice(0, 8), rec: rec, text: text });
      if (rec) helperPost("/turnlog", { file: recNow.file, rec: rec, text: text }).catch(function () {});
    }

    var CONDITIONS = ["Blinded", "Charmed", "Deafened", "Frightened", "Grappled", "Incapacitated", "Invisible", "Paralyzed",
                      "Petrified", "Poisoned", "Prone", "Restrained", "Stunned", "Unconscious", "Exhaustion"];

    function runEncounter(name, creatures, encId) {
      if (state.combat && state.combat.started &&
          !window.confirm("End the fight in progress (" + state.combat.name + ") and start " + name + "?")) return;
      var list = [], n = 0;
      // Players start from their card (data/party.yml): AC, HP, and the initiative bonus for ties.
      (D.party.members || []).forEach(function (p, pi) {
        list.push({ k: "p" + (n++), kind: "pc", pi: pi, name: p.character, sub: p.player, init: null, bonus: p.init || 0,
                    ac: p.ac == null ? "" : String(p.ac), hp: num(p.hp), max: num(p.hp), cond: "" });
      });
      creatures.forEach(function (c) {
        var m = byId[c.id];
        if (!m) return;
        for (var i = 1; i <= c.count; i++) {
          list.push({ k: "f" + (n++), kind: "foe", cid: m.id, name: m.name + (c.count > 1 ? " " + i : ""),
                      bonus: m.init || 0, ac: m.ac == null ? "" : String(m.ac),
                      hp: num(m.hp), max: num(m.hp), cond: "" });
        }
      });
      state.combat = { name: name, encId: encId || "", list: list, round: 1, cur: null, started: false, shown: null };
      rollFoes(state.combat);
      flash("");
      setView("initiative");
    }

    function order() {
      return state.combat.list.slice().sort(function (a, b) {
        var ai = a.init == null ? -99 : a.init, bi = b.init == null ? -99 : b.init;
        return bi - ai || b.bonus - a.bonus || (a.kind === "pc" ? -1 : 0) - (b.kind === "pc" ? -1 : 0) ||
          (a.name < b.name ? -1 : 1);
      });
    }
    function isOut(x) { return x.kind !== "pc" && x.hp != null && x.hp <= 0; }
    function find(k) { return state.combat.list.filter(function (x) { return x.k === k; })[0]; }

    // Whose turn it is. Until someone moves it, that's the top of the order (so it follows
    // the players' rolls as they're typed in).
    function current() {
      var c = state.combat, x = c.cur && find(c.cur);
      if (x && !isOut(x)) return x;
      return order().filter(function (y) { return !isOut(y); })[0] || null;
    }

    // dir 0 = Start combat (the turn stays at the top); 1 / -1 = next / back (buttons or arrow keys).
    function step(dir) {
      var c = state.combat, list = order().filter(function (x) { return !isOut(x); });
      if (!list.length) return;
      var was = c.started && c.cur;
      if (!c.started) {
        c.started = true; c.round = 1; c.cur = list[0].k;
        logEvent("Combat started: " + c.name);
      }
      if (dir) {
        var i = list.map(function (x) { return x.k; }).indexOf(c.cur);
        if (i < 0) i = 0;   // the current one just went down: carry on from the top of who's left
        var j = i + dir;
        if (j >= list.length) { j = 0; c.round += 1; }
        if (j < 0) { if (c.round > 1) { j = list.length - 1; c.round -= 1; } else j = 0; }
        c.cur = list[j].k;
      }
      c.alert = "";
      var now = find(c.cur);
      if (now && c.cur !== was) {
        logEvent("Round " + c.round + " · " + now.name + "'s turn" + (dir < 0 ? " (back)" : ""));
        // Condition countdowns tick at the start of the creature's own turn (going back doesn't undo them).
        if (dir > 0) {
          (now.conds || []).forEach(function (cd) {
            if (cd.r != null) cd.r -= 1;
            if (cd.r === 0) logEvent(cd.n + " ends on " + now.name);
          });
          now.conds = (now.conds || []).filter(function (cd) { return cd.r == null || cd.r > 0; });
        }
      }
      if (now && (now.kind === "foe" || now.kind === "pc")) c.shown = cardKey(now);
      renderInit();
      var row = $(".ei-cur");
      if (row) row.scrollIntoView({ block: "nearest" });
    }

    // The side panel shows a creature's stat block ("<creature id>") or a player's card ("pc:<n>").
    function cardKey(x) { return x.kind === "pc" ? "pc:" + x.pi : x.cid; }
    function cardHtml(key) {
      if (!key) return "";
      if (String(key).indexOf("pc:") === 0) {
        var p = (D.party.members || [])[+key.slice(3)];
        return p && p.sb || "";
      }
      return byId[key] ? byId[key].sb : "";
    }

    function renderInit() {
      var c = state.combat, box = $(".eb-initview");
      if (!c) { box.innerHTML = ""; return; }
      var missing = c.list.filter(function (x) { return x.kind === "pc" && x.init == null; }).length;
      var now = current();
      box.innerHTML =
        '<div class="ei-bar">' +
        ' <div class="ei-title"><span class="ei-name">' + esc(c.name) + "</span>" +
        (c.started ? ' <span class="ei-round">Round ' + c.round + "</span>" : "") +
        (now ? ' <span class="ei-now">' + (c.started ? esc(now.name) + "'s turn" : "Up first: " + esc(now.name)) + "</span>" : "") + "</div>" +
        ' <div class="ei-btns">' +
        (c.started ? '<button class="eb-act" data-ia="prev" title="Back one turn (↑ or ←)">◀ Back</button>' +
                     '<button class="ei-next md-button md-button--primary" data-ia="next" title="Next turn (↓ or →)">Next turn ▶</button>'
                   : '<button class="ei-next md-button md-button--primary" data-ia="start">Start combat</button>') +
        '  <button class="eb-act" data-ia="reroll" title="Roll the creatures\' initiative again">Reroll creatures</button>' +
        '  <label class="ei-group"><input type="checkbox" data-ia="group"' + (state.initGroup ? " checked" : "") + "> One roll per creature type</label>" +
        (ONLINE ? "" : '  <label class="ei-share" title="Show the order, turn, and conditions on the players\' site (Initiative page) as you go. HP, AC, and notes stay here."><input type="checkbox" data-ia="share"' +
          (state.share ? " checked" : "") + '> Share with players</label> <span class="ei-share-status"></span>') +
        (state.share && !ONLINE ? '  <button class="eb-act ei-victory" data-ia="victory" title="End the fight with a victory fanfare on the players\' phones">🏆 Victory</button>' : "") +
        '  <button class="eb-act eb-danger" data-ia="end">End combat</button>' +
        " </div></div>" +
        (!(D.party.members || []).length ? '<div class="eb-msg eb-warn">The party list isn\'t loaded, so the players aren\'t here. ' +
          "If <code>serve</code> was running when the site's hooks changed, close it and start it again, then Run the encounter again " +
          "(or add the players with the Add row below).</div>" : "") +
        (c.alert ? '<div class="eb-msg eb-warn ei-alert">' + esc(c.alert) + ' <a data-ia="unalert" title="Dismiss">×</a></div>' : "") +
        (missing && !c.started ? '<div class="eb-msg eb-info">Type in the players\' initiative rolls (' + missing + " to go), then Start combat. " +
          "Creatures are already rolled — click a number to change it.</div>" : "") +
        '<div class="ei-cols"><div class="ei-table">' +
        '<div class="ei-row ei-head"><span></span><span>Init</span><span>Name</span><span>AC</span><span>HP</span><span>Damage / heal</span><span>Conditions &amp; notes</span><span></span></div>' +
        order().map(function (x) {
          var isCur = now && x.k === now.k;
          var cls = "ei-row ei-" + x.kind + (isCur ? " ei-cur" : "") + (isOut(x) ? " ei-out" : "") + (x.hide ? " ei-hidden" : "");
          var hpLow = x.max && x.hp != null && x.hp > 0 && x.hp <= x.max / 2;
          return '<div class="' + cls + '" data-k="' + x.k + '">' +
            '<span class="ei-mark">' + (isCur ? "▶" : "") + "</span>" +
            '<span><input class="ei-init" type="number" data-f="init" value="' + (x.init == null ? "" : x.init) + '"' +
              (x.kind === "foe" ? ' title="d20 (' + x.die + ") " + signedPlain(x.bonus) + '"' : ' placeholder="roll"') + "></span>" +
            '<span class="ei-who">' + (cardHtml(cardKey(x))
              ? '<a class="ei-show" data-ia="show">' + esc(x.name) + "</a>" : "<b>" + esc(x.name) + "</b>") +
              '<span class="ei-sub">' + esc(x.kind === "pc" ? x.sub || "" : x.kind === "foe" ? "init " + signedPlain(x.bonus) : "") + "</span>" +
              (state.share ? '<button class="ei-hide" data-ia="hide" title="' + (x.hide ? "Hidden from the players\' tracker - click to show" : "Hide from the players\' tracker (an ambusher, someone invisible)") + '">' +
                (x.hide ? "hidden from players" : "hide") + "</button>" : "") + "</span>" +
            '<span><input class="ei-ac" data-f="ac" value="' + esc(x.ac) + '"></span>' +
            '<span class="ei-hpcell' + (hpLow ? " ei-bloodied" : "") + '"><input class="ei-hp" type="number" data-f="hp" value="' + (x.hp == null ? "" : x.hp) + '">' +
              '<span class="ei-max">/ <input class="ei-maxin" type="number" data-f="max" value="' + (x.max == null ? "" : x.max) + '"></span></span>' +
            '<span><input class="ei-dmg" data-f="dmg" placeholder="7 or +7" title="Type damage and press Enter; +7 heals"></span>' +
            '<span class="ei-condcell">' +
              (x.conc ? '<span class="ei-chip ei-conc" title="Concentrating - damage calls for a Con save">◆ Conc.<button data-ia="unconc" title="Concentration ends">×</button></span>' : "") +
              (x.conds || []).map(function (cd, ci) {
                return '<span class="ei-chip" title="' + (cd.r != null ? cd.r + " more round" + (cd.r === 1 ? "" : "s") + " (counts down at the start of its turn)" : "Until removed") + '">' +
                  esc(cd.n) + (cd.r != null ? "<i>" + cd.r + "</i>" : "") + '<button data-ia="uncond" data-ci="' + ci + '" title="Remove">×</button></span>';
              }).join("") +
              '<select class="ei-addcond" data-f="addcond" title="Add a condition, or concentration"><option value="">+</option>' +
              CONDITIONS.map(function (n) { return '<option value="' + n + '">' + n + "</option>"; }).join("") +
              '<option value="__conc">Concentrating</option></select>' +
              '<input class="ei-cond" data-f="cond" value="' + esc(x.cond) + '" placeholder="notes"></span>' +
            '<span><button data-ia="remove" title="Remove from the fight">×</button></span></div>';
        }).join("") +
        '<div class="ei-add"><input class="ei-a-name" placeholder="Add someone: name"><input class="ei-a-init" type="number" placeholder="init">' +
        '<input class="ei-a-ac" placeholder="AC"><input class="ei-a-hp" type="number" placeholder="HP"><button class="eb-act" data-ia="add">Add</button></div>' +
        '<p class="eb-hint">↓ or → moves to the next turn, ↑ or ← back one (press Enter or Esc to leave a box first). ' +
        "Creatures at 0 HP are skipped. Half HP or less shows as bloodied. Next turn wraps into a new round. " +
        "A condition's rounds count down at the start of that creature's turn. While a session recording runs, turns, damage, " +
        "and conditions are logged next to it for the write-up.</p>" +
        '</div><div class="ei-sb">' + (cardHtml(c.shown)
          || '<p class="eb-hint">Click a name for its stat block or character card. On each turn it opens here by itself.</p>') + "</div></div>";
      persist();
      shareStatus();
      share();
    }
    function signedPlain(n) { return n >= 0 ? "+" + n : String(n); }

    // ------------------------------------------------------------ Share with players
    // With "Share with players" ticked, every change goes (through the save helper and its service
    // token) to the players' live tracker on their site: names, initiative, whose turn, the round, and
    // conditions - never HP, AC, notes, or anyone hidden with the row's "hide" link. Until Start combat,
    // only the party shows, so the players don't see who they're up against before the fight begins.
    var shareTimer = null, shareLast = null, shareVictory = false;
    function shareView() {
      var c = state.combat;
      if (!c) return shareVictory ? { active: false, victory: true } : { active: false };
      var now = current();
      return { active: true, started: !!c.started, round: c.round,
        list: order().filter(function (x) { return !x.hide && (c.started || x.kind === "pc"); }).map(function (x) {
          return { name: x.name, init: x.init, pc: x.kind === "pc", cur: !!(c.started && now && x.k === now.k),
                   out: isOut(x), conc: !!x.conc, conds: (x.conds || []).map(function (cd) { return { n: cd.n, r: cd.r }; }) };
        }) };
    }
    function share(force) {
      if (ONLINE || (!state.share && !force)) return;
      clearTimeout(shareTimer);
      shareTimer = setTimeout(function () {
        var view = state.share ? shareView() : { active: false };
        shareVictory = false;
        helperPost("/tracker/share", { view: view }).then(function (res) {
          shareLast = res.body.token === false ? { ok: false, error: "tools\\tracker-token.txt is missing." } : res.body.last;
          shareStatus();
          // That reply describes the send before this one; ask again shortly for this one's result.
          setTimeout(function () {
            helperFetch(HELPER + "/tracker/share").then(function (r) { return r.json(); })
              .then(function (j) { if (j.last && j.last.ok !== null) { shareLast = j.last; shareStatus(); } }).catch(function () {});
          }, 1500);
        }).catch(function () { shareLast = { ok: false, error: "The save helper isn't running (it starts with serve)." }; shareStatus(); });
      }, 200);
    }
    function shareStatus() {
      var el = $(".ei-share-status");
      if (!el) return;
      if (!state.share) { el.className = "ei-share-status"; el.textContent = ""; return; }
      if (!shareLast || shareLast.ok === null) { el.className = "ei-share-status"; el.textContent = "sending…"; return; }
      el.className = "ei-share-status " + (shareLast.ok ? "ei-share-ok" : "ei-share-bad");
      el.textContent = shareLast.ok
        ? "● Live" + (shareLast.watching != null ? " · " + shareLast.watching + " watching" : "")
        : "⚠ " + shareLast.error;
    }

    $(".eb-initview").addEventListener("click", function (ev) {
      var t = ev.target, c = state.combat, act = t.getAttribute("data-ia");
      if (!c || !act || act === "group" || act === "share") return;
      var row = t.closest("[data-k]"), x = row && find(row.getAttribute("data-k"));
      if (act === "start") return step(0);
      if (act === "next") return step(1);
      if (act === "prev") return step(-1);
      if (act === "reroll") { rollFoes(c); return renderInit(); }
      if (act === "show") { c.shown = cardKey(x); return renderInit(); }
      if (act === "unalert") { c.alert = ""; return renderInit(); }
      if (act === "uncond") {
        var gone = x.conds.splice(+t.getAttribute("data-ci"), 1)[0];
        if (gone) logEvent(gone.n + " removed from " + x.name);
        return renderInit();
      }
      if (act === "unconc") { x.conc = false; logEvent(x.name + " stops concentrating"); return renderInit(); }
      if (act === "hide") { x.hide = !x.hide; return renderInit(); }
      if (act === "remove") {
        if (c.cur === x.k) step(1);
        c.list = c.list.filter(function (y) { return y !== x; });
        logEvent(x.name + " leaves the fight");
        return renderInit();
      }
      if (act === "add") {
        var name = $(".ei-a-name").value.trim();
        if (!name) return $(".ei-a-name").focus();
        c.list.push({ k: "x" + Date.now(), kind: "other", name: name, init: num($(".ei-a-init").value), bonus: 0,
                      ac: $(".ei-a-ac").value.trim(), hp: num($(".ei-a-hp").value), max: num($(".ei-a-hp").value), cond: "" });
        logEvent(name + " joins the fight");
        return renderInit();
      }
      if (act === "victory") {
        if (!window.confirm("Victory! End this combat and play the fanfare on the players' tracker?")) return;
        logEvent("Victory! Combat ended after " + c.round + " round" + (c.round === 1 ? "" : "s"));
        state.combat = null;
        shareVictory = true;
        share();
        return setView(state.editing ? "builder" : "active");
      }
      if (act === "end") {
        if (!window.confirm("End this combat? The tracker is cleared.")) return;
        if (c.started) logEvent("Combat ended after " + c.round + " round" + (c.round === 1 ? "" : "s"));
        state.combat = null;
        share();   // the players' tracker goes back to "No fight right now"
        return setView(state.editing ? "builder" : "active");
      }
    });
    $(".eb-initview").addEventListener("change", function (ev) {
      var t = ev.target, c = state.combat;
      if (!c) return;
      if (t.getAttribute("data-ia") === "group") { state.initGroup = t.checked; rollFoes(c); return renderInit(); }
      if (t.getAttribute("data-ia") === "share") {
        state.share = t.checked;
        shareLast = null;
        if (!state.share) share(true);   // clears the players' tracker
        return renderInit();
      }
      var row = t.closest("[data-k]"), f = t.getAttribute("data-f");
      if (!row || !f || f === "dmg") return;
      var x = find(row.getAttribute("data-k"));
      if (f === "addcond") {
        var what = t.value;
        t.value = "";
        if (!what) return;
        if (what === "__conc") {
          x.conc = true;
          logEvent(x.name + " is concentrating");
          return renderInit();
        }
        var rounds = window.prompt(what + " on " + x.name + " - for how many rounds? (Leave blank for until it's removed.)", "");
        if (rounds === null) return;   // cancelled
        var r = num(rounds);
        x.conds = (x.conds || []).filter(function (cd) { return cd.n !== what; });   // re-adding replaces the old one
        x.conds.push({ n: what, r: r && r > 0 ? r : null });
        logEvent(x.name + " is " + what.toLowerCase() + (r && r > 0 ? " (" + r + " round" + (r === 1 ? "" : "s") + ")" : ""));
        return renderInit();
      }
      if (f === "init") { x.init = num(t.value); if (x.kind === "foe" && x.init != null) x.die = x.init - x.bonus; return renderInit(); }
      if (f === "hp" || f === "max") { x[f] = num(t.value); return renderInit(); }
      x[f] = t.value; persist();   // AC, conditions: no redraw, so typing isn't interrupted
    });
    // Arrow keys move the turn - except while typing in a box, where they belong to the box.
    document.addEventListener("keydown", function (ev) {
      if (state.view !== "initiative" || !state.combat || ev.altKey || ev.ctrlKey || ev.metaKey) return;
      var dir = { ArrowDown: 1, ArrowRight: 1, ArrowUp: -1, ArrowLeft: -1 }[ev.key];
      var tag = (ev.target.tagName || "").toLowerCase();
      if (!dir || tag === "textarea" || tag === "select" || ev.target.isContentEditable ||
          (tag === "input" && ev.target.type !== "checkbox")) return;
      if (document.querySelector(".md-search__input:focus")) return;
      ev.preventDefault();
      step(dir);
    });
    $(".eb-initview").addEventListener("keydown", function (ev) {
      var t = ev.target;
      if (ev.key === "Escape" && t.tagName === "INPUT") return t.blur();
      if (ev.key !== "Enter") return;
      if (t.classList.contains("ei-a-name") || t.classList.contains("ei-a-init") || t.classList.contains("ei-a-hp") || t.classList.contains("ei-a-ac"))
        return $('[data-ia="add"]').click();
      if (t.getAttribute("data-f") !== "dmg") return t.blur();
      var x = find(t.closest("[data-k]").getAttribute("data-k")), v = t.value.trim(), amount = Math.abs(num(v) || 0);
      if (!amount) return;
      var heal = v.charAt(0) === "+";
      var before = x.hp;
      var hp = (x.hp == null ? (x.max || 0) : x.hp) + (heal ? amount : -amount);
      x.hp = Math.max(0, x.max != null ? Math.min(hp, x.max) : hp);
      var tally = " (" + x.hp + (x.max != null ? "/" + x.max : "") + ")";
      logEvent(x.name + (heal ? " heals " + amount : " takes " + amount + " damage") + tally);
      if (!heal && x.hp === 0 && before !== 0) {
        logEvent(x.kind === "pc" ? x.name + " drops to 0 HP" : x.name + " is down");
        if (x.conc) { x.conc = false; logEvent(x.name + "'s concentration ends"); }
      } else if (!heal && x.conc) {
        // 5e: a concentrating creature that takes damage makes a Con save, DC 10 or half the damage.
        var dc = Math.max(10, Math.floor(amount / 2));
        state.combat.alert = x.name + " is concentrating - Constitution save, DC " + dc + ". (× if it's kept; the ◆ chip's × if it's lost.)";
        logEvent(x.name + " makes a concentration check (DC " + dc + ")");
      }
      var k = x.k;
      renderInit();
      var again = $('.ei-row[data-k="' + k + '"] .ei-dmg');   // ready for the next hit on the same row
      if (again) again.focus();
    });

    // ------------------------------------------------------------ custom creatures
    // The New creature form saves to data/monsters/custom.yml through the save helper. The draft is
    // kept with the rest of the builder's state, so a live reload mid-edit doesn't lose it. The preview
    // is built the same way hooks/campaign.py builds stat blocks (render_statblock).
    var CR_XP = { "0": 10, "1/8": 25, "1/4": 50, "1/2": 100, "1": 200, "2": 450, "3": 700, "4": 1100, "5": 1800,
      "6": 2300, "7": 2900, "8": 3900, "9": 5000, "10": 5900, "11": 7200, "12": 8400, "13": 10000, "14": 11500,
      "15": 13000, "16": 15000, "17": 18000, "18": 20000, "19": 22000, "20": 25000, "21": 33000, "22": 41000,
      "23": 50000, "24": 62000, "25": 75000, "26": 90000, "27": 105000, "28": 120000, "29": 135000, "30": 155000 };
    var ABIL = ["str", "dex", "con", "int", "wis", "cha"];
    var CTYPES = ["aberration", "beast", "celestial", "construct", "dragon", "elemental", "fey", "fiend", "giant",
                  "humanoid", "monstrosity", "ooze", "plant", "undead"];
    var ENVS = Array.from(new Set(["Arctic", "Coastal", "Desert", "Forest", "Grassland", "Hill", "Mountain", "Swamp",
      "Underdark", "Underwater", "Urban"].concat([].concat.apply([], D.creatures.map(function (c) { return c.env || []; }))))).sort();
    var DETAILS = [["saves", "Saving throws", "Con +7, Wis +5"], ["skills", "Skills", "Deception +6, Stealth +4"],
      ["vulnerabilities", "Damage vulnerabilities", "fire"], ["resistances", "Damage resistances", "cold"],
      ["immunities", "Damage immunities", "poison"], ["condition_immunities", "Condition immunities", "charmed, poisoned"],
      ["senses", "Senses", "darkvision 60 ft., passive Perception 12"], ["languages", "Languages", "Common, Sylvan"]];
    var LISTS = [["traits", "Traits", "trait"], ["actions", "Actions", "action"], ["bonus_actions", "Bonus Actions", "bonus action"],
      ["reactions", "Reactions", "reaction"], ["legendary_actions", "Legendary Actions", "legendary action"]];
    var FIELDS = ["id", "name", "group", "type", "size", "creature_type", "environments", "cr", "ac", "ac_note", "hp",
      "hp_formula", "speed", "abilities", "initiative"].concat(DETAILS.map(function (d) { return d[0]; }))
      .concat(LISTS.map(function (l) { return l[0]; })).concat(["note"]);

    function cf(sel) { return $(".eb-cform").querySelector(sel); }
    function mod(score) { return Math.floor(((parseInt(score, 10) || 10) - 10) / 2); }
    function signed(n) { return n >= 0 ? "+" + n : "−" + Math.abs(n); }
    function squash(s) { return String(s == null ? "" : s).split(/\s+/).join(" ").trim(); }
    // Stat block text allows the same bold/italic Markdown the data files use.
    function inlineMd(s) {
      return esc(squash(s)).replace(/\*\*\*(.+?)\*\*\*/g, "<strong><em>$1</em></strong>")
        .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>").replace(/\*(.+?)\*/g, "<em>$1</em>");
    }
    function subtitle(size, ctype, alignment) {
      var s = [size, ctype].filter(Boolean).join(" ");
      return s + (alignment ? (s ? ", " : "") + alignment : "");
    }
    function hpAverage(formula) {
      var m = String(formula || "").replace(/\s+/g, "").replace("−", "-").match(/^(\d+)d(\d+)([+-]\d+)?$/);
      return m ? Math.max(1, Math.floor(m[1] * (+m[2] + 1) / 2) + (+m[3] || 0)) : null;
    }

    function blankCreature() {
      var c = { group: "Custom", size: "Medium", creature_type: "humanoid", cr: "1", speed: "30 ft.", environments: [],
                abilities: { str: 10, dex: 10, con: 10, int: 10, wis: 10, cha: 10 }, actions: [{ name: "", text: "" }] };
      c.type = subtitle(c.size, c.creature_type, "");
      return { c: formData(c), editing: false, idEdited: false, subEdited: false, alignment: "" };
    }
    // Any creature entry (a file's, or blank) as form values: strings, full ability set, list rows.
    function formData(raw) {
      var c = {};
      FIELDS.forEach(function (f) { c[f] = raw[f] == null ? "" : typeof raw[f] === "object" ? raw[f] : String(raw[f]); });
      var scores = raw.abilities || {};
      c.abilities = {};
      ABIL.forEach(function (a) { c.abilities[a] = String(scores[a] == null ? 10 : scores[a]); });
      c.environments = (raw.environments || []).slice();
      LISTS.forEach(function (l) {
        c[l[0]] = (raw[l[0]] || []).map(function (e) { return { name: String(e.name || ""), text: squash(e.text) }; });
      });
      // Size and type from the italic line when the file doesn't list them (as the builder's filters do).
      var words = String(c.type).replace(/,/g, " ").split(/\s+/);
      if (!c.size && sizes.indexOf(words[0]) > -1) c.size = words[0];
      if (!c.creature_type && sizes.indexOf(words[0]) > -1 && words[1]) c.creature_type = words[1].replace(/[()]/g, "").toLowerCase();
      if (!c.cr || !CR_XP.hasOwnProperty(c.cr)) c.cr = "1";
      return c;
    }
    function draftFrom(raw, editing) {
      var c = formData(raw);
      var align = (String(c.type).match(/,\s*(.+)$/) || [])[1] || "";
      return { c: c, editing: editing, idEdited: editing, alignment: align,
               subEdited: !!c.type && c.type !== subtitle(c.size, c.creature_type, align) };
    }

    // The form's values as a creature entry, the way it will be saved (and previewed).
    function toCreature(d) {
      var c = d.c, out = {};
      FIELDS.forEach(function (f) {
        var v = c[f];
        if (typeof v === "string") { v = f === "note" ? v.trim() : squash(v); if (v) out[f] = v; }
      });
      if (!out.hp && hpAverage(c.hp_formula)) out.hp = String(hpAverage(c.hp_formula));
      ["ac", "hp", "initiative"].forEach(function (f) { if (out[f] && /^[+-]?\d+$/.test(out[f])) out[f] = parseInt(out[f], 10); });
      out.abilities = {};
      ABIL.forEach(function (a) { out.abilities[a] = parseInt(c.abilities[a], 10) || 10; });
      if (c.environments.length) out.environments = c.environments.slice();
      LISTS.forEach(function (l) {
        var rows = c[l[0]].map(function (e) { return { name: squash(e.name), text: squash(e.text) }; })
          .filter(function (e) { return e.name || e.text; });
        if (rows.length) out[l[0]] = rows;
      });
      return out;
    }

    function previewHtml(m) {
      var xp = CR_XP[m.cr] || 0, sub = m.type || "";
      var h = '<div class="statblock"><h3>' + esc(m.name || "Unnamed creature") + "</h3>" +
        "<p><em>" + esc(sub) + (sub ? " — " : "") + "CR " + esc(m.cr) + " (" + xp.toLocaleString("en-US") + " XP)</em></p><hr>";
      var head = ["<strong>Armor Class</strong> " + esc(m.ac != null ? m.ac : "?") + (m.ac_note ? " (" + esc(m.ac_note) + ")" : ""),
        "<strong>Hit Points</strong> " + esc(m.hp != null ? m.hp : "?") + (m.hp_formula ? " (" + esc(m.hp_formula) + ")" : ""),
        "<strong>Speed</strong> " + esc(m.speed || "30 ft."),
        "<strong>Initiative</strong> " + signed(m.initiative != null && m.initiative !== "" ? parseInt(m.initiative, 10) || 0 : mod(m.abilities.dex))];
      h += "<p>" + head.join("<br>\n") + "</p>";
      h += "<table><thead><tr>" + ABIL.map(function (a) { return '<th style="text-align: center;">' + a.toUpperCase() + "</th>"; }).join("") +
        "</tr></thead><tbody><tr>" + ABIL.map(function (a) {
          return '<td style="text-align: center;">' + m.abilities[a] + " (" + signed(mod(m.abilities[a])) + ")</td>";
        }).join("") + "</tr></tbody></table>";
      var details = [["Saving Throws", "saves"], ["Skills", "skills"], ["Damage Vulnerabilities", "vulnerabilities"],
        ["Damage Resistances", "resistances"], ["Damage Immunities", "immunities"], ["Condition Immunities", "condition_immunities"],
        ["Senses", "senses"], ["Languages", "languages"]].filter(function (x) { return m[x[1]]; })
        .map(function (x) { return "<strong>" + x[0] + "</strong> " + esc(m[x[1]]); });
      if (details.length) h += "<p>" + details.join("<br>\n") + "</p>";
      h += "<hr>";
      LISTS.forEach(function (l, i) {
        if (!m[l[0]]) return;
        if (i > 0) h += '<p class="sb-section">' + l[1] + "</p>";
        m[l[0]].forEach(function (e) { h += "<p><strong><em>" + inlineMd(e.name) + ".</em></strong> " + inlineMd(e.text) + "</p>"; });
      });
      if (m.note) h += "<hr><p><em>" + inlineMd(m.note) + "</em></p>";
      return h + "</div>";
    }

    // Until a rebuild works out the real role (hooks/campaign.py _combat_role), a close guess.
    function guessRole(m) {
      var texts = [].concat(m.actions || []).map(function (a) { return a.text; }).join(" ");
      var ranged = /Ranged (Weapon|Spell) Attack/.test(texts), melee = /Melee (or Ranged )?(Weapon|Spell) Attack/.test(texts);
      if ((m.traits || []).some(function (t) { return /^Spellcasting/.test(t.name); })) return ["caster", true];
      return [ranged && !melee ? "ranged" : "melee", ranged];
    }

    function creatureYaml(m) {
      var q = function (v) { return typeof v === "number" ? String(v) : JSON.stringify(v); };
      var lines = [];
      FIELDS.forEach(function (f) {
        if (m[f] == null) return;
        if (f === "abilities") lines.push("abilities: {" + ABIL.map(function (a) { return a + ": " + m.abilities[a]; }).join(", ") + "}");
        else if (f === "environments") lines.push("environments: [" + m.environments.map(q).join(", ") + "]");
        else if (Array.isArray(m[f])) {
          lines.push(f + ":");
          m[f].forEach(function (e) { lines.push("  - name: " + q(e.name), "    text: " + q(e.text)); });
        } else lines.push(f + ": " + q(m[f]));
      });
      return "- " + lines.join("\n  ") + "\n";
    }

    function listRows(key, noun) {
      var rows = state.cdraft.c[key];
      return rows.map(function (e, i) {
        var at = ' data-l="' + key + '" data-i="' + i + '"';
        return '<div class="eb-cf-entry"><div class="eb-cf-entryhead"><input' + at + ' data-k="name" placeholder="Name" value="' + esc(e.name) + '">' +
          '<button class="eb-act eb-danger" data-rm="' + key + '" data-i="' + i + '">Remove</button></div>' +
          "<textarea" + at + ' data-k="text" rows="2" placeholder="' +
          (key === "actions" ? "*Melee Weapon Attack:* +5 to hit, reach 5 ft., one target. *Hit:* 7 (1d8 + 3) slashing damage." : "What it does") +
          '">' + esc(e.text) + "</textarea></div>";
      }).join("") + '<button class="eb-act" data-addl="' + key + '">+ Add ' + noun + "</button>";
    }

    function renderCForm() {
      var d = state.cdraft, c = d.c;
      var input = function (f, label, ph, cls) {
        return '<label class="' + (cls || "") + '">' + label + ' <input data-f="' + f + '" value="' + esc(c[f]) + '"' +
          (ph ? ' placeholder="' + esc(ph) + '"' : "") + "></label>";
      };
      var opts = function (list, value) {
        return list.map(function (v) { return '<option value="' + esc(v) + '"' + (v === value ? " selected" : "") + ">" + esc(v || "—") + "</option>"; }).join("");
      };
      $(".eb-cform").innerHTML =
        '<div class="eb-cf-head"><span class="eb-cf-title">' + (d.editing ? "Editing " + esc(c.name || c.id) : "New creature") + "</span>" +
        '<span class="eb-cf-btns"><button class="eb-cf-save md-button md-button--primary">' + (d.editing ? "Save changes" : "Save creature") + "</button>" +
        '<button class="eb-cf-cancel md-button">Cancel</button></span></div>' +
        '<div class="eb-cf-status"></div>' +
        '<div class="eb-cf-cols"><div class="eb-cf-form">' +
        '<fieldset><legend>Basics</legend><div class="eb-cf-grid">' +
        input("name", "Name", "Bog Hag Matron", "eb-w2") +
        '<label>File id <input data-f="id" value="' + esc(c.id) + '"' + (d.editing ? " readonly title=\"Encounters point at the id, so it stays the same once saved.\"" : "") + "></label>" +
        '<label>CR <select data-f="cr">' + opts(CRS, c.cr) + '</select> <span class="eb-cf-xp"></span></label>' +
        '<label>Size <select data-f="size">' + opts([""].concat(sizes), c.size) + "</select></label>" +
        '<label>Type <input data-f="creature_type" list="eb-ctypes" value="' + esc(c.creature_type) + '"></label>' +
        '<datalist id="eb-ctypes">' + CTYPES.map(function (t) { return '<option value="' + t + '">'; }).join("") + "</datalist>" +
        '<label>Alignment <input data-x="alignment" value="' + esc(d.alignment) + '" placeholder="neutral evil"></label>' +
        input("type", "Subtitle (the italic line)", "", "eb-w2") +
        input("group", "Bestiary section", "Custom") +
        '</div><div class="eb-cf-hint eb-cf-namehint"></div></fieldset>' +
        '<fieldset><legend>Environments</legend><div class="eb-cf-envs">' + ENVS.map(function (e) {
          return '<label><input type="checkbox" data-env="' + esc(e) + '"' + (c.environments.indexOf(e) > -1 ? " checked" : "") + "> " + esc(e) + "</label>";
        }).join("") + '</div><div class="eb-cf-hint">Used by the builder\'s environment filter and the generator.</div></fieldset>' +
        '<fieldset><legend>Defenses and movement</legend><div class="eb-cf-grid">' +
        input("ac", "AC", "15") + input("ac_note", "AC note", "natural armor") +
        input("hp", "HP", "") + input("hp_formula", "HP formula", "13d8 + 52") +
        input("speed", "Speed", "30 ft., fly 60 ft.", "eb-w2") + input("initiative", "Initiative (if not Dex)", "") +
        "</div></fieldset>" +
        '<fieldset><legend>Ability scores</legend><div class="eb-cf-abil">' + ABIL.map(function (a) {
          return "<label>" + a.toUpperCase() + ' <input type="number" min="1" max="30" data-a="' + a + '" value="' + esc(c.abilities[a]) + '">' +
            '<span class="eb-cf-mod" data-mod="' + a + '"></span></label>';
        }).join("") + "</div></fieldset>" +
        '<fieldset><legend>Details</legend><div class="eb-cf-grid">' +
        DETAILS.map(function (x) { return input(x[0], x[1], x[2], x[0] === "senses" || x[0] === "resistances" || x[0] === "immunities" ? "eb-w2" : ""); }).join("") +
        "</div></fieldset>" +
        LISTS.map(function (l) {
          return "<fieldset><legend>" + l[1] + '</legend><div class="eb-cf-list" data-list="' + l[0] + '">' + listRows(l[0], l[2]) + "</div>" +
            (l[0] === "actions" ? '<div class="eb-cf-hint">Write attacks as <code>*Melee Weapon Attack:* … *Hit:* 7 (…)</code> so the generator can tell melee from ranged. <code>*text*</code> is italic.</div>' : "") +
            "</fieldset>";
        }).join("") +
        '<fieldset><legend>DM note</legend><textarea data-f="note" rows="3" placeholder="Shown at the bottom of the stat block.">' + esc(c.note) + "</textarea></fieldset>" +
        '</div><div class="eb-cf-preview"></div></div>';
      updateCForm();
    }

    function updateCForm() {
      var d = state.cdraft;
      var m = toCreature(d);
      cf(".eb-cf-preview").innerHTML = previewHtml(m);
      cf(".eb-cf-xp").textContent = (CR_XP[d.c.cr] || 0).toLocaleString("en-US") + " XP";
      ABIL.forEach(function (a) { cf('[data-mod="' + a + '"]').textContent = signed(mod(d.c.abilities[a])); });
      var avg = hpAverage(d.c.hp_formula);
      cf('[data-f="hp"]').placeholder = avg ? String(avg) + " (average)" : "110";
      var hints = [], name = squash(d.c.name).toLowerCase();
      var twin = name && D.creatures.filter(function (x) { return x.name.toLowerCase() === name && x.id !== d.c.id; })[0];
      if (twin) hints.push("There's already a creature called " + esc(twin.name) + " (" + sourceLabel(twin.source) + ")" +
        " - [[mentions]] and families.yml would only find one of them.");
      if (!d.editing && d.c.id && byId[d.c.id]) hints.push("The id " + esc(d.c.id) + " is taken - change the file id.");
      cf(".eb-cf-namehint").innerHTML = hints.join("<br>");
      persist();
    }

    function openCForm(draft) {
      state.cdraft = draft;
      flash("");
      renderCForm();
      setView("builder");
      window.scrollTo({ top: root.getBoundingClientRect().top + window.scrollY - 80 });
    }
    function closeCForm() {
      state.cdraft = null;
      $(".eb-cform").innerHTML = "";
      setView("builder");
    }
    function cstatus(html, kind) {
      if (!state.cdraft) return flash(html, kind);   // the form was closed while the helper was answering
      cf(".eb-cf-status").innerHTML = '<div class="eb-msg eb-' + (kind || "info") + '">' + html + "</div>";
    }

    function loadCreature(id, asCopy) {
      helperFetch(HELPER + "/creature?id=" + encodeURIComponent(id))
        .then(function (r) { return r.json().then(function (j) { return { status: r.status, body: j }; }); })
        .then(function (res) {
          if (res.status !== 200) return flash(esc(res.body.error || "Couldn't load it."), "warn");
          if (!asCopy) return openCForm(draftFrom(res.body.creature, true));
          var raw = Object.assign({}, res.body.creature);
          raw.name = (raw.name || id) + " (copy)";
          raw.id = slug(raw.name);
          raw.group = "Custom";
          openCForm(draftFrom(raw, false));
        })
        .catch(function () { flash(OFFLINE + (ONLINE ? "" : " It's needed to load a creature into the form."), "warn"); });
    }

    function saveCreature() {
      var d = state.cdraft, m = toCreature(d);
      if (!m.name) return cstatus("Give the creature a name.", "warn");
      if (!/^[a-z0-9][a-z0-9-]*$/.test(m.id || "")) return cstatus("The file id can only use lowercase letters, numbers, and dashes.", "warn");
      if (!d.editing && byId[m.id]) return cstatus("The id " + esc(m.id) + " is already used - change the file id.", "warn");
      helperPost("/creature", { creature: m, editing: d.editing }).then(function (res) {
        if (res.status !== 200) return cstatus(esc(res.body.error || "Couldn't save."), "warn");
        var size = m.size || "", role = guessRole(m);
        var entry = { id: m.id, name: m.name, cr: m.cr, xp: CR_XP[m.cr] || 0, size: size, type: m.creature_type || "",
          ac: m.ac, hp: m.hp, source: "custom", env: m.environments || [], sb: previewHtml(m), role: role[0], rc: role[1] };
        var i = D.creatures.findIndex(function (x) { return x.id === m.id; });
        if (i > -1) D.creatures[i] = entry; else D.creatures.push(entry);
        D.creatures.sort(function (a, b) { return a.name.toLowerCase() < b.name.toLowerCase() ? -1 : 1; });
        byId[m.id] = entry;
        closeCForm();
        flash((res.body.updated ? "Updated" : "Saved") + " “" + esc(m.name) + "” in <code>data/monsters/custom.yml</code>. " +
          "It's in the list now; the Bestiary and hover cards pick it up when the site rebuilds.", "ok");
        renderList(); renderTray(); showStatblock(m.id);
      }).catch(function () {
        cstatus(OFFLINE + " Add this to the end of <code>data/monsters/custom.yml</code>" +
          (d.editing ? ", in place of the old entry" : "") + ":" +
          '<textarea class="eb-yaml" readonly rows="10">' + esc(creatureYaml(m)) + "</textarea>", "warn");
      });
    }

    function deleteCreature(id) {
      var c = byId[id];
      var used = (D.encounters || []).filter(function (e) { return e.creatures.some(function (x) { return x.id === id; }); });
      if (used.length) return flash("“" + esc(c.name) + "” is still in " + used.map(function (e) { return "“" + esc(e.name) + "”"; }).join(", ") +
        ". Take it out of those encounters first.", "warn");
      if (!window.confirm("Delete “" + c.name + "”? It's removed from custom.yml; a copy goes to sources/backups/creatures.")) return;
      helperPost("/creature/delete", { id: id }).then(function (res) {
        if (res.status !== 200) return flash(esc(res.body.error || "Couldn't delete it."), "warn");
        D.creatures = D.creatures.filter(function (x) { return x.id !== id; });
        delete byId[id];
        state.tray = state.tray.filter(function (t) { return t.id !== id; });
        $(".eb-sb").innerHTML = '<p class="eb-hint">Click a creature\'s name to see its stat block here.</p>';
        flash("Deleted “" + esc(c.name) + "”. A copy is in <code>" + esc(res.body.backup) + "</code>.", "ok");
        renderList(); renderTray();
      }).catch(function () { flash(OFFLINE, "warn"); });
    }

    $(".eb-cform").addEventListener("input", function (ev) {
      var t = ev.target, d = state.cdraft;
      if (!d) return;
      var f = t.getAttribute("data-f"), a = t.getAttribute("data-a"), l = t.getAttribute("data-l");
      var autoSub = false;
      if (f) {
        d.c[f] = t.value;
        if (f === "name" && !d.editing && !d.idEdited) cf('[data-f="id"]').value = d.c.id = slug(t.value);
        if (f === "id") d.idEdited = true;
        if (f === "type") d.subEdited = !!t.value.trim();   // cleared: back to building it from size, type, alignment
        if (f === "size" || f === "creature_type") autoSub = true;
      } else if (t.getAttribute("data-x") === "alignment") {
        d.alignment = t.value; autoSub = true;
      } else if (a) {
        d.c.abilities[a] = t.value;
      } else if (l) {
        d.c[l][+t.getAttribute("data-i")][t.getAttribute("data-k")] = t.value;
      } else if (t.hasAttribute("data-env")) {
        d.c.environments = Array.from($(".eb-cform").querySelectorAll("[data-env]:checked")).map(function (x) { return x.getAttribute("data-env"); });
      }
      if (autoSub && !d.subEdited) cf('[data-f="type"]').value = d.c.type = subtitle(d.c.size, d.c.creature_type, d.alignment);
      updateCForm();
    });
    $(".eb-cform").addEventListener("click", function (ev) {
      var t = ev.target, d = state.cdraft;
      if (!d) return;
      if (t.classList.contains("eb-cf-save")) return saveCreature();
      if (t.classList.contains("eb-cf-cancel")) {
        if (d.c.name && !window.confirm("Discard " + (d.editing ? "your changes to " : "") + "“" + d.c.name + "”?")) return;
        return closeCForm();
      }
      var key = t.getAttribute("data-addl") || t.getAttribute("data-rm");
      if (!key) return;
      if (t.hasAttribute("data-addl")) d.c[key].push({ name: "", text: "" });
      else d.c[key].splice(+t.getAttribute("data-i"), 1);
      var noun = LISTS.filter(function (x) { return x[0] === key; })[0][2];
      cf('[data-list="' + key + '"]').innerHTML = listRows(key, noun);
      if (t.hasAttribute("data-addl")) cf('[data-list="' + key + '"] .eb-cf-entry:last-of-type input').focus();
      updateCForm();
    });

    // ------------------------------------------------------------ wiring
    $(".eb-psize").value = state.size;
    $(".eb-plevel").value = state.level;
    $(".eb-name").value = state.name;
    $(".eb-loc").value = state.location;
    $(".eb-id").value = state.id;

    ["eb-q", "eb-crmin", "eb-crmax", "eb-type", "eb-size", "eb-env", "eb-source"].forEach(function (c) {
      $("." + c).addEventListener(c === "eb-q" ? "input" : "change", renderList);
    });
    $(".eb-psize").addEventListener("change", function () { state.size = Math.max(1, +this.value || 1); renderTray(); renderEncList(); });
    $(".eb-plevel").addEventListener("change", function () { state.level = Math.min(20, Math.max(1, +this.value || 1)); renderTray(); renderEncList(); });
    $(".eb-lq").addEventListener("input", renderEncList);
    $(".eb-name").addEventListener("input", function () {
      state.name = this.value;
      if (!$(".eb-id").dataset.edited) { $(".eb-id").value = slug(this.value); state.id = $(".eb-id").value; }
      persist();
    });
    $(".eb-loc").addEventListener("input", function () { state.location = this.value; persist(); });
    $(".eb-id").addEventListener("input", function () { this.dataset.edited = "1"; state.id = this.value; persist(); });
    $(".eb-savebtn").addEventListener("click", function () { save(false); });
    $(".eb-g-go").addEventListener("click", generate);
    root.addEventListener("click", function (ev) {   // × on a family chip in the stat block panel
      if (ev.target.getAttribute("data-famact") !== "remove") return;
      var id = ev.target.closest("[data-cid]").getAttribute("data-cid");
      familyChange(id, ev.target.getAttribute("data-fam"), ev.target.getAttribute("data-role"), false, false);
    });
    root.addEventListener("change", function (ev) {   // "+ Add to a family…"
      if (!ev.target.classList.contains("eb-famadd") || !ev.target.value) return;
      var box = ev.target.closest("[data-cid]"), id = box.getAttribute("data-cid");
      var family = ev.target.value, isNew = family === "__new", role = box.querySelector(".eb-famrole").value;
      ev.target.value = "";
      if (isNew) {
        family = (window.prompt("Name of the new family (e.g. Mire Folk):", "") || "").trim();
        if (!family) return;
      }
      familyChange(id, family, role, true, isNew);
    });
    $(".eb-runtray").addEventListener("click", function () {
      if (!state.tray.length) return status("Add some creatures first.", "warn");
      runEncounter($(".eb-name").value.trim() || "Unsaved encounter", state.tray, state.editing);
    });
    $(".eb-clear").addEventListener("click", function () {
      state.tray = []; state.name = state.location = state.id = "";
      $(".eb-name").value = $(".eb-loc").value = $(".eb-id").value = "";
      delete $(".eb-id").dataset.edited;
      $(".eb-status").innerHTML = "";
      renderTray();
    });
    root.addEventListener("click", function (ev) {
      var vb = ev.target.closest(".eb-vbtn");
      if (vb) return setView(vb.getAttribute("data-view"));
      if (ev.target.classList.contains("eb-new")) { clearBuilder(); flash(""); setView("builder"); return draftNotice(); }
      if (ev.target.classList.contains("eb-stop")) { clearBuilder(); return; }
      if (ev.target.classList.contains("eb-newc")) return openCForm(blankCreature());
      var cact = ev.target.getAttribute && ev.target.getAttribute("data-cact");
      if (cact) {
        var cid = ev.target.closest("[data-cid]").getAttribute("data-cid");
        if (cact === "edit") return loadCreature(cid, false);
        if (cact === "copy") return loadCreature(cid, true);
        if (cact === "delete") return deleteCreature(cid);
      }
      var act = ev.target.getAttribute && ev.target.getAttribute("data-act");
      if (act) {
        var eid = ev.target.closest("[data-enc]").getAttribute("data-enc");
        var enc = D.encounters.filter(function (x) { return x.id === eid; })[0];
        if (act === "run") return runEncounter(enc.name, enc.creatures, enc.id);
        if (act === "edit") return loadInto(enc, false);
        if (act === "duplicate") return loadInto(enc, true);
        if (act === "archive") return setArchived(enc, true);
        if (act === "restore") return setArchived(enc, false);
        if (act === "delete") return deleteEnc(enc);
      }
      var row = ev.target.closest("[data-id]");
      if (ev.target.classList.contains("eb-overwrite")) return save(true);
      if (!row) return;
      var id = row.getAttribute("data-id");
      if (ev.target.classList.contains("eb-add")) add(id);
      else if (ev.target.classList.contains("eb-name-link")) showStatblock(id);
      else if (ev.target.classList.contains("eb-plus")) add(id);
      else if (ev.target.classList.contains("eb-minus")) {
        state.tray.forEach(function (t) { if (t.id === id) t.count -= 1; });
        state.tray = state.tray.filter(function (t) { return t.count > 0; });
        renderTray();
      } else if (ev.target.classList.contains("eb-remove")) {
        state.tray = state.tray.filter(function (t) { return t.id !== id; });
        renderTray();
      }
    });

    renderList();
    renderTray();
    if (state.cdraft) renderCForm();   // a creature was being written when the page reloaded
    if (state.flash) { $(".eb-flash").innerHTML = '<div class="eb-msg eb-' + state.flash.kind + '">' + state.flash.html + "</div>"; }
    // "Open in the encounter builder" links from story pages arrive as ?edit=<id>.
    var edit = (location.search.match(/[?&]edit=([a-z0-9-]+)/) || [])[1];
    var target = edit && (D.encounters || []).filter(function (x) { return x.id === edit; })[0];
    // "Run it" links from story pages arrive as ?run=<id>.
    var run = (location.search.match(/[?&]run=([a-z0-9-]+)/) || [])[1];
    var runTarget = run && (D.encounters || []).filter(function (x) { return x.id === run; })[0];
    if (target) {
      history.replaceState(null, "", location.pathname);
      loadInto(target, false);
    } else if (runTarget) {
      history.replaceState(null, "", location.pathname);
      if (state.combat && state.combat.encId === runTarget.id) setView("initiative");   // already running: don't reroll
      else runEncounter(runTarget.name, runTarget.creatures, runTarget.id);
    } else {
      setView(state.view || "active");
    }
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
