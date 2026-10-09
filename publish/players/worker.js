// The players' site: the built pages (./site), plus the live initiative tracker, the live Party page, item claims, and notes.
//
//   GET  /api/tracker            -> the fight as the players see it (JSON)
//   GET  /api/tracker/ws         -> the same, live: a WebSocket that gets every change
//   POST /api/tracker            -> the DM's tracker, via the save helper (tools/site_helper.py)
//
//   GET  /api/me                 -> the signed-in player's character: {character, index, id, level}
//
//   GET  /api/items/claims       -> who has asked for which up-for-grabs item (the helper also gets ids and emails)
//   POST /api/items/claim        -> {"item"} claim it for your character; {"item", "withdraw": true} take that back
//   POST /api/items/resolve      -> the DM's helper: {"id", "status": "approved" | "rejected"}
//
//   GET  /api/party              -> the Party page live: {me: your card's id, cards: [...]} - other players'
//                                   cards without their private parts; the DM's helper gets everything
//   GET  /api/party/ws           -> a WebSocket that says "changed" whenever a card changes
//   POST /api/party/import       -> {"file": a .ccc5e's text, "save": false} the preview; with "save": true and
//                                   "rev", onto your own card (portrait shrunk by the page first)
//   POST /api/party/save         -> {"card": {...fields}, "rev"} your own card, edited on the page
//   POST /api/party/status       -> {"hp" | "hp_delta" | "temp" | "conds" | "insp" | "slots" | "hd" | "death"} your card's
//                                   live status (see party.applyStatus); the DM's helper: {"cards": [{"id", ...}]}
//   POST /api/party/treasury     -> {"coins": {gp: +10}, "add" | "take": {name, qty}, "note"} the party's shared pool
//   POST /api/party/settings     -> the DM's helper: {"show_hp": true} whether players see each other's current HP
//   POST /api/party/private      -> {"private": [fields], "hidden": [item names], "rev"} what only you (and the DM) see
//   GET  /api/party/portrait/ID  -> an uploaded portrait
//   GET  /api/party/all          -> the DM's helper: every card in full, with its rev (to bring into party.yml)
//   GET  /api/party/history?id=  -> the DM's helper: a card's changes, newest first
//   POST /api/party/undo         -> the DM's helper: {"id", "key"} put a card back as it was before that change
//
//   GET  /api/notes              -> the signed-in player's own notes: {"text", "rev", "saved"}
//   PUT  /api/notes              -> {"text", "rev"} save them; rev is the version they were loaded at, and a
//                                   newer one already saved (from another device) answers 409 with that version
//
// Cloudflare Access sits in front of all of it, so every request here is already signed in; the
// signed Access token says who (a player's email, or the helper's service token). Which email plays
// which character comes from roster.json, written by the publish script from data/party.yml - it's part of
// this script, never one of the site's files. The helper's calls (POST tracker, the DM's Party calls, resolve)
// are refused for players. Notes are private to the player who wrote them: each email has its own
// store, nothing else reads it, and the helper's service token can't reach it - not even the DM sees them.
import { DurableObject } from "cloudflare:workers";
import ROSTER from "./roster.json";
import * as ccc5e from "./ccc5e.mjs";
import * as party from "./party.mjs";

// Your Cloudflare Access team address (https://<team>.cloudflareaccess.com). The publish script writes
// it into wrangler.jsonc as ACCESS_TEAM from campaign.yml (online: access_team:).
const team = (env) => String(env.ACCESS_TEAM || "").replace(/\/+$/, "");

const NOTE_MAX = 100000;   // bytes of notes per player (a Durable Object value holds up to 128 KiB)

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const path = url.pathname;
    if (path === "/api/tracker" || path === "/api/tracker/ws") {
      if (request.method === "POST" && !(await isHelper(request, env))) {
        return json({ error: "Only the DM's tracker can change the fight." }, 403);
      }
      if (request.method !== "GET" && request.method !== "POST") return json({ error: "Not allowed." }, 405);
      return env.TRACKER.get(env.TRACKER.idFromName("live")).fetch(request);
    }
    if (path === "/api/me") return whoAmI(request, env);
    if (path.startsWith("/api/items/")) return claims(request, env, path);
    if (path === "/api/notes") return notes(request, env);
    if (path === "/api/party" || path.startsWith("/api/party/")) return partyApi(request, env, path);
    return env.ASSETS.fetch(request);
  },
};

