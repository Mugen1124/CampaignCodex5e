/* NPC Index cards: Edit on each card, and Add NPC above them. Saves to data/npcs/ through
   hooks/npc_cards.py, on the site's own server while CampaignCodex5e is running; the site then
   rebuilds and the page refreshes by itself. Campaign-owned, like the hook - not an engine file.
   Loaded only on the DM site's NPC Index (the hook adds it), and never online. */
(function () {
  "use strict";
  var ONLINE = location.protocol === "file:" || !/^(127\.0\.0\.1|localhost|\[::1\])$/.test(location.hostname);
  var OFFLINE = "Saving needs CampaignCodex5e running - restart it if you just added NPC cards.";
  var FIELDS = [["name", "Name", "Hester Vane"], ["race", "Race", "Human"], ["role", "Role", "Innkeeper"],
                ["region", "Region", "Greywater"], ["group", "Group", "The Quay (optional)"]];
  var TEXTS = [["hook", "Who they are at a glance", "One or two sentences. Shown on hover.", 2],
               ["description", "Longer description", "Optional; shown on the card in place of the line above.", 3],
               ["appearance", "Appearance", "Flour on her apron, a pencil behind one ear.", 2],
               ["personality", "Personality", "Warm to strangers, merciless to cheats.", 2]];
  var PRIVATE = [["notes", "Notes", "What we've learned, what they want, what they owe us...", 5],
                 ["secret", "Private theories", "Hunches and suspicions.", 3]];

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }

  function init() {
    var bar = document.querySelector(".npc-bar"), box = document.querySelector(".npc-form"),
        page = document.querySelector(".npc-page");
    if (!bar || !box || !page || ONLINE) return;
    var current = null;   // { id: "..." or null (new), portrait: dataURL or null, removePortrait: bool }

    bar.className = "eb pe-bar npc-bar";
    bar.innerHTML = '<button class="md-button npc-add">Add NPC</button><span class="pe-msg"></span>';
    page.querySelectorAll(".npc-card[data-npc]").forEach(function (card) {
      var tools = document.createElement("div");
      tools.className = "eb eb-sbbar";
      tools.innerHTML = '<button class="eb-act" data-npc-edit="' + esc(card.getAttribute("data-npc")) + '">Edit</button>';
      card.insertBefore(tools, card.firstChild);
    });

    function msg(html, kind) {
      bar.querySelector(".pe-msg").innerHTML = html ? '<span class="eb-msg eb-' + (kind || "info") + '">' + html + "</span>" : "";
    }
    function status(html, kind) {
      var el = box.querySelector(".eb-cf-status");
      el.innerHTML = html ? '<div class="eb-msg eb-' + (kind || "info") + '">' + html + "</div>" : "";
    }
    function fail(e) { (box.style.display === "none" ? msg : status)(e.message === "Failed to fetch" ? OFFLINE : esc(e.message), "warn"); }

    function load(id) {
      return fetch("/__npc/get" + (id ? "?id=" + encodeURIComponent(id) : ""), { cache: "no-store" })
        .then(function (r) {
          if (!(r.headers.get("Content-Type") || "").includes("json")) throw new Error(OFFLINE);
          return r.json().then(function (j) { if (!r.ok) throw new Error(j.error || "Couldn't read data/npcs/."); return j; });
        });
    }

    function open(id) {
      load(id).then(function (res) {
        var n = res.npc || {};
        current = { id: id || null, portrait: null, removePortrait: false, had: n.portrait || "" };
        if (!id) {   // a new NPC starts in the region of the first card on the page
          var h = page.querySelector("h2");
          n.region = h ? h.textContent.trim() : "";
        }
        var input = function (f) {
          return "<label" + (f[0] === "name" ? ' class="eb-w2"' : "") + ">" + f[1] +
            ' <input data-f="' + f[0] + '" value="' + esc(n[f[0]]) + '" placeholder="' + esc(f[2]) + '"></label>';
        };
        var area = function (f) {
          return '<label class="npc-area">' + f[1] + ' <textarea data-f="' + f[0] + '" rows="' + f[3] +
            '" placeholder="' + esc(f[2]) + '">' + esc(n[f[0]]) + "</textarea></label>";
        };
        var locs = '<label>Location <select data-f="location"><option value="">—</option>' +
          res.locations.map(function (l) {
            return '<option value="' + esc(l.id) + '"' + (l.id === n.location ? " selected" : "") + ">" + esc(l.name) + "</option>";
          }).join("") + "</select></label>";
        var stat = '<label>Status <select data-f="status">' + res.statuses.map(function (s) {
          return '<option value="' + s + '"' + ((n.status || "alive") === s ? " selected" : "") + ">" + s.charAt(0).toUpperCase() + s.slice(1) + "</option>";
        }).join("") + "</select></label>";
        var shown = n.portrait ? "../" + n.portrait.replace(/^\/+/, "") : "";
        box.innerHTML =
          '<div class="eb-cf-head"><span class="eb-cf-title">' + (id ? "Editing " + esc(n.name) : "New NPC") + "</span>" +
          '<span class="eb-cf-btns"><button class="npc-save md-button md-button--primary">' + (id ? "Save changes" : "Add NPC") + "</button>" +
          '<button class="npc-cancel md-button">Cancel</button></span></div>' +
          '<div class="eb-cf-status"></div>' +
          '<fieldset><legend>Who they are</legend><div class="eb-cf-grid">' + FIELDS.map(input).join("") + locs + stat + "</div>" +
          TEXTS.map(area).join("") + "</fieldset>" +
          '<fieldset><legend>Private - never on the players\' site</legend>' + PRIVATE.map(area).join("") + "</fieldset>" +
          '<fieldset><legend>Portrait</legend><div class="npc-portrait-edit">' +
          '<img class="npc-portrait-preview" alt=""' + (shown ? ' src="' + esc(shown) + '"' : ' style="display:none"') + ">" +
          '<div><input type="file" accept="image/png,image/jpeg,image/webp,image/gif" class="npc-file">' +
          '<button class="eb-act eb-danger npc-unpic"' + (shown ? "" : ' style="display:none"') + ">Remove portrait</button>" +
          '<div class="eb-cf-hint">PNG, JPEG, WebP or GIF, up to 10 MB. Saved in docs/npc-portraits/.</div></div></div></fieldset>';
        page.style.display = "none"; bar.style.display = "none"; box.style.display = "";
        box.scrollIntoView({ block: "start" });
      }).catch(fail);
    }

    function close() {
      current = null;
      box.innerHTML = ""; box.style.display = "none"; page.style.display = ""; bar.style.display = "";
    }

    function save() {
      var npc = {};
      box.querySelectorAll("[data-f]").forEach(function (el) { npc[el.getAttribute("data-f")] = el.value; });
      var btn = box.querySelector(".npc-save");
      btn.disabled = true;
      status("Saving…");
      fetch("/__npc/save", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id: current.id, npc: npc, portrait: current.portrait, remove_portrait: current.removePortrait })
      }).then(function (r) {
        return r.json().then(function (j) { if (!r.ok) throw new Error(j.error || "Couldn't save."); return j; });
      }).then(function (j) {
        status("Saved to " + esc(j.saved) + " — the page refreshes in a moment.", "ok");
      }).catch(function (e) { btn.disabled = false; fail(e); });
    }

    document.addEventListener("click", function (e) {
      var t = e.target;
      if (t.closest(".npc-add")) return open(null);
      var ed = t.closest("[data-npc-edit]");
      if (ed) return open(ed.getAttribute("data-npc-edit"));
      if (!current) return;
      if (t.closest(".npc-cancel")) return close();
      if (t.closest(".npc-save")) return save();
      if (t.closest(".npc-unpic")) {
        current.portrait = null; current.removePortrait = true;
        var img = box.querySelector(".npc-portrait-preview");
        img.removeAttribute("src"); img.style.display = "none";
        box.querySelector(".npc-file").value = "";
        t.style.display = "none";
      }
    });
    document.addEventListener("change", function (e) {
      if (!current || !e.target.classList.contains("npc-file")) return;
      var file = e.target.files[0];
      if (!file) return;
      if (file.size > 10 * 1024 * 1024) { e.target.value = ""; return status("That image is over 10 MB - use a smaller one.", "warn"); }
      var reader = new FileReader();
      reader.onload = function () {
        current.portrait = reader.result; current.removePortrait = false;
        var img = box.querySelector(".npc-portrait-preview");
        img.src = reader.result; img.style.display = "";
        box.querySelector(".npc-unpic").style.display = "";
        status("");
      };
      reader.readAsDataURL(file);
    });
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
