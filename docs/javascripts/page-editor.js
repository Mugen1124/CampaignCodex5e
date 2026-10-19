/* Page editor: the pencil beside a page's title opens the page in an editor and saves it back to
   docs/ through hooks/page_editor.py, on the site's own server while CampaignCodex5e is running; the
   site then rebuilds and the page reloads. Campaign-owned, like the hook - not an engine file. Never
   on the players' site, and never online.

   Two editors:
   - Visual (Toast UI Editor): typed like a document, no Markdown needed. Session pages, This Session
     and the World/town pages open in it. The page is split into its boxes (Previously…, Private
     theories, At a glance…), each edited in place - on session pages each "## Heading" section is a
     labelled field too; parts the site fills in itself ({{ markers }},
     players: hide/end lines) are shown as grey bars and kept exactly as they are. Only the parts you
     actually change are rewritten.
   - Markdown (EasyMDE): the page as written, for every other page. Either one can switch to the other. */
(function () {
  "use strict";
  var ONLINE = location.protocol === "file:" || !/^(127\.0\.0\.1|localhost|\[::1\])$/.test(location.hostname);
  var SRC = window.PAGE_EDITOR_SRC;
  var VENDOR = window.PAGE_EDITOR_VENDOR || "javascripts/vendor/";
  var VISUAL = /^(index\.md$|sessions\/|world\/|cities\/)/;
  var PENCIL = '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8" ' +
               'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 20h4L19 9l-4-4L4 16z"/>' +
               '<path d="m13.5 6.5 4 4"/></svg>';
  var TRASH = '<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="1.8" ' +
              'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 7h16M10 11v6M14 11v6"/>' +
              '<path d="M6 7l1 13h10l1-13M9 7V4h6v3"/></svg>';

  // While the editor is open the site's live reload waits: adding an image changes docs/, which
  // would otherwise reload the page and lose what you're typing. It goes ahead once the editor closes.
  var HOLD = { on: false, pending: null };
  (function () {
    var open = XMLHttpRequest.prototype.open, send = XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.open = function (method, url) {
      this._peLive = /^\/livereload\//.test(String(url));
      return open.apply(this, arguments);
    };
    XMLHttpRequest.prototype.send = function () {
      var handler = this.onloadend;
      if (this._peLive && handler) this.onloadend = function () {
        var xhr = this;
        if (HOLD.on) HOLD.pending = function () { handler.call(xhr); };
        else handler.call(xhr);
      };
      return send.apply(this, arguments);
    };
  })();
  function holdReload(on) {
    HOLD.on = on;
    if (!on && HOLD.pending) { var go = HOLD.pending; HOLD.pending = null; go(); }
  }

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }

  function init() {
    var title = document.querySelector(".md-content__inner > h1");
    if (!title || !SRC || ONLINE || typeof EasyMDE === "undefined" || title.querySelector(".pe-pencil")) return;
    var btn = document.createElement("button");
    btn.className = "pe-pencil";
    btn.type = "button";
    btn.title = "Edit this page";
    btn.setAttribute("aria-label", "Edit this page");
    btn.innerHTML = PENCIL;
    title.appendChild(btn);
    btn.addEventListener("click", open);

    // Sessions: New session on the Sessions page; a small Delete at the foot of each session page.
    if (SRC === "index.md") title.insertAdjacentElement("afterend", sessionBar(
      '<button class="md-button md-button--primary pe-new-session" type="button">New session</button>', newSession));
    if (/^sessions\/[^/]+\.md$/.test(SRC)) {
      var foot = sessionBar('<button class="pe-delete-session" type="button" title="Delete this session" ' +
        'aria-label="Delete this session">' + TRASH + '<span>Delete session</span></button>', deleteSession);
      foot.classList.add("pe-session-foot");
      title.parentElement.appendChild(foot);
    }
    // Just made by New session: open straight into the editor.
    if (location.hash === "#edit") { history.replaceState(null, "", location.pathname); open(); }
  }

  function sessionBar(inner, onClick) {
    var bar = document.createElement("div");
    bar.className = "pe-session-bar";
    bar.innerHTML = inner + '<span class="pe-session-msg" aria-live="polite"></span>';
    bar.querySelector("button").addEventListener("click", function () { onClick(bar); });
    return bar;
  }

  function post(url, body) {
    return fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) })
      .then(function (r) { return r.json().then(function (j) { if (!r.ok) throw new Error(j.error || "Something went wrong."); return j; }); });
  }

  function newSession(bar) {
    if (bar.querySelector("form")) return;
    fetch("/__page/new-session-info", { cache: "no-store" }).then(function (r) { return r.json(); }).then(function (info) {
      var form = document.createElement("form");
      form.className = "pe-session-form";
      form.innerHTML =
        '<label>Session ' + info.number + ' name <input name="title" required placeholder="The Lighthouse"></label>' +
        '<label>Where <input name="place" required value="' + esc(info.place) + '"></label>' +
        '<button class="md-button md-button--primary" type="submit">Create and start writing</button>' +
        '<button class="md-button pe-cancel" type="button">Cancel</button>';
      bar.appendChild(form);
      form.elements.namedItem("title").focus();
      form.querySelector(".pe-cancel").addEventListener("click", function () { form.remove(); });
      form.addEventListener("submit", function (e) {
        e.preventDefault();
        var msg = bar.querySelector(".pe-session-msg");
        msg.textContent = "Creating…";
        post("/__page/new-session", { title: form.elements.namedItem("title").value, place: form.elements.namedItem("place").value })
          .then(function (res) { msg.textContent = "Created - opening it…"; waitFor(res.url); })
          .catch(function (err) { msg.textContent = err.message === "Failed to fetch" ? "Needs CampaignCodex5e running." : err.message; });
      });
    });
  }

  // The site rebuilds after a new page is added; open it once it's there.
  function waitFor(url, tries) {
    var to = "/" + url;
    fetch(to, { method: "HEAD", cache: "no-store" }).then(function (r) {
      if (r.ok) location.href = to + "#edit";
      else if ((tries || 0) < 40) setTimeout(function () { waitFor(url, (tries || 0) + 1); }, 750);
    }).catch(function () { setTimeout(function () { waitFor(url, (tries || 0) + 1); }, 750); });
  }

  function deleteSession(bar) {
    var name = (document.querySelector(".md-content__inner > h1").firstChild || {}).textContent || "this session";
    if (!confirm("Delete \"" + name.trim() + "\"?\n\nIt comes off the site; a copy is kept in sources/backups/deleted/.")) return;
    var msg = bar.querySelector(".pe-session-msg");
    msg.textContent = "Deleting…";
    post("/__page/delete-session", { src: SRC })
      .then(function () { msg.textContent = "Deleted - going to Sessions…"; setTimeout(function () { location.href = "/"; }, 1500); })
      .catch(function (err) { msg.textContent = err.message === "Failed to fetch" ? "Needs CampaignCodex5e running." : err.message; });
  }

  function open() {
    if (document.querySelector(".pe-editor")) return;
    fetch("/__page/get?src=" + encodeURIComponent(SRC), { cache: "no-store" })
      .then(function (r) { return r.json().then(function (j) { return { ok: r.ok, j: j }; }); })
      .then(function (res) {
        if (!res.ok) throw new Error(res.j.error || "Couldn't open this page.");
        (VISUAL.test(res.j.src) ? visual : markdown)(res.j, res.j.text, false);
      })
      .catch(function (err) {
        alert(err.message === "Failed to fetch"
          ? "Editing needs CampaignCodex5e running - restart it if you just added the page editor."
          : err.message);
      });
  }

  // ---------------------------------------------------------------- the editor window

  function frame(page, switchLabel, hint) {
    var box = document.createElement("div");
    box.className = "pe-editor";
    box.setAttribute("role", "dialog");
    box.setAttribute("aria-label", "Edit page");
    box.innerHTML =
      '<div class="pe-panel">' +
        '<div class="pe-head"><span class="pe-title">Editing <code>docs/' + esc(page.src) + '</code></span>' +
        '<span class="pe-status" aria-live="polite"></span>' +
        (switchLabel ? '<button class="md-button pe-switch" type="button">' + switchLabel + '</button>' : "") +
        '<button class="md-button md-button--primary pe-save" type="button">Save</button>' +
        '<button class="md-button pe-cancel" type="button">Cancel</button></div>' +
        '<div class="pe-body"></div>' +
        '<div class="pe-hint">' + hint + '</div>' +
      "</div>";
    document.body.appendChild(box);
    document.documentElement.classList.add("pe-open");
    holdReload(true);
    return box;
  }

  // Save, Cancel, Ctrl+S, Esc and the Visual/Markdown switch, for either editor. `ed` gives
  // text(), destroy(), mode, page and dirty.
  function wire(box, ed) {
    var status = box.querySelector(".pe-status");
    ed.changed = function () { ed.dirty = true; status.textContent = "Unsaved changes"; };
    if (ed.dirty) status.textContent = "Unsaved changes";

    function shut() {
      ed.destroy();
      box.remove();
      document.documentElement.classList.remove("pe-open");
      document.removeEventListener("keydown", onKey);
    }
    function close() {
      if (ed.dirty && !confirm("Discard your changes to this page?")) return;
      shut();
      holdReload(false);
    }
    function onKey(e) {
      if (e.key === "Escape") close();
      if ((e.ctrlKey || e.metaKey) && e.key === "s") { e.preventDefault(); save(); }
    }
    function save() {
      status.textContent = "Saving…";
      var text;
      try { text = ed.text(); } catch (err) { status.textContent = "Couldn't read the editor: " + err.message; return; }
      fetch("/__page/save", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ src: ed.page.src, text: text, hash: ed.page.hash })
      })
        .then(function (r) { return r.json().then(function (j) { return { ok: r.ok, j: j }; }); })
        .then(function (res) {
          if (!res.ok) throw new Error(res.j.error || "Couldn't save.");
          ed.page.hash = res.j.hash;
          ed.dirty = false;
          status.textContent = "Saved - the page will reload in a moment";
          setTimeout(function () { location.reload(); }, 1500);
        })
        .catch(function (err) {
          status.textContent = err.message === "Failed to fetch"
            ? "Saving needs CampaignCodex5e running." : err.message;
        });
    }
    var sw = box.querySelector(".pe-switch");
    if (sw) sw.addEventListener("click", function () {
      var text = ed.text(), dirty = ed.dirty;
      shut();
      (ed.mode === "visual" ? markdown : visual)(ed.page, text, dirty);
    });
    box.querySelector(".pe-save").addEventListener("click", save);
    box.querySelector(".pe-cancel").addEventListener("click", close);
    document.addEventListener("keydown", onKey);
  }

  // ---------------------------------------------------------------- Markdown editor (EasyMDE)

  function markdown(page, text, dirty) {
    var box = frame(page, VISUAL.test(page.src) ? "Visual editor" : "",
      'Markdown, as the page is written: <code>[[Name]]</code> links, <code>{{ markers }}</code> and ' +
      '<code>??? dm</code> boxes all work as before. A copy of the old version is kept in sources/backups/pages/.');
    var area = document.createElement("textarea");
    box.querySelector(".pe-body").appendChild(area);
    var mde = new EasyMDE({
      element: area,
      initialValue: text,
      autofocus: true,
      spellChecker: false,
      nativeSpellcheck: true,
      autoDownloadFontAwesome: false,
      status: ["lines", "words"],
      minHeight: "50vh",
      sideBySideFullscreen: false,
      toolbar: [
        { name: "bold", action: EasyMDE.toggleBold, text: "B", title: "Bold" },
        { name: "italic", action: EasyMDE.toggleItalic, text: "I", title: "Italic" },
        { name: "heading", action: EasyMDE.toggleHeadingSmaller, text: "H", title: "Heading" },
        "|",
        { name: "quote", action: EasyMDE.toggleBlockquote, text: "“", title: "Quote" },
        { name: "unordered-list", action: EasyMDE.toggleUnorderedList, text: "•", title: "Bulleted list" },
        { name: "ordered-list", action: EasyMDE.toggleOrderedList, text: "1.", title: "Numbered list" },
        { name: "link", action: EasyMDE.drawLink, text: "Link", title: "Link" },
        { name: "mention", action: function (ed) { wrap(ed, "[[", "]]", "Name"); }, text: "[[ ]]",
          title: "Link a person, place or item" },
        { name: "dm-box", action: function (ed) { dmBox(ed); }, text: "Private", title: "Private theories box (never on the players' site)" },
        "|",
        { name: "side-by-side", action: EasyMDE.toggleSideBySide, text: "Preview", title: "Live preview beside the text" },
        { name: "undo", action: EasyMDE.undo, text: "↶", title: "Undo" },
        { name: "redo", action: EasyMDE.redo, text: "↷", title: "Redo" }
      ]
    });
    var ed = { mode: "markdown", page: page, dirty: dirty,
               text: function () { return mde.value(); },
               destroy: function () { mde.toTextArea(); } };
    mde.codemirror.on("change", function () { ed.changed(); });
    wire(box, ed);
  }

  function wrap(ed, before, after, fallback) {
    var cm = ed.codemirror, sel = cm.getSelection() || fallback;
    cm.replaceSelection(before + sel + after);
    cm.focus();
  }

  function dmBox(ed) {
    var cm = ed.codemirror, sel = cm.getSelection() || "Your private theory.";
    var body = sel.split("\n").map(function (l) { return "    " + l; }).join("\n");
    cm.replaceSelection('\n??? dm "Private theories"\n' + body + "\n");
    cm.focus();
  }

  // ---------------------------------------------------------------- Visual editor (Toast UI)

  function loadToast(done) {
    if (window.toastui && window.toastui.Editor) return done();
    window.tui = window.tui || {};
    window.tui.usageStatistics = false;        // never phone home
    ["toastui/toastui-editor.css", "toastui/toastui-editor-dark.css"].forEach(function (href) {
      var link = document.createElement("link");
      link.rel = "stylesheet";
      link.href = VENDOR + href;
      document.head.appendChild(link);
    });
    var s = document.createElement("script");
    s.src = VENDOR + "toastui/toastui-editor-all.min.js";
    s.onload = done;
    s.onerror = function () { alert("Couldn't load the visual editor (docs/javascripts/vendor/toastui/)."); };
    document.head.appendChild(s);
  }

  var BOX = /^(!!!|\?\?\?\+?)\s+([\w-]+)(?:\s+"(.*)")?\s*$/;

  function lockedStart(line) {
    return /^\s*\{\{.*\}\}\s*$/.test(line) || /^\s*<!--/.test(line) || /^\s*\{[:.#]/.test(line) || /^<[a-zA-Z\/]/.test(line);
  }

  // The page body as segments: text (edited visually), box (!!! / ??? with its own segments
  // inside) and locked (kept as written).
  // With `fields` (session pages), each "## Heading" and the text under it is a labelled field.
  function parse(lines, fields) {
    var out = [], text = null, fence = false, i = 0;
    function flush() { if (text) { out.push(text); text = null; } }
    while (i < lines.length) {
      var line = lines[i], m;
      if (fields && !fence && (m = /^##\s+(.+?)\s*#*\s*$/.exec(line))) {
        flush();
        text = { type: "text", head: line, label: m[1], lines: [] };
        i++;
        continue;
      }
      if (!fence && (m = BOX.exec(line))) {
        flush();
        var body = [], j = i + 1;
        while (j < lines.length && (lines[j].trim() === "" || /^( {4}|\t)/.test(lines[j]))) {
          body.push(lines[j].replace(/^( {4}|\t)/, ""));
          j++;
        }
        while (body.length && body[body.length - 1].trim() === "") { body.pop(); j--; }
        out.push({ type: "box", head: line, kind: m[2], title: m[3] != null ? m[3] : m[2], children: parse(body) });
        i = j;
        continue;
      }
      if (!fence && lockedStart(line)) {
        flush();
        var lk = [line], k = i + 1;
        if (/^\s*<!--/.test(line)) {
          if (line.indexOf("-->") < 0) while (k < lines.length) { lk.push(lines[k]); k++; if (lines[k - 1].indexOf("-->") >= 0) break; }
        } else if (/^</.test(line)) {
          while (k < lines.length && lines[k].trim() !== "") { lk.push(lines[k]); k++; }
        }
        out.push({ type: "locked", lines: lk });
        i = k;
        continue;
      }
      if (/^\s*(```|~~~)/.test(line)) fence = !fence;
      if (!text) text = { type: "text", lines: [] };
      text.lines.push(line);
      i++;
    }
    flush();
    return out;
  }

  // Toast UI writes [[Name]] as \[\[Name\]\]; put the site's own spelling back.
  function clean(md) {
    return md.replace(/\\\[\\\[([^\n]*?)\\\]\\\]/g, "[[$1]]")
             .replace(/\\\[\\\[([^\n]*?)\]\]/g, "[[$1]]")
             .replace(/<br>\s*$/gm, "");
  }

  function assemble(segs) {
    var out = [];
    function blankEnd() { while (out.length && out[out.length - 1].trim() === "") out.pop(); if (out.length) out.push(""); }
    segs.forEach(function (s) {
      if (s.type === "locked") { out.push.apply(out, s.lines); return; }
      if (s.type === "text") {
        if (!s.dirty) {
          if (s.head) out.push(s.head);
          out.push.apply(out, s.lines);
          return;
        }
        var md = clean(s.editor.getMarkdown()).replace(/\s+$/, "").replace(/^\s*\n/, "");
        blankEnd();
        if (s.head) { out.push(s.head); out.push(""); }
        if (md) { out.push.apply(out, md.split("\n")); out.push(""); }
        return;
      }
      var body = assemble(s.children);
      while (body.length && body[0].trim() === "") body.shift();
      if (s.fresh && !body.length) return;              // a new box left empty: not saved
      if (s.fresh) blankEnd();
      out.push(s.head);
      body.forEach(function (l) { out.push(l.trim() === "" ? "" : "    " + l); });
      if (s.fresh) out.push("");
    });
    while (out.length && out[out.length - 1].trim() === "") out.pop();
    return out;
  }

  function lockedLabel(lines) {
    var t = lines.join(" ").trim(), m;
    if (/^<!--\s*players:\s*hide/.test(t)) return "Private from here – not on the players' site";
    if (/^<!--\s*players:\s*end/.test(t)) return "End of the private part";
    if ((m = /^<!--\s*players:\s*show\s*([\s\S]*?)-->$/.exec(t))) return "Players' site only: " + m[1].trim();
    if ((m = /^\{\{\s*(.*?)\s*\}\}$/.exec(t))) return "Filled in by the site: " + m[1];
    return t;
  }

  function visual(page, text, dirty) {
    loadToast(function () {
      text = text.replace(/\r\n/g, "\n");
      var fm = /^---\n[\s\S]*?\n---\n/.exec(text);
      var head = fm ? fm[0] : "";
      var segs = parse((fm ? text.slice(head.length) : text).split("\n"), /^sessions\//.test(page.src));
      var box = frame(page, "Markdown",
        'Type as you would in a document. Grey bars are filled in by the site and stay as they are. ' +
        'A copy of the old version is kept in sources/backups/pages/.');
      var body = box.querySelector(".pe-body");
      body.classList.add("pe-writer");
      var ed = { mode: "visual", page: page, dirty: dirty, active: null, editors: [], texts: [] };
      body.appendChild(toolbar(ed, segs));
      var list = document.createElement("div");
      list.className = "pe-segs";
      body.appendChild(list);
      renderAll(segs, list, ed, null);
      ed.text = function () {
        var lines = assemble(segs);
        if (head && lines.length && lines[0].trim()) lines.unshift("");   // a blank line after the --- block
        return head + lines.join("\n") + "\n";
      };
      ed.destroy = function () { ed.editors.forEach(function (e) { e.destroy(); }); };
      wire(box, ed);
      if (ed.editors[0]) ed.editors[0].focus();
    });
  }

  function renderAll(segs, el, ed, owner) {
    var hasText = segs.some(function (s) { return s.type === "text" && (s.label || s.lines.join("").trim()); });
    if (!hasText) segs.push({ type: "text", lines: [], fresh: true });
    segs.forEach(function (s) {
      s.parent = segs;
      s.owner = owner;
      var node = renderSeg(s, ed);
      if (node) el.appendChild(node);
    });
  }

  function renderSeg(s, ed) {
    if (s.type === "locked") {
      s.el = document.createElement("div");
      s.el.className = "pe-seg-locked";
      s.el.textContent = lockedLabel(s.lines);
      s.el.title = s.lines.join("\n");
      return s.el;
    }
    if (s.type === "box") {
      s.el = document.createElement("section");
      s.el.className = "pe-seg-box pe-kind-" + s.kind;
      s.el.innerHTML = '<div class="pe-seg-box-head"></div><div class="pe-seg-box-body"></div>';
      s.el.firstChild.textContent = s.title + (s.kind === "dm" ? "  ·  private" : "");
      renderAll(s.children, s.el.lastChild, ed, s);
      return s.el;
    }
    if (!s.fresh && !s.label && !s.lines.join("").trim()) return null;   // only blank lines: kept as they are
    var value = s.lines.join("\n").trim();
    // The big writing area: Table notes on a session page; on other pages, the main text (not a box,
    // not just the title).
    var main = s.label ? /notes/i.test(s.label) : !s.owner && !/^#{1,6}\s[^\n]*$/.test(value);
    s.el = document.createElement("div");
    s.el.className = "pe-seg-text" + (main ? " pe-seg-main" : "") + (s.label ? " pe-seg-field" : "") +
      (s.label === "Where we left off" ? " pe-field-group" : "");   // starts the "for next time" part
    var host = s.el;
    if (s.label) {
      var label = document.createElement("div");
      label.className = "pe-field-label";
      label.textContent = s.label;
      s.el.appendChild(label);
      host = document.createElement("div");
      s.el.appendChild(host);
    }
    var ready = false;
    var editor = new toastui.Editor({
      el: host,
      initialValue: value,
      initialEditType: "wysiwyg",
      previewStyle: "tab",
      height: "auto",
      minHeight: main ? "320px" : s.label ? "72px" : "56px",
      hideModeSwitch: true,
      toolbarItems: [],
      usageStatistics: false,
      theme: "dark",
      autofocus: false,
      customHTMLRenderer: { htmlInline: { u: function (node, ctx) {   // underline, saved as <u>…</u>
        return ctx.entering ? { type: "openTag", tagName: "u", attributes: node.attrs } : { type: "closeTag", tagName: "u" };
      } } },
      hooks: { addImageBlobHook: function (blob, callback) {         // pasted or dropped pictures
        uploadImage(blob).then(function (r) { callback(r.url, r.alt); }).catch(function (err) { alert(err.message); });
      } }
    });
    editor.on("change", function () { if (ready) { s.dirty = true; ed.changed(); } });
    editor.on("focus", function () { ed.active = s; });
    setTimeout(function () { ready = true; }, 0);
    s.editor = editor;
    ed.editors.push(editor);
    ed.texts.push(s);
    return s.el;
  }

  function toolbar(ed, segs) {
    var bar = document.createElement("div");
    bar.className = "pe-tools";
    function level(n) { return function (e) { e.exec("heading", { level: n }); }; }
    var items = [
      ["H1", "Page title", level(1), "pe-t-h"],
      ["H2", "Heading", level(2), "pe-t-h"],
      ["H3", "Smaller heading", level(3), "pe-t-h"],
      ["H4", "Smallest heading", level(4), "pe-t-h"],
      ["Text", "Plain text (undo a heading)", level(0)],
      "|",
      ["B", "Bold (Ctrl+B)", function (e) { e.exec("bold"); }, "pe-t-b"],
      ["I", "Italic (Ctrl+I)", function (e) { e.exec("italic"); }, "pe-t-i"],
      ["U", "Underline", underline, "pe-t-u"],
      ["S", "Strike through", function (e) { e.exec("strike"); }, "pe-t-s"],
      "|",
      ["•", "Bulleted list", function (e) { e.exec("bulletList"); }],
      ["1.", "Numbered list", function (e) { e.exec("orderedList"); }],
      ["“", "Quote", function (e) { e.exec("blockQuote"); }],
      ["―", "Separator line", function (e) { e.exec("hr"); }],
      "|",
      ["Link", "Link to a web page", function (e) {
        var url = prompt("Link to (web address):");
        if (url) e.exec("addLink", { linkUrl: url, linkText: e.getSelectedText() || url });
      }],
      ["[[ ]]", "Link a person, place or item by name", function (e) {
        e.insertText("[[" + (e.getSelectedText() || "Name") + "]]");
      }],
      ["Image", "Add a picture (you can also paste or drop one in)", pickImage],
      "|",
      ["+ Private box", "Add a Private theories box (never on the players' site)", function () { addPrivate(ed, segs); }],
      "|",
      ["↶", "Undo", function (e) { e.exec("undo"); }],
      ["↷", "Redo", function (e) { e.exec("redo"); }]
    ];
    items.forEach(function (it) {
      if (it === "|") { bar.appendChild(document.createElement("i")); return; }
      var b = document.createElement("button");
      b.type = "button";
      b.textContent = it[0];
      b.title = it[1];
      if (it[3]) b.className = it[3];
      b.addEventListener("mousedown", function (e) { e.preventDefault(); });   // keep the text's selection
      b.addEventListener("click", function () {
        // The part holding the cursor or selection; else the last one written in; else the first.
        var at = getSelection().anchorNode, host = at && (at.nodeType === 1 ? at : at.parentElement);
        host = host && host.closest(".pe-seg-text");
        var s = ed.texts.filter(function (x) { return x.el === host; })[0] || ed.active || ed.texts[0];
        var e = s && s.editor;
        if (!e) return;
        it[2](e);
        e.focus();
      });
      bar.appendChild(b);
    });
    return bar;
  }

  // Underline on/off for the selected words (Markdown has none of its own: saved as <u>…</u>).
  function underline(e) {
    var view = e.wwEditor && e.wwEditor.view, mark = view && view.state.schema.marks.u;
    if (!mark) return;
    var sel = view.state.selection;
    if (sel.empty) return;
    var tr = view.state.doc.rangeHasMark(sel.from, sel.to, mark)
      ? view.state.tr.removeMark(sel.from, sel.to, mark)
      : view.state.tr.addMark(sel.from, sel.to, mark.create({ htmlAttrs: {}, htmlInline: true }));
    view.dispatch(tr);
  }

  // Pictures go to docs/uploads/ on this computer and are linked from the page.
  function uploadImage(blob) {
    var name = blob.name || "picture";
    return fetch("/__page/upload?src=" + encodeURIComponent(SRC) + "&name=" + encodeURIComponent(name), {
      method: "POST", headers: { "Content-Type": blob.type || "application/octet-stream" }, body: blob
    }).then(function (r) {
      return r.json().then(function (j) { if (!r.ok) throw new Error(j.error || "Couldn't add the picture."); return j; });
    }).catch(function (err) {
      throw new Error(err.message === "Failed to fetch" ? "Adding pictures needs CampaignCodex5e running." : err.message);
    });
  }

  function pickImage(e) {
    var input = document.createElement("input");
    input.type = "file";
    input.accept = "image/png,image/jpeg,image/gif,image/webp";
    input.addEventListener("change", function () {
      var file = input.files && input.files[0];
      if (!file) return;
      uploadImage(file).then(function (r) {
        e.focus();
        e.exec("addImage", { imageUrl: r.url, altText: r.alt });
      }).catch(function (err) { alert(err.message); });
    });
    input.click();
  }

  // A new Private theories box, just after the part being written in (or at the end).
  function addPrivate(ed, segs) {
    var at = ed.active;
    while (at && at.owner) at = at.owner;
    var parent = at ? at.parent : segs;
    var nb = { type: "box", fresh: true, head: '??? dm "Private theories"', kind: "dm", title: "Private theories", children: [] };
    var i = at ? parent.indexOf(at) + 1 : parent.length;
    parent.splice(i, 0, nb);
    var node = renderSeg(nb, ed);
    var list = document.querySelector(".pe-segs");
    if (at && at.el) at.el.insertAdjacentElement("afterend", node);
    else list.appendChild(node);
    nb.parent = parent;
    ed.changed();
    var first = nb.children[0];
    if (first && first.editor) setTimeout(function () { ed.active = first; first.editor.focus(); }, 50);
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
  // Material's instant navigation swaps pages without a reload.
  if (window.document$ && window.document$.subscribe) window.document$.subscribe(init);
})();