async function whoAmI(request, env) {
  const who = await identity(request, env);
  if (!who) return json({ error: "Not signed in." }, 401);
  const me = who.service ? null : playerFor(who.email);
  if (!me) return json({ character: null });
  return json({ character: me.character, index: me.index, id: me.id || party.cardId(me.character), level: ROSTER.level || null });
}

async function claims(request, env, path) {
  const store = env.CARDS.get(env.CARDS.idFromName("cards"));
  const who = await identity(request, env);
  if (!who) return json({ error: "Not signed in." }, 401);
  if (path === "/api/items/claims" && request.method === "GET") {
    return store.fetch("https://cards/claims" + (who.service ? "?all=1" : ""));
  }
  if (path === "/api/items/resolve" && request.method === "POST") {
    if (!who.service) return json({ error: "Only the DM can do that." }, 403);
    return store.fetch(new Request("https://cards/claim-resolve", request));
  }
  if (path === "/api/items/claim" && request.method === "POST") {
    const me = playerFor(who.email);
    if (!me) return json({ error: "Your email isn't linked to a character yet - ask the DM." }, 403);
    let body;
    try { body = await request.json(); } catch (e) { return json({ error: "Couldn't read that." }, 400); }
    const item = (ROSTER.grabs || []).find((i) => i.id === String((body && body.item) || ""));
    if (!item) return json({ error: "That item isn't up for grabs any more." }, 404);
    return store.fetch("https://cards/claim", {
      method: "POST", body: JSON.stringify({ item: item.id, character: me.character, email: who.email, withdraw: !!body.withdraw }),
    });
  }
  return json({ error: "Not found." }, 404);
}

// A player's own notes. Any signed-in email may keep notes (linked to a character or not); the
// helper's service token has no email, so it never gets in.
async function notes(request, env) {
  const who = await identity(request, env);
  if (!who) return json({ error: "Not signed in." }, 401);
  if (!who.email) return json({ error: "Notes belong to a signed-in player." }, 403);
  const store = env.NOTES.get(env.NOTES.idFromName(who.email));
  if (request.method === "GET") return store.fetch("https://notes/");
  if (request.method === "PUT") {
    let body;
    try { body = await request.json(); } catch (e) { return json({ error: "Couldn't read your notes." }, 400); }
    const text = String((body && body.text) == null ? "" : body.text);
    if (new TextEncoder().encode(text).length > NOTE_MAX) {
      return json({ error: "Your notes are too long to save - about 100,000 characters is the most." }, 413);
    }
    return store.fetch("https://notes/", { method: "PUT", body: JSON.stringify({ text, rev: Number(body.rev) || 0 }) });
  }
  return json({ error: "Not allowed." }, 405);
}

function playerFor(email) {
  if (!email) return null;
  return (ROSTER.members || []).find((m) => m.email && m.email === String(email).toLowerCase()) || null;
}

// Item claims. (It once also held card suggestions, which the live Party page replaced; any left are never read.)
export class Cards extends DurableObject {
  async fetch(request) {
    const url = new URL(request.url);
    const what = url.pathname.slice(1);
    if (what === "claim") {   // one claim per item and character
      const c = await request.json();
      const key = "claim:" + c.item + ":" + c.character;
      const had = await this.ctx.storage.get(key);
      if (c.withdraw) {
        if (had && had.status === "pending") await this.ctx.storage.delete(key);
        return json({ ok: true, status: "withdrawn" });
      }
      if (had && had.status === "pending") return json({ ok: true, status: "pending" });
      await this.ctx.storage.put(key, { id: crypto.randomUUID(), item: c.item, character: c.character, email: c.email,
                                        at: Date.now(), status: "pending" });
      return json({ ok: true, status: "pending" });
    }
    if (what === "claims" || what === "claim-resolve") {
      const claims = [...(await this.ctx.storage.list({ prefix: "claim:" })).values()];
      if (what === "claims") {
        const recent = claims.filter((c) => c.status === "pending" || Date.now() - (c.decided || 0) < 14 * 86400000);
        return json({ claims: url.searchParams.get("all") ? recent
          : recent.map((c) => ({ item: c.item, character: c.character, status: c.status })) });
      }
      const r = await request.json();
      const c = claims.find((x) => x.id === r.id);
      if (!c || !["approved", "rejected"].includes(r.status)) return json({ error: "No such claim." }, 404);
      c.status = r.status;
      c.decided = Date.now();
      await this.ctx.storage.put("claim:" + c.item + ":" + c.character, c);
      return json({ ok: true });
    }
    return json({ error: "Not found." }, 404);
  }
}

