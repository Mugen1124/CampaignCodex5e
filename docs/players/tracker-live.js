/* The players' live initiative tracker (docs/players/tracker.md, player site only).
 * Listens to /api/tracker/ws on the players' worker (publish/players/worker.js), which passes on
 * every change the DM's tracker makes: the order, whose turn it is, the round, and conditions.
 * Reconnects by itself (phones drop connections when the screen locks), and keeps the screen
 * awake while a fight is on and the page is showing. When the DM ends a fight with Victory, a
 * fanfare plays - victory.mp3 next to this page if there is one, otherwise a short one made here.
 * Phones only allow sound after a tap, hence the "Tap for sound" button. */
(function () {
  var box = document.querySelector(".live-tracker");
  if (!box) return;

  var ws = null, retry = 1000, pinger = null, lock = null, fight = null, lastCur = null;
  var sound = false, audio = null, hasFile = false, actx = null;

  // A fight that was on, and has just been won: fanfare. (Joining after the fact doesn't play it.)
  function receive(f) {
    if (f && f.victory && fight && fight.active) fanfare();
    render(f);
  }

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }

  function render(f) {
    fight = f;
    if (!f || !f.active || !(f.list || []).length) {
      var won = f && f.victory && f.updated && Date.now() - f.updated < 10 * 60 * 1000;
      box.innerHTML = (won ? '<p class="lt-victory">Victory!</p>' : "") +
        '<p class="lt-wait">No fight right now. When the DM starts one, it shows up here.</p>' + status();
      keepAwake(false);
      return;
    }
    var cur = f.list.filter(function (x) { return x.cur; })[0];
    box.innerHTML =
      '<div class="lt-head">' +
      (f.started ? '<span class="lt-round">Round ' + f.round + "</span>" +
                   (cur ? '<span class="lt-now">' + esc(cur.name) + "'s turn</span>" : "")
                 : '<span class="lt-now">Rolling initiative…</span>') +
      "</div>" +
      '<ol class="lt-list">' + f.list.map(function (x) {
        return '<li class="lt-row' + (x.pc ? " lt-pc" : "") + (x.cur ? " lt-cur" : "") + (x.out ? " lt-out" : "") + '">' +
          '<span class="lt-init">' + (x.init == null ? "–" : x.init) + "</span>" +
          '<span class="lt-name">' + esc(x.name) + "</span>" +
          '<span class="lt-conds">' +
            (x.conc ? '<span class="lt-chip lt-conc">◆ Concentrating</span>' : "") +
            (x.conds || []).map(function (c) {
              return '<span class="lt-chip">' + esc(c.n) + (c.r != null ? " <i>" + c.r + "</i>" : "") + "</span>";
            }).join("") +
          "</span></li>";
      }).join("") + "</ol>" + status();
    keepAwake(true);
    var now = cur ? cur.name : null;
    if (now && now !== lastCur) {
      var row = box.querySelector(".lt-cur");
      if (row && row.scrollIntoView) row.scrollIntoView({ block: "nearest", behavior: "smooth" });
    }
    lastCur = now;
  }

  function status() {
    var live = ws && ws.readyState === 1;
    return '<p class="lt-status' + (live ? " lt-live" : "") + '">' + (live ? "● Live" : "○ Reconnecting…") +
      ' <button class="lt-sound" type="button">' + (sound ? "🔊 Sound on" : "🔈 Tap for sound") + "</button></p>";
  }

  function connect() {
    if (ws && (ws.readyState === 0 || ws.readyState === 1)) return;
    try {
      ws = new WebSocket((location.protocol === "https:" ? "wss://" : "ws://") + location.host + "/api/tracker/ws");
    } catch (e) { return later(); }
    ws.onopen = function () {
      retry = 1000;
      clearInterval(pinger);
      pinger = setInterval(function () { if (ws.readyState === 1) ws.send("ping"); }, 25000);
    };
    ws.onmessage = function (ev) {
      if (ev.data === "pong") return;
      try { receive(JSON.parse(ev.data)); } catch (e) {}
    };
    ws.onclose = function () {
      clearInterval(pinger);
      render(fight);
      later();
    };
  }
  function later() {
    // Meanwhile, fetch the fight once so a flaky connection still shows the latest.
    fetch("/api/tracker", { cache: "no-store" }).then(function (r) { return r.ok ? r.json() : null; })
      .then(function (f) { if (f) receive(f); }).catch(function () {});
    setTimeout(connect, retry);
    retry = Math.min(retry * 2, 15000);
  }

  // Keep the screen on while a fight is showing (where the browser allows it).
  function keepAwake(on) {
    if (!("wakeLock" in navigator)) return;
    if (on && !lock && document.visibilityState === "visible") {
      navigator.wakeLock.request("screen").then(function (l) {
        lock = l;
        l.addEventListener("release", function () { lock = null; });
      }).catch(function () {});
    } else if (!on && lock) {
      lock.release().catch(function () {});
      lock = null;
    }
  }
  // Sound: switched on by a tap (the only way phones allow it), which also readies the player.
  box.addEventListener("click", function (ev) {
    if (!ev.target.classList.contains("lt-sound")) return;
    sound = !sound;
    if (sound) {
      var Ctx = window.AudioContext || window.webkitAudioContext;
      if (Ctx && !actx) actx = new Ctx();
      if (actx && actx.resume) actx.resume();
      audio = new Audio("victory.mp3");
      audio.muted = true;
      audio.play().then(function () { audio.pause(); audio.currentTime = 0; audio.muted = false; hasFile = true; })
        .catch(function () { hasFile = false; });
      chime();
    }
    render(fight);
  });
  function fanfare() {
    if (!sound) return;
    if (hasFile && audio) {
      audio.currentTime = 0;
      audio.play().catch(synthFanfare);
    } else synthFanfare();
  }
  // Tones: [frequency, start, length] in seconds, played as a soft brass-like voice.
  function play(notes, level) {
    if (!actx) return;
    var t0 = actx.currentTime + 0.05;
    notes.forEach(function (n) {
      var g = actx.createGain(), lp = actx.createBiquadFilter();
      lp.type = "lowpass"; lp.frequency.value = 2200;
      g.gain.setValueAtTime(0.0001, t0 + n[1]);
      g.gain.exponentialRampToValueAtTime(level, t0 + n[1] + 0.02);
      g.gain.exponentialRampToValueAtTime(0.0001, t0 + n[1] + n[2]);
      lp.connect(g); g.connect(actx.destination);
      [-6, 6].forEach(function (cents) {
        var o = actx.createOscillator();
        o.type = "sawtooth"; o.frequency.value = n[0]; o.detune.value = cents;
        o.connect(lp); o.start(t0 + n[1]); o.stop(t0 + n[1] + n[2] + 0.05);
      });
    });
  }
  function chime() { play([[784, 0, 0.18]], 0.06); }   // confirms sound is on
  function synthFanfare() {   // an original little fanfare: a rising call, then a held major chord
    play([[392, 0, 0.16], [523.25, 0.15, 0.16], [659.25, 0.30, 0.16], [783.99, 0.45, 0.32],
          [659.25, 0.78, 0.14], [783.99, 0.93, 0.2],
          [523.25, 1.15, 1.5], [659.25, 1.15, 1.5], [783.99, 1.15, 1.5], [1046.5, 1.15, 1.5]], 0.07);
  }

  document.addEventListener("visibilitychange", function () {
    if (document.visibilityState !== "visible") return;
    retry = 1000;
    connect();
    if (fight && fight.active) keepAwake(true);
  });

  connect();
})();
