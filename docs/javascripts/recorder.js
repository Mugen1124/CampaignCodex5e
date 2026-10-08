/* Record & Transcribe page: records the table from a microphone into a file, and starts
   transcriptions. The browser records; every few seconds the audio so far goes to the local save
   helper (tools/site_helper.py), which adds it to the file on disk - so a crash or a closed tab
   loses seconds, not the session. Transcribing runs tools/transcribe.py in the background.
   Works on the site at home or on the laptop at the table (serve); the online copy only
   explains that.

   Pop out: the recorder can run in its own small window (recording.html?popout), so the main
   window can move around the site - leaving a page would otherwise stop its recording. The
   recorder says how it's doing every second on a BroadcastChannel; every other page of the site
   shows that as a "REC" light in its header (click it to bring the recorder forward), and keeps
   the screen awake while it's visible. Only one window records at a time. */
(function () {
  "use strict";
  var HELPER = "http://127.0.0.1:8765";
  // Which campaign this page belongs to (hooks/campaign.py puts it in every page), so saved state
  // stays separate when two campaigns are served on one computer.
  var CAMPAIGN = (document.querySelector('meta[name="codex-campaign"]') || {}).content || "codex";
  var STORE = CAMPAIGN + "-recorder";
  var CHUNK_MS = 5000;
  var ONLINE = location.protocol !== "file:" && !/^(127\.0\.0\.1|localhost|\[::1\])$/.test(location.hostname);
  var OFFLINE = "The save helper isn't running (it starts with <code>serve</code>).";
  var WINDOW_NAME = CAMPAIGN + "-recorder";
  var POPOUT = /[?&]popout\b/.test(location.search);
  var bc = window.BroadcastChannel ? new BroadcastChannel(CAMPAIGN + "-recorder") : null;
  var BUSY = { recording: 1, paused: 1, failing: 1 };

  function recorderUrl() {
    return new URL("recording.html?popout", window.__md_scope || new URL(".", location)).href;
  }
  // Bring the recorder window forward - or open it. (Opening it by its URL when it's already open
  // would reload it and end its recording, so first ask for the window by name without a URL.)
  function openRecorder() {
    var w = window.open("", WINDOW_NAME, "popup,width=600,height=470");
    if (!w) { window.alert("The browser blocked the recorder window - allow pop-ups for this site, then try again."); return; }
    try { if (w.location.href === "about:blank") w.location.href = recorderUrl(); } catch (e) {}
    w.focus();
  }

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }
  function clock(ms) {
    var s = Math.floor(ms / 1000);
    return [Math.floor(s / 3600), Math.floor(s % 3600 / 60), s % 60].map(function (n) { return n < 10 ? "0" + n : n; }).join(":");
  }
  function mb(bytes) { return bytes < 1048576 ? Math.max(1, Math.round(bytes / 1024)) + " KB" : (bytes / 1048576).toFixed(1) + " MB"; }

  function init() {
    var root = document.getElementById("rec-root");
    if (!root) return;
    if (ONLINE) {
      root.innerHTML = '<div class="eb-msg eb-info">Recording works on the site at home or on the laptop at the table ' +
        "(<code>serve</code>), not on the online copy.</div>";
      return;
    }
    if (!navigator.mediaDevices || !window.MediaRecorder) {
      root.innerHTML = '<div class="eb-msg eb-warn">This browser can\'t record here. Open the site with <code>serve</code> ' +
        "(http://127.0.0.1:8000) in Chrome or Edge.</div>";
      return;
    }
    var prefs = {};
    try { prefs = JSON.parse(localStorage.getItem(STORE) || "{}"); } catch (e) {}
    function savePrefs() { try { localStorage.setItem(STORE, JSON.stringify(prefs)); } catch (e) {} }
    if (POPOUT) {   // just the recorder: styles hide the site around it (html.rec-popout)
      document.documentElement.classList.add("rec-popout");
      window.name = WINDOW_NAME;
    }

    root.innerHTML =
      '<div class="rec-panel">' +
      ' <div class="rec-grid">' +
      '  <label>Microphone</label><div class="rec-line"><select class="rec-dev"><option value="">(allow the microphone to choose)</option></select>' +
      '   <button class="eb-act rec-allow">Allow microphone</button></div>' +
      '  <label>Level</label><div class="rec-line"><div class="rec-meter"><div class="rec-meter-fill"></div></div><span class="rec-level-note"></span></div>' +
      '  <label>Save to</label><div class="rec-line"><input class="rec-folder" readonly><button class="eb-act rec-browse">Browse…</button>' +
      '   <button class="eb-act rec-default" title="The recordings folder next to campaign-site">Default</button></div>' +
      " </div>" +
      ' <div class="rec-controls">' +
      '  <button class="md-button md-button--primary rec-start">● Record</button>' +
      '  <button class="md-button rec-pause" hidden>Pause</button>' +
      '  <button class="md-button rec-stop" hidden>■ Stop</button>' +
      '  <span class="rec-clock">00:00:00</span><span class="rec-state"></span>' +
      (POPOUT ? "" : '  <button class="md-button rec-popout-btn" title="Record in a small window of its own, so this one can go anywhere on the site">⧉ Pop out</button>') +
      " </div>" +
      ' <div class="rec-status"></div><div class="rec-silence"></div><div class="rec-elsewhere"></div>' +
      (POPOUT
        ? ' <p class="eb-hint">Ask the table before recording. Keep this window open (park it in a corner) - closing it stops the recording. ' +
          "Use the main window for the rest of the site; its REC light brings this window back.</p>"
        : ' <p class="eb-hint">Ask the table before recording. Leaving this page stops a recording made here - use <b>Pop out</b> to record ' +
          "in a small window of its own and keep using the site. The audio is saved every few seconds, so a crash loses seconds, not the session.</p>") +
      "</div>" +
      '<div class="rec-list-title">Recordings</div>' +
      '<div class="rec-list"><p class="eb-hint">Loading…</p></div>';
    function $(sel) { return root.querySelector(sel); }

    function status(html, kind) { $(".rec-status").innerHTML = html ? '<div class="eb-msg eb-' + (kind || "info") + '">' + html + "</div>" : ""; }
    function call(path, body, raw) {
      var opts = raw ? { method: "POST", headers: { "Content-Type": "application/octet-stream" }, body: raw }
        : body ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) } : {};
      return fetch(HELPER + path, opts).then(function (r) {
        return r.json().then(function (j) { return { status: r.status, body: j }; });
      });
    }

    // ------------------------------------------------------------ microphone and level meter
    var stream = null, audioCtx = null, meterTimer = null, lastSound = Date.now(), warnedSilent = false;
    var CONSTRAINTS = { echoCancellation: false, noiseSuppression: false, autoGainControl: false, channelCount: 1 };

    function listDevices() {
      return navigator.mediaDevices.enumerateDevices().then(function (all) {
        var mics = all.filter(function (d) { return d.kind === "audioinput"; });
        var named = mics.some(function (d) { return d.label; });
        $(".rec-allow").hidden = named;
        if (!named) return false;
        $(".rec-dev").innerHTML = mics.map(function (d) {
          return '<option value="' + esc(d.deviceId) + '">' + esc(d.label || "Microphone") + "</option>";
        }).join("");
        var wanted = mics.filter(function (d) { return d.deviceId === prefs.deviceId; })[0] || mics[0];   // last used, or the default
        if (wanted) $(".rec-dev").value = wanted.deviceId;
        return true;
      });
    }
    function openMic() {
      var id = $(".rec-dev").value;
      var audio = Object.assign({}, CONSTRAINTS, id ? { deviceId: { exact: id } } : {});
      if (stream) stream.getTracks().forEach(function (t) { t.stop(); });
      return navigator.mediaDevices.getUserMedia({ audio: audio }).then(function (s) {
        stream = s;
        prefs.deviceId = id; savePrefs();
        startMeter();
      });
    }
    function startMeter() {
      if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      if (audioCtx.state === "suspended") audioCtx.resume();
      var analyser = audioCtx.createAnalyser();
      analyser.fftSize = 2048;
      audioCtx.createMediaStreamSource(stream).connect(analyser);
      var buf = new Float32Array(analyser.fftSize), fill = $(".rec-meter-fill"), note = $(".rec-level-note"), peakHold = 0;
      clearInterval(meterTimer);
      meterTimer = setInterval(function () {
        analyser.getFloatTimeDomainData(buf);
        var sum = 0, peak = 0;
        for (var i = 0; i < buf.length; i++) { sum += buf[i] * buf[i]; peak = Math.max(peak, Math.abs(buf[i])); }
        var rms = Math.sqrt(sum / buf.length), level = Math.min(1, rms * 4);
        fill.style.width = (level * 100).toFixed(0) + "%";
        peakHold = Math.max(peak, peakHold * 0.97);
        fill.className = "rec-meter-fill" + (peakHold > 0.97 ? " rec-hot" : "");
        note.textContent = peakHold > 0.97 ? "Too loud - turn the mic's gain down" : level < 0.02 ? "Quiet" : "";
        // A minute of silence while recording usually means the mic is unplugged, muted, or not the one chosen.
        if (level >= 0.02) lastSound = Date.now();
        var silent = rec && !pausedAt && Date.now() - lastSound > 60000;
        if (silent !== warnedSilent) {
          warnedSilent = silent;
          $(".rec-silence").innerHTML = silent ? '<div class="eb-msg eb-warn">No sound picked up for over a minute - ' +
            "check the microphone is plugged in, unmuted, and the one chosen above. Still recording.</div>" : "";
        }
      }, 100);
    }
    function allow() {
      return navigator.mediaDevices.getUserMedia({ audio: CONSTRAINTS }).then(function (s) {
        s.getTracks().forEach(function (t) { t.stop(); });
        return listDevices();
      }).then(function (ok) { if (ok) return openMic(); })
        .catch(function (e) { status("The microphone wasn't allowed (" + esc(e.name) + "). Allow it in the browser's address bar, then try again.", "warn"); });
    }

    // ------------------------------------------------------------ save folder and recordings list
    var job = null, pollTimer = null;
    function refresh() {
      return call("/recordings?folder=" + encodeURIComponent(prefs.folder || "")).then(function (res) {
        var d = res.body;
        $(".rec-folder").value = d.folder;
        if (prefs.folder && !d.found) status("The folder " + esc(prefs.folder) + " isn't there any more - using the default.", "warn");
        job = d.job && d.job.file ? d.job : null;
        renderList(d.files);
        clearTimeout(pollTimer);
        if (job && job.running) pollTimer = setTimeout(refresh, 5000);
      }).catch(function () {
        $(".rec-list").innerHTML = '<div class="eb-msg eb-warn">' + OFFLINE + "</div>";
      });
    }
    function renderList(files) {
      if (!files.length) {
        $(".rec-list").innerHTML = '<p class="eb-hint">No recordings in this folder yet.</p>';
        return;
      }
      $(".rec-list").innerHTML = files.map(function (f) {
        var mine = job && job.file === f.path, state;
        if (f.recording) state = '<span class="rec-tag rec-live">Recording…</span>';
        else if (mine && job.running) state = '<span class="rec-tag">Transcribing</span> <span class="eb-meta">' + esc(job.progress.replace(/^\s*/, "") || "starting…") + "</span>";
        else if (mine && job.error) state = '<span class="rec-tag rec-bad">Transcription failed</span> <span class="eb-meta">' + esc(job.error) + "</span>";
        else if (f.transcript) state = '<span class="rec-tag rec-ok">Transcript ready</span> <span class="eb-meta">' + esc(f.name.replace(/\.[^.]+$/, "")) + ".transcript.txt</span>";
        else state = '<button class="eb-act rec-tx" data-file="' + esc(f.path) + '">Transcribe</button>';
        return '<div class="rec-item"><span class="rec-name">' + esc(f.name) + '</span><span class="eb-meta">' + esc(f.modified) +
          " · " + mb(f.bytes) + '</span><span class="rec-what">' + state + "</span></div>";
      }).join("");
    }
    function browse() {
      status("A folder picker is open on this computer - it may be behind the browser window.", "info");
      call("/folder/browse", { start: $(".rec-folder").value }).then(function (res) {
        status("");
        if (res.status !== 200) return status(esc(res.body.error), "warn");
        if (res.body.folder) { prefs.folder = res.body.folder; savePrefs(); refresh(); }
      }).catch(function () { status(OFFLINE, "warn"); });
    }

    // ------------------------------------------------------------ recording
    var rec = null, current = null, queue = [], sending = false, failingSince = 0;
    var startedAt = 0, pausedTotal = 0, pausedAt = 0, tick = null, wakeLock = null, saved = 0;

    function pump() {
      if (sending || !queue.length || !current) return;
      sending = true;
      call("/recording/chunk?id=" + encodeURIComponent(current.id) + "&file=" + encodeURIComponent(current.file), null, queue[0])
        .then(function (res) {
          sending = false;
          if (res.status !== 200) throw new Error(res.body.error || "not saved");
          queue.shift();
          saved = res.body.bytes;
          if (failingSince) { failingSince = 0; status("Saving again - nothing was lost.", "ok"); }
          pump();
        })
        .catch(function () {
          sending = false;
          if (!failingSince) failingSince = Date.now();
          status("Not saving since " + clock(elapsed() - (Date.now() - failingSince)) + " - " + OFFLINE +
            " The audio is kept here and saved as soon as it's back. Don't close this page.", "warn");
          setTimeout(pump, 3000);
        });
    }
    function elapsed() { return rec ? (pausedAt || Date.now()) - startedAt - pausedTotal : 0; }
    function showTime() {
      $(".rec-clock").textContent = clock(elapsed());
      $(".rec-state").textContent = !rec ? "" : pausedAt ? "Paused" : "Recording" + (saved ? " · " + mb(saved) + " saved" : "");
    }
    function keepAwake() {
      if (!navigator.wakeLock || !rec) return;
      navigator.wakeLock.request("screen").then(function (l) { wakeLock = l; }).catch(function () {});
    }
    document.addEventListener("visibilitychange", function () { if (document.visibilityState === "visible" && rec) keepAwake(); });
    window.addEventListener("beforeunload", function (ev) {
      if (rec || queue.length) { ev.preventDefault(); ev.returnValue = "A recording is in progress."; }
    });

    function start() {
      if (!stream) return status("Choose a microphone first (Allow microphone).", "warn");
      var type = ["audio/webm;codecs=opus", "audio/webm"].filter(function (t) { return MediaRecorder.isTypeSupported(t); })[0];
      if (!type) return status("This browser can't record in the format the transcriber reads - use Chrome or Edge.", "warn");
      call("/recording/start", { folder: prefs.folder || "" }).then(function (res) {
        if (res.status !== 200) return status(esc(res.body.error || "Couldn't start the file."), "warn");
        current = { id: res.body.id, file: res.body.file, name: res.body.name };
        queue = []; saved = 0; failingSince = 0;
        rec = new MediaRecorder(stream, { mimeType: type, audioBitsPerSecond: 64000 });
        rec.ondataavailable = function (e) { if (e.data && e.data.size) { queue.push(e.data); pump(); } };
        rec.onstop = finish;
        rec.start(CHUNK_MS);
        startedAt = Date.now(); pausedTotal = 0; pausedAt = 0; lastSound = Date.now();
        tick = setInterval(showTime, 500);
        keepAwake();
        setButtons();
        $(".rec-dev").disabled = true; $(".rec-browse").disabled = true; $(".rec-default").disabled = true;
        status("Recording to <code>" + esc(current.file) + "</code>", "ok");
        refresh();
      }).catch(function () { status(OFFLINE + " Recording needs it to save the file.", "warn"); });
    }
    function pause() {
      if (!rec) return;
      if (pausedAt) { rec.resume(); pausedTotal += Date.now() - pausedAt; pausedAt = 0; lastSound = Date.now(); }
      else { rec.pause(); pausedAt = Date.now(); }
      setButtons(); showTime();
    }
    function stop() {
      if (!rec || !window.confirm("Stop recording? (Pause keeps the same file going.)")) return;
      if (pausedAt) { pausedTotal += Date.now() - pausedAt; pausedAt = 0; }
      rec.stop();   // the last chunk arrives, then finish()
    }
    function finish() {
      clearInterval(tick);
      $(".rec-state").textContent = "Saving the last of it…";
      var wait = setInterval(function () {
        if (queue.length || sending) return;
        clearInterval(wait);
        call("/recording/stop", { id: current.id }).catch(function () {}).then(function () {
          status("Saved <code>" + esc(current.name) + "</code> (" + mb(saved) + ", " + clock(elapsed()) + ").", "ok");
          rec = null; current = null;
          if (wakeLock) { wakeLock.release().catch(function () {}); wakeLock = null; }
          $(".rec-dev").disabled = false; $(".rec-browse").disabled = false; $(".rec-default").disabled = false;
          setButtons(); showTime(); refresh();
        });
      }, 300);
    }
    function setButtons() {
      $(".rec-start").hidden = !!rec;
      $(".rec-pause").hidden = !rec; $(".rec-stop").hidden = !rec;
      $(".rec-pause").textContent = pausedAt ? "Resume" : "Pause";
    }

    // ------------------------------------------------------------ wiring
    $(".rec-allow").addEventListener("click", allow);
    $(".rec-dev").addEventListener("change", function () { openMic().catch(function (e) { status("Couldn't open that microphone (" + esc(e.name) + ").", "warn"); }); });
    $(".rec-browse").addEventListener("click", browse);
    $(".rec-default").addEventListener("click", function () { delete prefs.folder; savePrefs(); status(""); refresh(); });
    $(".rec-start").addEventListener("click", start);
    $(".rec-pause").addEventListener("click", pause);
    $(".rec-stop").addEventListener("click", stop);
    $(".rec-list").addEventListener("click", function (ev) {
      var file = ev.target.getAttribute("data-file");
      if (!file) return;
      call("/transcribe", { file: file }).then(function (res) {
        if (res.status !== 200) return status(esc(res.body.error), "warn");
        status("Transcribing in the background - you can leave this page; the transcript appears next to the recording.", "info");
        refresh();
      }).catch(function () { status(OFFLINE, "warn"); });
    });

    // ------------------------------------------------------------ other windows (pop out, REC light, one at a time)
    var otherBusyAt = 0;
    function recState() { return !rec ? "idle" : failingSince ? "failing" : pausedAt ? "paused" : "recording"; }
    if (bc) bc.addEventListener("message", function (ev) {
      var d = ev.data || {};
      if (BUSY[d.state]) otherBusyAt = Date.now();
      else if (d.state === "closed") otherBusyAt = 0;
    });
    var beat = 0;
    setInterval(function () {
      if (bc) bc.postMessage({ state: recState(), elapsed: elapsed(), name: current ? current.name : "",
                               file: current ? current.file : "" });   // the tracker's turn log is saved next to it
      // Paused, no audio goes to the helper - so every 10 s an empty piece says the recording is
      // still going (it treats one that's gone quiet for 30 s as finished).
      if (rec && pausedAt && ++beat % 10 === 0 && !queue.length && !sending) {
        call("/recording/chunk?id=" + encodeURIComponent(current.id) + "&file=" + encodeURIComponent(current.file), null, new Blob([])).catch(function () {});
      }
      var elsewhere = !rec && Date.now() - otherBusyAt < 4000;   // another window is recording
      $(".rec-start").disabled = elsewhere;
      $(".rec-elsewhere").innerHTML = elsewhere ? '<div class="eb-msg eb-info">Recording in another window' +
        (POPOUT ? "" : ' - <a class="rec-bring">bring it forward</a>') + ".</div>" : "";
      if (!POPOUT) $(".rec-popout-btn").disabled = !!rec || elsewhere;
      if (POPOUT) document.title = rec ? (pausedAt ? "❚❚ " : "● ") + clock(elapsed()) + " · Recorder" : "Recorder";
    }, 1000);
    window.addEventListener("pagehide", function () { if (bc && rec) bc.postMessage({ state: "closed" }); });
    if (!POPOUT) $(".rec-popout-btn").addEventListener("click", openRecorder);
    root.addEventListener("click", function (ev) { if (ev.target.classList.contains("rec-bring")) openRecorder(); });

    listDevices().then(function (ok) { if (ok) return openMic(); }).catch(function () {});
    refresh();
  }

  // ------------------------------------------------------------ REC light (every other page's header)
  function initLight() {
    if (POPOUT || !bc || ONLINE) return;
    var header = document.querySelector(".md-header__inner");
    if (!header) return;
    var light = document.createElement("button");
    light.type = "button";
    light.className = "rec-light";
    light.hidden = true;
    light.title = "Session recording - click to bring the recorder window forward";
    header.insertBefore(light, header.querySelector(".md-search") || null);
    var last = null, lastAt = 0, wake = null;
    bc.addEventListener("message", function (ev) {
      if (ev.data && ev.data.state) { last = ev.data; lastAt = Date.now(); render(); }
    });
    function render() {
      var lost = last && (last.state === "closed" || (BUSY[last.state] && Date.now() - lastAt > 5000));
      var show = !!last && (BUSY[last.state] || last.state === "closed");
      light.hidden = !show;
      if (!show) return release();
      var cls = "rec-light", text;
      if (lost) { cls += " rec-light-lost"; text = "● REC · recorder closed?"; }
      else {
        var t = clock(last.elapsed + (last.state === "recording" ? Date.now() - lastAt : 0));
        if (last.state === "failing") { cls += " rec-light-warn"; text = "● REC " + t + " · not saving"; }
        else if (last.state === "paused") { cls += " rec-light-paused"; text = "❚❚ PAUSED " + t; }
        else text = "● REC " + t;
      }
      light.className = cls;
      light.textContent = text;
      // While a recording runs, any visible page of the site keeps the screen (and laptop) awake,
      // even if the recorder window itself is minimized.
      if (!lost && document.visibilityState === "visible") hold(); else release();
    }
    function hold() {
      if (wake || !navigator.wakeLock) return;
      wake = "asking";
      navigator.wakeLock.request("screen").then(function (l) {
        wake = l;
        l.addEventListener("release", function () { wake = null; });
      }).catch(function () { wake = null; });
    }
    function release() {
      if (wake && wake.release) wake.release().catch(function () {});
      if (wake !== "asking") wake = null;
    }
    document.addEventListener("visibilitychange", render);
    setInterval(render, 1000);
    light.addEventListener("click", function () {
      if (last && last.state === "closed") { last = null; render(); }   // seen - put the light out
      openRecorder();
    });
  }

  function start() { init(); initLight(); }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start);
  else start();
})();