// One player's notes: one of these per email (idFromName), holding a single notepad.
export class Notes extends DurableObject {
  async fetch(request) {
    const cur = (await this.ctx.storage.get("note")) || { text: "", rev: 0, saved: null };
    if (request.method === "PUT") {
      const n = await request.json();
      if (n.rev !== cur.rev) return json(Object.assign({ error: "Changed on another device." }, cur), 409);
      const next = { text: n.text, rev: cur.rev + 1, saved: new Date().toISOString() };
      await this.ctx.storage.put("note", next);
      return json(next);
    }
    return json(cur);
  }
}

// ---------------------------------------------------------------- the live Party page
// One Party store for the campaign. The worker tells it who's asking (a header it sets itself - the
// store is only reachable through here): the DM's helper, a player and their card's id, or nobody.
async function partyApi(request, env, path) {
  const who = await identity(request, env);
  if (!who) return json({ error: "Not signed in." }, 401);
  const me = who.service ? null : playerFor(who.email);
  const viewer = who.service ? { dm: true } : { email: who.email, id: me ? me.id || party.cardId(me.character) : null,
                                               name: me ? me.character : null };
  const url = new URL(request.url);
  // The body read here in full, so a request refused before it's read can't leave the stream hanging.
  const headers = new Headers(request.headers);
  headers.set("X-Viewer", JSON.stringify(viewer));
  const inner = new Request("https://party" + path + url.search, {
    method: request.method, headers,
    body: request.method === "POST" ? await request.text() : undefined,
  });
  return env.PARTY.get(env.PARTY.idFromName("party")).fetch(inner);
}

const HISTORY_KEPT = 30;
const PORTRAIT_MAX = 200000;   // characters of base64 - the page shrinks it to 320 px first

export class Party extends DurableObject {
  constructor(ctx, env) {
    super(ctx, env);
    ctx.setWebSocketAutoResponse(new WebSocketRequestResponsePair("ping", "pong"));
  }

