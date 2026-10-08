/* Who carries what. On the site at home (CampaignCodex5e running):
     - Items page: a "Held by" picker under every item, and "Players' site": automatic (the usual
       rules - session page mentions, revealed.yml, carried), always show, or always hide, and the pickups tools/transcribe.py noticed
       in session transcripts, each with Assign / Dismiss.
     - Items page: claims players made on their site for items you marked "Found — up for grabs",
       with Approve (gives it to them) / Decline.
     - Party page: "Give an item" on each character card - a search box (type part of a name), so it
       stays usable however many items there are. Empty, it lists the items nobody carries yet. It only
       offers items the players can see; hidden ones (Items page, "Players' site") are left out.
   Saves through the local save helper (tools/site_helper.py), which changes only that item's
   holder: line in data/items/. After a save, CampaignCodex5e rebuilds and the page refreshes by itself.
   An item with a holder shows under Carrying on that character's card, on both sites, and is
   revealed on the players' site. The online copies don't show any of this. */
(function () {
  "use strict";
  var HELPER = "http://127.0.0.1:8765";
  // Which campaign this page belongs to (hooks/campaign.py puts it in every page), so saved state
  // stays separate when two campaigns are served on one computer.
  var CAMPAIGN = (document.querySelector('meta[name="codex-campaign"]') || {}).content || "codex";
  var ONLINE = location.protocol !== "file:" && !/^(127\.0\.0\.1|localhost|\[::1\])$/.test(location.hostname);
  var OFFLINE = "The save helper isn't running (it starts with <code>CampaignCodex5e</code>).";

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }
  function call(path, body) {
    var opts = body ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) } : {};
    return fetch(HELPER + path, opts).then(function (r) {
      return r.json().then(function (j) { return { status: r.status, body: j }; });
    });
  }
  function holderOptions(party, value, blank) {
    return '<option value="">' + esc(blank) + "</option>" +
      party.concat(["Party", "Unclaimed"]).map(function (n) {
        return '<option value="' + esc(n) + '"' + (n.toLowerCase() === String(value || "").toLowerCase() ? " selected" : "") + ">" +
          esc(n === "Party" ? "The party (shared)" : n === "Unclaimed" ? "Found — up for grabs" : n) + "</option>";
      }).join("");
  }
  function note(el, html, kind) {
    el.innerHTML = html ? '<span class="eb-msg eb-' + (kind || "info") + '">' + html + "</span>" : "";
  }

  function init() {
    var holds = Array.from(document.querySelectorAll(".item-hold[data-item]"));
    var suggest = document.querySelector(".item-suggest");
    var cards = Array.from(document.querySelectorAll(".pc-cards .pc-card[data-pc]"));
    if (ONLINE || (!holds.length && !suggest && !cards.length)) return;

    call("/items").then(function (res) {
      var data = res.body, byId = {};
      data.items.forEach(function (i) { byId[i.id] = i; });

      // ---------------------------------------------------------- Items page: Held by
      holds.forEach(function (box) {
        var item = byId[box.getAttribute("data-item")];
        if (!item) return;
        box.className += " eb";
        var said = box.previousElementSibling;   // the plain "Held by:" line - the picker says it now
        if (said && /^Held by:/.test(said.textContent)) said.style.display = "none";
        var setting = box.getAttribute("data-reveal") || "auto", shownNow = box.getAttribute("data-shown") === "1";
        box.innerHTML = '<label class="item-hold-label">Held by <select class="item-holder">' + holderOptions(data.party, item.holder, "— nobody yet —") +
          '</select></label> <label class="item-hold-label item-reveal-label">Players\' site <select class="item-reveal">' +
          '<option value="auto"' + (setting === "auto" ? " selected" : "") + ">Automatic — " + (shownNow ? "shown" : "hidden") + "</option>" +
          '<option value="show"' + (setting === "show" ? " selected" : "") + ">Always show</option>" +
          '<option value="hide"' + (setting === "hide" ? " selected" : "") + ">Always hide</option></select></label>" +
          ' <span class="item-hold-msg"></span>';
        if (setting === "auto") box.querySelector(".item-reveal").title = "Automatic: " + (shownNow ? "shown, because " : "hidden, because ") + (box.getAttribute("data-why") || "") + ".";
        box.querySelector(".item-reveal").addEventListener("change", function (ev) {
          var msg = box.querySelector(".item-hold-msg");
          call("/item/reveal", { id: item.id, reveal: ev.target.value }).then(function (r) {
            if (r.status !== 200) return note(msg, esc(r.body.error || "Couldn't save it."), "warn");
            note(msg, "Saved — run <code>publish</code> to update the players' site.", "ok");
          }).catch(function () { note(msg, OFFLINE, "warn"); });
        });
        box.querySelector(".item-holder").addEventListener("change", function (ev) {
          var msg = box.querySelector(".item-hold-msg");
          call("/item/holder", { id: item.id, holder: ev.target.value }).then(function (r) {
            if (r.status !== 200) return note(msg, esc(r.body.error || "Couldn't save it."), "warn");
            item.holder = r.body.holder;
            note(msg, "Saved to <code>" + esc(r.body.file) + "</code> — the page refreshes after the rebuild.", "ok");
          }).catch(function () { note(msg, OFFLINE, "warn"); });
        });
      });

      // ---------------------------------------------------------- Party page: Give an item
      var SHOWN = 8;   // results listed at a time
      var seen = document.querySelector(".items-visible"), visible = null;   // items the players can see
      if (seen) {
        visible = {};
        (seen.getAttribute("data-ids") || "").split(" ").forEach(function (id) { if (id) visible[id] = true; });
      }
      function matches(who, q) {
        q = q.trim().toLowerCase();
        var pool = data.items.filter(function (i) { return i.holder.toLowerCase() !== who.toLowerCase() && (!visible || visible[i.id]); });
        var free = function (i) { return !i.holder || i.holder === "Unclaimed"; };
        if (!q) return pool.filter(free);   // nothing typed: what nobody carries
        return pool.map(function (i) {
          var at = i.name.toLowerCase().indexOf(q);
          var word = (" " + i.name.toLowerCase()).indexOf(" " + q);
          return { i: i, rank: at < 0 ? -1 : (word >= 0 ? 0 : 1) + (free(i) ? 0 : 2) };   // word starts, then unheld first
        }).filter(function (x) { return x.rank >= 0; })
          .sort(function (a, b) { return a.rank - b.rank || a.i.name.localeCompare(b.i.name); })
          .map(function (x) { return x.i; });
      }
      cards.forEach(function (card) {
        var who = data.party[+card.getAttribute("data-pc")];
        if (!who) return;
        var bar = document.createElement("div");
        bar.className = "eb item-give";
        bar.innerHTML = '<div class="item-give-box"><input class="item-give-q" type="search" autocomplete="off" ' +
          'placeholder="Give an item — type to search" aria-label="Give ' + esc(who) + ' an item">' +
          '<div class="item-give-list" role="listbox" hidden></div></div><span class="item-hold-msg"></span>';
        card.appendChild(bar);
        var q = bar.querySelector(".item-give-q"), list = bar.querySelector(".item-give-list"),
            msg = bar.querySelector(".item-hold-msg"), found = [], pick = 0;
        function show() {
          var all = matches(who, q.value);
          found = all.slice(0, SHOWN);
          pick = Math.min(pick, Math.max(found.length - 1, 0));
          list.innerHTML = !found.length
            ? '<div class="item-give-none">' + (q.value.trim() ? "No item the players can see matches." : "Every item the players can see has someone carrying it — type to search them.") + "</div>"
            : found.map(function (i, k) {
                return '<div class="item-give-opt' + (k === pick ? " item-give-on" : "") + '" role="option" data-k="' + k + '">' + esc(i.name) +
                  (i.holder === "Unclaimed" ? ' <span class="item-give-held">up for grabs</span>'
                   : i.holder ? ' <span class="item-give-held">held by ' + esc(i.holder === "Party" ? "the party" : i.holder) + "</span>" : "") + "</div>";
              }).join("") + (all.length > SHOWN ? '<div class="item-give-none">' + (all.length - SHOWN) + " more — keep typing.</div>" : "");
          list.hidden = false;
        }
        function give(i) {
          if (!i) return;
          if (i.holder && i.holder !== "Unclaimed" && !window.confirm(i.name + " is held by " + (i.holder === "Party" ? "the party" : i.holder) + ". Give it to " + who + " instead?")) return;
          list.hidden = true;
          q.value = "";
          call("/item/holder", { id: i.id, holder: who }).then(function (r) {
            if (r.status !== 200) return note(msg, esc(r.body.error || "Couldn't save it."), "warn");
            i.holder = who;
            note(msg, "Gave " + esc(who) + " the " + esc(i.name) + " — the page refreshes after the rebuild.", "ok");
          }).catch(function () { note(msg, OFFLINE, "warn"); });
        }
        q.addEventListener("focus", function () { pick = 0; show(); });
        q.addEventListener("input", function () { pick = 0; show(); });
        q.addEventListener("keydown", function (ev) {
          if (ev.key === "ArrowDown" || ev.key === "ArrowUp") {
            ev.preventDefault();
            pick = (pick + (ev.key === "ArrowDown" ? 1 : -1) + found.length) % Math.max(found.length, 1);
            show();
          } else if (ev.key === "Enter") {
            ev.preventDefault();
            give(found[pick]);
          } else if (ev.key === "Escape") {
            list.hidden = true;
          }
        });
        list.addEventListener("mousedown", function (ev) {   // before the box loses focus
          var opt = ev.target.closest(".item-give-opt");
          if (opt) { ev.preventDefault(); give(found[+opt.getAttribute("data-k")]); }
        });
        q.addEventListener("blur", function () { setTimeout(function () { list.hidden = true; }, 100); });
      });

      // ---------------------------------------------------------- Items page: players' claims
      var claimBox = document.querySelector(".item-claims");
      if (claimBox) {
        call("/item/claims").then(function (r) {
          var list = r.body.claims || [];
          if (r.status !== 200 || !list.length) return;
          claimBox.className += " eb";
          claimBox.innerHTML = '<div class="item-sug-box"><p class="item-sug-title">Claimed on the players\' site</p>' +
            list.map(function (c, k) {
              return '<div class="item-sug" data-k="' + k + '"><div class="item-sug-what"><b>' + esc(c.character) + "</b> wants the <b>" +
                esc(c.item_name) + "</b> " + '<span class="item-sug-when">' + esc(new Date(c.at).toLocaleString()) + "</span></div>" +
                '<div class="item-sug-act"><button class="eb-act" data-c="approve">Approve</button>' +
                '<button class="eb-act eb-danger" data-c="reject">Decline</button><span class="item-hold-msg"></span></div></div>';
            }).join("") + "</div>";
          claimBox.addEventListener("click", function (ev) {
            var a = ev.target.getAttribute("data-c");
            if (!a) return;
            var row = ev.target.closest(".item-sug"), c = list[+row.getAttribute("data-k")], msg = row.querySelector(".item-hold-msg");
            call("/item/claim", { id: c.id, action: a }).then(function (res) {
              if (res.status !== 200) return note(msg, esc(res.body.error || "Couldn't do that."), "warn");
              row.classList.add("item-sug-done");
              row.querySelector(".item-sug-act").innerHTML = '<span class="eb-msg eb-ok">' + (a === "approve"
                ? "Given to " + esc(c.character) + " — run <code>publish</code> to show it on their card." : "Declined.") + "</span>";
            }).catch(function () { note(msg, OFFLINE, "warn"); });
          });
        }).catch(function () {});
      }

      // ---------------------------------------------------------- Items page: from transcripts
      if (!suggest) return;
      var prefs = {};
      try { prefs = JSON.parse(localStorage.getItem(CAMPAIGN + "-recorder") || "{}"); } catch (e) {}   // the Record page's folder
      call("/item/suggestions?folder=" + encodeURIComponent(prefs.folder || "")).then(function (r) {
        var list = r.body.suggestions || [];
        if (!list.length) return;
        suggest.className += " eb";
        suggest.innerHTML = '<div class="item-sug-box"><p class="item-sug-title">From session transcripts — did someone take these?</p>' +
          list.map(function (s, k) {
            return '<div class="item-sug" data-k="' + k + '"><div class="item-sug-what"><b>' + esc(s.item) + "</b> " +
              '<span class="item-sug-when">' + esc(s.recording) + " at " + esc(s.time) + "</span>" +
              '<div class="item-sug-line">“' + esc(s.line) + "”</div></div>" +
              '<div class="item-sug-act"><select>' + holderOptions(data.party, s.holder, "Who has it?") + "</select>" +
              '<button class="eb-act" data-a="assign">Assign</button><button class="eb-act" data-a="dismiss">Dismiss</button>' +
              '<span class="item-hold-msg"></span></div></div>';
          }).join("") + "</div>";
        suggest.addEventListener("click", function (ev) {
          var a = ev.target.getAttribute("data-a");
          if (!a) return;
          var row = ev.target.closest(".item-sug"), s = list[+row.getAttribute("data-k")], msg = row.querySelector(".item-hold-msg");
          call("/item/suggestion", { file: s.file, n: s.n, action: a, holder: row.querySelector("select").value }).then(function (r) {
            if (r.status !== 200) return note(msg, esc(r.body.error || "Couldn't save it."), "warn");
            row.classList.add("item-sug-done");
            row.querySelector(".item-sug-act").innerHTML = '<span class="eb-msg eb-ok">' + esc(r.body.done) + "</span>";
          }).catch(function () { note(msg, OFFLINE, "warn"); });
        });
      }).catch(function () {});
    }).catch(function () {
      holds.forEach(function (box) { box.innerHTML = ""; });
    });
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
