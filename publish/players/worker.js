// The players' site: the built pages (./site), plus the live initiative tracker and card suggestions.
//
//   GET  /api/tracker            -> the fight as the players see it (JSON)
//   GET  /api/tracker/ws         -> the same, live: a WebSocket that gets every change
//   POST /api/tracker            -> the DM's tracker, via the save helper (tools/site_helper.py)
//
//   GET  /api/me                 -> the signed-in player's character, its card, and their latest suggestion
//   POST /api/cards/suggest      -> {"member": {...}} a suggested change to their own card, for the DM to approve
//   GET  /api/cards/suggestions  -> the DM's helper: suggestions waiting for a decision
//   POST /api/cards/resolve      -> the DM's helper: {"id", "status": "approved" | "rejected"}
//
//   GET  /api/items/claims       -> who has asked for which up-for-grabs item (the helper also gets ids and emails)
//   POST /api/items/claim        -> {"item"} claim it for your character; {"item", "withdraw": true} take that back
//   POST /api/items/resolve      -> the DM's helper: {"id", "status": "approved" | "rejected"}
//
// Cloudflare Access sits in front of all of it, so every request here is already signed in; the
// signed Access token says who (a player's email, or the helper's service token). Which email plays
// which character comes from roster.json, written by the publish script from data/party.yml - it's part of
// this script, never one of the site's files. The helper's calls (POST tracker, suggestions, resolve)
// are refused for players.
import { DurableObject } from "cloudflare:workers";
import ROSTER from "./roster.json";

// Your Cloudflare Access team address (https://<team>.cloudflareaccess.com). The publish script writes
// it into wrangler.jsonc as ACCESS_TEAM from campaign.yml (online: access_team:).
const team = (env) => String(env.ACCESS_TEAM || "").replace(/\/+$/, "");

// What a player may suggest for their card (not their name, the player field, or the DM's note).
const TEXT = ["race", "class", "ac_note", "hp_formula", "speed", "saves", "skills", "resistances", "immunities",
              "condition_immunities", "senses", "languages"];
const NUMBERS = ["level", "ac", "hp", "initiative", "passive_perception"];
const LISTS = ["features", "actions", "bonus_actions", "reactions"];
const ABIL = ["str", "dex", "con", "int", "wis", "cha"];

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
    if (path === "/api/me" || path.startsWith("/api/cards/")) return cards(request, env, path);
    if (path.startsWith("/api/items/")) return claims(request, env, path);
    return env.ASSETS.fetch(request);
  },
};

async function cards(request, env, path) {
  const store = env.CARDS.get(env.CARDS.idFromName("cards"));
  const who = await identity(request, env);
  if (!who) return json({ error: "Not signed in." }, 401);
  if (path === "/api/cards/suggestions" || path === "/api/cards/resolve") {
    if (!who.service) return json({ error: "Only the DM can do that." }, 403);
    return store.fetch(new Request("https://cards/" + path.split("/").pop(), request));
  }
  const me = playerFor(who.email);
  if (path === "/api/me") {
    if (!me) return json({ character: null });
    const latest = await (await store.fetch("https://cards/mine?character=" + encodeURIComponent(me.character))).json();
    return json({ character: me.character, index: me.index, level: ROSTER.level || null, card: me.card || {}, suggestion: latest });
  }
  if (path === "/api/cards/suggest" && request.method === "POST") {
    if (!me) return json({ error: "Your email isn't linked to a character yet - ask the DM." }, 403);
    let body;
    try { body = await request.json(); } catch (e) { return json({ error: "Couldn't read the card." }, 400); }
    const member = cleanMember(body && body.member);
    return store.fetch("https://cards/suggest", {
      method: "POST", body: JSON.stringify({ character: me.character, index: me.index, email: who.email, member }),
    });
  }
  return json({ error: "Not found." }, 404);
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

function playerFor(email) {
  if (!email) return null;
  return (ROSTER.members || []).find((m) => m.email && m.email === String(email).toLowerCase()) || null;
}

// Suggested card changes: one waiting suggestion per character (a new one replaces it), kept
// with its outcome once the DM decides, so the player can see what happened.
export class Cards extends DurableObject {
  async fetch(request) {
    const url = new URL(request.url);
    const what = url.pathname.slice(1);
    if (what === "suggest") {
      const s = await request.json();
      const entry = { id: crypto.randomUUID(), character: s.character, index: s.index, email: s.email,
                      member: s.member, at: Date.now(), status: "pending" };
      await this.ctx.storage.put("sug:" + s.character, entry);
      return json({ ok: true, status: "pending" });
    }
    if (what === "mine") {
      return json((await this.ctx.storage.get("sug:" + url.searchParams.get("character"))) || null);
    }
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
    const all = [...(await this.ctx.storage.list({ prefix: "sug:" })).values()];
    if (what === "suggestions") return json({ suggestions: all.filter((s) => s.status === "pending") });
    if (what === "resolve" && request.method === "POST") {
      const r = await request.json();
      const s = all.find((x) => x.id === r.id);
      if (!s || !["approved", "rejected"].includes(r.status)) return json({ error: "No such suggestion." }, 404);
      s.status = r.status;
      s.decided = Date.now();
      await this.ctx.storage.put("sug:" + s.character, s);
      return json({ ok: true });
    }
    return json({ error: "Not found." }, 404);
  }
}

function cleanMember(raw) {
  const m = {};
  if (!raw || typeof raw !== "object") return m;
  const str = (v, n) => String(v).replace(/\s+/g, " ").trim().slice(0, n);
  for (const k of TEXT) if (raw[k] != null && str(raw[k], 300)) m[k] = str(raw[k], 300);
  for (const k of NUMBERS) {
    const n = parseInt(String(raw[k] == null ? "" : raw[k]).replace("+", ""), 10);
    if (!isNaN(n) && Math.abs(n) < 1000) m[k] = n;
  }
  if (raw.abilities && typeof raw.abilities === "object") {
    const a = {};
    for (const k of ABIL) {
      const n = parseInt(raw.abilities[k], 10);
      if (!isNaN(n) && n >= 1 && n <= 30) a[k] = n;
    }
    if (Object.keys(a).length) m.abilities = a;
  }
  for (const k of LISTS) {
    if (!Array.isArray(raw[k])) continue;
    const rows = raw[k].slice(0, 40).map((e) => ({ name: str((e && e.name) || "", 100), text: str((e && e.text) || "", 2000) }))
      .filter((e) => e.name || e.text);
    if (rows.length) m[k] = rows;
  }
  return m;
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