  async fetch(request) {
    const url = new URL(request.url);
    const path = url.pathname;
    let viewer = {};
    try { viewer = JSON.parse(request.headers.get("X-Viewer") || "{}"); } catch (e) {}
    await this.sync();

    if (path === "/api/party/ws") {
      if (request.headers.get("Upgrade") !== "websocket") return json({ error: "Expected a WebSocket." }, 426);
      const [client, server] = Object.values(new WebSocketPair());
      this.ctx.acceptWebSocket(server);
      return new Response(null, { status: 101, webSocket: client });
    }
    if (path === "/api/party" && request.method === "GET") {
      const cards = [], status = {};
      const settings = (await this.ctx.storage.get("settings")) || {};
      for (const m of ROSTER.members || []) {
        const id = m.id || party.cardId(m.character);
        const s = await this.ctx.storage.get("card:" + id);
        if (!s) continue;
        const who = viewer.dm ? "dm" : viewer.id === id ? "owner" : "other";
        cards.push(Object.assign(party.view(party.withLevel(s.card, ROSTER.level), who), { id, index: m.index, rev: s.rev, by: viewer.dm ? s.by : undefined,
                                                             updated: s.at || null }));
        // From the whole card (its private marks), not the view of it.
        status[id] = party.statusView(s.card, await this.ctx.storage.get("status:" + id), who, !!settings.show_hp);
      }
      const log = [...(await this.ctx.storage.list({ prefix: "tlog:", reverse: true, limit: 20 })).values()];
      return json({ me: viewer.id || null, dm: !!viewer.dm, level: ROSTER.level || null, cards, status,
                    show_hp: !!settings.show_hp, treasury: (await this.ctx.storage.get("treasury")) || party.blankTreasury(),
                    treasury_log: log });
    }
    if (path.startsWith("/api/party/portrait/") && request.method === "GET") {
      const id = decodeURIComponent(path.slice("/api/party/portrait/".length));
      const s = await this.ctx.storage.get("card:" + id);
      const pic = await this.ctx.storage.get("portrait:" + id);
      const hidden = s && (s.card.private || []).includes("portrait") && !viewer.dm && viewer.id !== id;
      if (!pic || hidden) return new Response("Not found", { status: 404 });
      return new Response(Uint8Array.from(atob(pic.b64), (ch) => ch.charCodeAt(0)),
        { headers: { "Content-Type": pic.mime, "Cache-Control": "private, max-age=31536000" } });
    }
    if (path === "/api/party/import" && request.method === "POST") return this.importFile(request, viewer);
    if (path === "/api/party/private" && request.method === "POST") return this.setPrivate(request, viewer);
    if (path === "/api/party/save" && request.method === "POST") return this.saveCard(request, viewer);
    if (path === "/api/party/status" && request.method === "POST") return this.setStatus(request, viewer);
    if (path === "/api/party/treasury" && request.method === "POST") return this.changeTreasury(request, viewer);
    if (!viewer.dm) return json({ error: path.startsWith("/api/party/") ? "Only the DM can do that." : "Not found." }, viewer.dm ? 404 : 403);

    // ---- the DM's helper
    if (path === "/api/party/all") {
      const out = [];
      for (const m of ROSTER.members || []) {
        const id = m.id || party.cardId(m.character);
        const s = await this.ctx.storage.get("card:" + id);
        if (s) out.push({ id, index: m.index, rev: s.rev, by: s.by, at: s.at, card: s.card,
                          portrait: !!(await this.ctx.storage.get("portrait:" + id)) });
      }
      return json({ cards: out });
    }
    if (path === "/api/party/settings" && request.method === "POST") {
      let body;
      try { body = await request.json(); } catch (e) { return json({ error: "Couldn't read that." }, 400); }
      const settings = Object.assign((await this.ctx.storage.get("settings")) || {}, { show_hp: !!body.show_hp });
      await this.ctx.storage.put("settings", settings);
      this.announce();
      return json({ ok: true, show_hp: settings.show_hp });
    }
    if (path === "/api/party/history") {
      const id = url.searchParams.get("id") || "";
      const list = [...(await this.ctx.storage.list({ prefix: `hist:${id}:`, reverse: true, limit: HISTORY_KEPT })).entries()]
        .map(([key, h]) => ({ key, at: h.at, by: h.by, summary: h.summary, undo: !!h.before }));
      return json({ id, history: list });
    }
    if (path === "/api/party/undo" && request.method === "POST") {
      let body;
      try { body = await request.json(); } catch (e) { return json({ error: "Couldn't read that." }, 400); }
      const s = await this.ctx.storage.get("card:" + body.id);
      const h = await this.ctx.storage.get(String(body.key || ""));
      if (!s || !h || !h.before || !String(body.key).startsWith(`hist:${body.id}:`)) return json({ error: "No such change." }, 404);
      // "undo", not "dm": party.yml doesn't have it yet - the helper pulls it in straight after.
      await this.save(body.id, s, party.sanitize(h.before), "undo", "undid: " + h.summary);
      return json({ ok: true });
    }
    return json({ error: "Not found." }, 404);
  }

  // party.yml as last published (roster.json) into the store - see party.reconcile.
  async sync() {
    if (!ROSTER.version || (await this.ctx.storage.get("roster")) === ROSTER.version) return;
    let changed = false;
    for (const m of ROSTER.members || []) {
      const id = m.id || party.cardId(m.character);
      const before = await this.ctx.storage.get("card:" + id);
      let out;
      try { out = party.reconcile(before, { card: m.card || {}, base: m.base || 0, hash: m.hash }); } catch (e) { continue; }
      if (out.stored !== before) { await this.ctx.storage.put("card:" + id, out.stored); changed = true; }
      if (out.history) await this.remember(id, out.history);
    }
    await this.ctx.storage.put("roster", ROSTER.version);
    if (changed) this.announce();
  }

  async importFile(request, viewer) {
    if (!viewer.id) return json({ error: "Your email isn't linked to a character yet - ask the DM." }, 403);
    let body;
    try { body = await request.json(); } catch (e) { return json({ error: "Couldn't read that." }, 400); }
    const s = await this.ctx.storage.get("card:" + viewer.id);
    if (!s) return json({ error: "Your character isn't on the Party page yet - ask the DM to publish." }, 404);
    // The player's own date (the page sends it): the worker's clock is UTC.
    const today = /^\d{4}-\d{2}-\d{2}$/.test(String(body.today)) ? body.today : new Date().toISOString().slice(0, 10);
    let data, next;
    try {
      if (String(body.file || "").length > 400000) throw new Error("That file is too big for a character.");
      data = ccc5e.parse(body.file, String(body.name || "That file"));
      next = party.fromPlayer(s.card, ccc5e.merge(s.card, ccc5e.card(data, today)));
    } catch (e) { return json({ error: e.message }, 400); }
    const portrait = String((data.Sheet || {}).portrait || "");
    const pic = portrait.match(/^data:(image\/(?:jpeg|png|webp));base64,([A-Za-z0-9+/=]+)$/);
    const named = String((data.Sheet || {}).name || data.Name || "");
    if (!body.save) {
      return json({ character: s.card.character, file: named, has_sheet: !!(data.Sheet && typeof data.Sheet === "object"),
                    portrait: !!pic, changes: ccc5e.changes(s.card, next) });
    }
    if (body.rev !== s.rev) return json({ error: "Your card changed since you opened this - reload and import again.", rev: s.rev }, 409);
    if (pic && pic[2].length <= PORTRAIT_MAX) {
      await this.ctx.storage.put("portrait:" + viewer.id, { mime: pic[1], b64: pic[2] });
      next.portrait = `/api/party/portrait/${encodeURIComponent(viewer.id)}?v=${s.rev + 1}`;
    }
    await this.save(viewer.id, s, next, viewer.email, "imported from CCC5e: " + party.summary(s.card, next));
    return json({ ok: true, rev: s.rev + 1 });
  }

  // Live status: a player changes their own; the DM (the tracker, the Party page at home) any - one, or
  // several at once ({"cards": [{id, ...}]}).
  async setStatus(request, viewer) {
    let body;
    try { body = await request.json(); } catch (e) { return json({ error: "Couldn't read that." }, 400); }
    const changes = viewer.dm && Array.isArray(body.cards) ? body.cards : [Object.assign({}, body, { id: viewer.dm ? body.id : viewer.id })];
    if (!viewer.dm && !viewer.id) return json({ error: "Your email isn't linked to a character yet - ask the DM." }, 403);
    const out = {};
    for (const ch of changes.slice(0, 20)) {
      const id = String((ch && ch.id) || "");
      const stored = await this.ctx.storage.get("card:" + id);
      if (!stored) return json({ error: "No such character." }, 404);
      const patch = Object.assign({}, ch);
      delete patch.id;
      let next;
      try {
        next = party.applyStatus(party.withLevel(stored.card, ROSTER.level), await this.ctx.storage.get("status:" + id), patch, viewer.dm ? "dm" : "owner");
      } catch (e) { return json({ error: e.message }, 400); }
      await this.ctx.storage.put("status:" + id, Object.assign(next, { at: Date.now() }));
      out[id] = next;
    }
    this.announce();
    return json({ ok: true, status: out });
  }

  // The party's shared pool: anyone in the party, or the DM, adds to it or takes from it; each change is logged.
  async changeTreasury(request, viewer) {
    if (!viewer.dm && !viewer.id) return json({ error: "Your email isn't linked to a character yet - ask the DM." }, 403);
    let body;
    try { body = await request.json(); } catch (e) { return json({ error: "Couldn't read that." }, 400); }
    let r;
    try { r = party.applyTreasury(await this.ctx.storage.get("treasury"), body); } catch (e) { return json({ error: e.message }, 400); }
    const at = Date.now();
    await this.ctx.storage.put("treasury", r.treasury);
    await this.ctx.storage.put("tlog:" + String(at).padStart(15, "0"), { at, by: viewer.dm ? "DM" : viewer.name, text: r.text });
    const old = [...(await this.ctx.storage.list({ prefix: "tlog:" })).keys()];
    if (old.length > 200) await this.ctx.storage.delete(old.slice(0, old.length - 200));
    this.announce();
    return json({ ok: true, treasury: r.treasury });
  }

  // A player's own card, edited on the page: the fields they sent replace those on the card; the rest
  // (spells, portrait, where it came from) stay. The name and the player stay as the DM has them.
  async saveCard(request, viewer) {
    if (!viewer.id) return json({ error: "Your email isn't linked to a character yet - ask the DM." }, 403);
    let body;
    try { body = await request.json(); } catch (e) { return json({ error: "Couldn't read that." }, 400); }
    const s = await this.ctx.storage.get("card:" + viewer.id);
    if (!s) return json({ error: "Your character isn't on the Party page yet." }, 404);
    if (body.rev !== s.rev) return json({ error: "Your card changed since you opened this (another device, or the DM) - your edits are still here; copy anything you need, then reload.", rev: s.rev }, 409);
    if (!body.card || typeof body.card !== "object" || Array.isArray(body.card)) return json({ error: "That isn't a character card." }, 400);
    let next;
    try { next = party.fromPlayer(s.card, Object.assign({}, s.card, body.card)); } catch (e) { return json({ error: e.message }, 400); }
    if (party.canonical(next) === party.canonical(s.card)) return json({ ok: true, rev: s.rev, unchanged: true });
    await this.save(viewer.id, s, next, viewer.email, "edited: " + party.summary(s.card, next));
    return json({ ok: true, rev: s.rev + 1 });
  }

  async setPrivate(request, viewer) {
    if (!viewer.id) return json({ error: "Your email isn't linked to a character yet - ask the DM." }, 403);
    let body;
    try { body = await request.json(); } catch (e) { return json({ error: "Couldn't read that." }, 400); }
    const s = await this.ctx.storage.get("card:" + viewer.id);
    if (!s) return json({ error: "Your character isn't on the Party page yet." }, 404);
    if (body.rev !== s.rev) return json({ error: "Your card changed since you opened this - reload and try again.", rev: s.rev }, 409);
    const next = JSON.parse(JSON.stringify(s.card));
    next.private = Array.isArray(body.private) ? body.private : [];
    const hidden = new Set((Array.isArray(body.hidden) ? body.hidden : []).map(String));
    (next.inventory || []).forEach((i) => { if (hidden.has(i.name)) i.private = true; else delete i.private; });
    let clean;
    try { clean = party.fromPlayer(s.card, next); } catch (e) { return json({ error: e.message }, 400); }
    await this.save(viewer.id, s, clean, viewer.email, party.summary(s.card, clean));
    return json({ ok: true, rev: s.rev + 1 });
  }

  async save(id, stored, card, by, summary) {
    await this.ctx.storage.put("card:" + id, Object.assign({}, stored, { card, rev: stored.rev + 1, by, at: Date.now() }));
    await this.remember(id, { by, summary, before: stored.card });
    this.announce();
  }

  async remember(id, entry) {
    const at = Date.now();
    await this.ctx.storage.put(`hist:${id}:${String(at).padStart(15, "0")}`, Object.assign({ at }, entry));
    const old = [...(await this.ctx.storage.list({ prefix: `hist:${id}:` })).keys()];
    if (old.length > HISTORY_KEPT) await this.ctx.storage.delete(old.slice(0, old.length - HISTORY_KEPT));
  }

  announce() {
    for (const ws of this.ctx.getWebSockets()) {
      try { ws.send('{"changed":true}'); } catch (e) { /* gone - it reconnects */ }
    }
  }

  webSocketMessage() {}
  webSocketClose(ws, code) {
    try { ws.close(code === 1005 ? 1000 : code); } catch (e) {}
  }
}

export class Tracker extends DurableObject {
  constructor(ctx, env) {
    super(ctx, env);
    // Phones ping to keep their connection open; answered without waking this object.
    ctx.setWebSocketAutoResponse(new WebSocketRequestResponsePair("ping", "pong"));
  }

  async fetch(request) {
    const url = new URL(request.url);
    if (url.pathname.endsWith("/ws")) {
      if (request.headers.get("Upgrade") !== "websocket") return json({ error: "Expected a WebSocket." }, 426);
      const [client, server] = Object.values(new WebSocketPair());
      this.ctx.acceptWebSocket(server);
      server.send(JSON.stringify(await this.current()));
      return new Response(null, { status: 101, webSocket: client });
    }
    if (request.method === "POST") {
      let body;
      try { body = await request.json(); } catch (e) { return json({ error: "Couldn't read the fight." }, 400); }
      const fight = clean(body);
      fight.updated = Date.now();
      await this.ctx.storage.put("fight", fight);
      const text = JSON.stringify(fight);
      for (const ws of this.ctx.getWebSockets()) {
        try { ws.send(text); } catch (e) { /* gone - it reconnects */ }
      }
      return json({ ok: true, watching: this.ctx.getWebSockets().length });
    }
    return json(await this.current());
  }

  async current() {
    return (await this.ctx.storage.get("fight")) || { active: false };
  }

  webSocketMessage() {}
  webSocketClose(ws, code) {
    try { ws.close(code === 1005 ? 1000 : code); } catch (e) {}
  }
}

// Only these fields, of the right types and sizes, are kept.
function clean(raw) {
  if (!raw || !raw.active) return raw && raw.victory === true ? { active: false, victory: true } : { active: false };
  const str = (v, n) => String(v == null ? "" : v).slice(0, n);
  const int = (v) => (Number.isInteger(v) && Math.abs(v) < 1000 ? v : null);
  return {
    active: true,
    started: !!raw.started,
    round: int(raw.round) || 1,
    list: (Array.isArray(raw.list) ? raw.list : []).slice(0, 60).map((x) => ({
      name: str(x && x.name, 60),
      init: int(x && x.init),
      pc: !!(x && x.pc),
      cur: !!(x && x.cur),
      out: !!(x && x.out),
      conc: !!(x && x.conc),
      conds: (Array.isArray(x && x.conds) ? x.conds : []).slice(0, 15)
        .map((c) => ({ n: str(c && c.n, 30), r: int(c && c.r) })),
    })),
  };
}

async function isHelper(request, env) {
  const who = await identity(request, env);
  return !!(who && who.service);
}

// Who is asking: {email} for a player (or the DM) signed in through Access, {service: true} for the
// helper's service token. Checks the signed Access token itself rather than trusting a header.
async function identity(request, env) {
  const jwt = request.headers.get("Cf-Access-Jwt-Assertion");
  if (!jwt) {
    if (env.DEV_NO_AUTH !== "1") return null;   // DEV_NO_AUTH / DEV_EMAIL: only ever set by `wrangler dev` for testing
    return request.headers.get("CF-Access-Client-Id") ? { service: true } : { email: env.DEV_EMAIL || "" };
  }
  try {
    const [h, p, s] = jwt.split(".");
    const header = JSON.parse(b64text(h)), payload = JSON.parse(b64text(p));
    const TEAM = team(env);
    if (!TEAM) return null;   // not configured: nobody is trusted
    const certs = await (await fetch(TEAM + "/cdn-cgi/access/certs", { cf: { cacheTtl: 3600 } })).json();
    const jwk = (certs.keys || []).find((k) => k.kid === header.kid);
    if (!jwk) return null;
    const key = await crypto.subtle.importKey("jwk", jwk, { name: "RSASSA-PKCS1-v1_5", hash: "SHA-256" }, false, ["verify"]);
    const ok = await crypto.subtle.verify("RSASSA-PKCS1-v1_5", key, b64bytes(s), new TextEncoder().encode(h + "." + p));
    if (!ok || payload.iss !== TEAM || !(payload.exp > Date.now() / 1000)) return null;
    if (payload.email) return { email: String(payload.email).toLowerCase() };
    return payload.common_name ? { service: true } : null;
  } catch (e) {
    return null;
  }
}

function b64bytes(s) {
  const bin = atob(s.replace(/-/g, "+").replace(/_/g, "/") + "===".slice((s.length + 3) % 4));
  return Uint8Array.from(bin, (c) => c.charCodeAt(0));
}
function b64text(s) { return new TextDecoder().decode(b64bytes(s)); }

function json(obj, status = 200) {
  return new Response(JSON.stringify(obj), {
    status, headers: { "Content-Type": "application/json", "Cache-Control": "no-store" },
  });
}
