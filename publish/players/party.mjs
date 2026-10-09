// The live Party page's rules, kept apart from the worker so they can be tested on their own
// (tests/party.test.mjs). The worker's Party store (worker.js) uses them.
//
// A card online is the same as a card in data/party.yml (templates/character.yml), without the DM's
// note and the player's email - those never go online. Each card has a rev (bumped on every change).

// Every field a card may have online, in order.
export const FIELDS = ["player", "character", "race", "class", "background", "level", "ac", "ac_note", "hp",
  "hp_formula", "speed", "initiative", "passive_perception", "abilities", "saves", "skills", "resistances", "immunities",
  "condition_immunities", "senses", "languages", "proficiencies", "features", "actions", "bonus_actions", "reactions",
  "spellcasting", "inventory", "currency", "persona", "portrait", "private", "source"];
// A player never changes these on their own card (the DM does, in party.yml).
export const PROTECTED = ["character", "player"];
// What a player may mark private: a whole field, or one part of the persona.
export const PRIVATE_PATHS = ["saves", "skills", "senses", "languages", "resistances", "immunities",
  "condition_immunities", "proficiencies", "features", "actions", "bonus_actions", "reactions", "spellcasting",
  "inventory", "currency", "persona", "portrait", "persona.traits", "persona.ideal", "persona.bond", "persona.flaw",
  "persona.appearance", "persona.backstory", "persona.allies", "persona.deity", "persona.alignment"];
export const MAX_CARD_BYTES = 100000;

export function cardId(name) {
  return "pc-" + String(name || "").toLowerCase().replace(/'/g, "").replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
}

const clone = (x) => JSON.parse(JSON.stringify(x));

// A card as the other players see it - the same rule as hooks/campaign.py strip_private.
export function stripPrivate(card) {
  const out = clone(card);
  for (const path of out.private || []) {
    const [head, sub] = String(path).split(".", 2);
    if (sub && out[head] && typeof out[head] === "object" && !Array.isArray(out[head])) {
      delete out[head][sub];
      if (!Object.keys(out[head]).length) delete out[head];
    } else if (!sub) {
      delete out[head];
    }
  }
  delete out.private;
  if (Array.isArray(out.inventory)) out.inventory = out.inventory.filter((i) => !(i && i.private));
  return out;
}

// What one viewer gets: the DM and the card's own player see everything on it; anyone else, not the private parts.
export function view(card, who) {
  return who === "dm" || who === "owner" ? clone(card) : stripPrivate(card);
}

// ---------------------------------------------------------------- checking what comes in
const str = (v, n) => String(v == null ? "" : v).replace(/\s+$/, "").slice(0, n);
const line = (v, n) => String(v == null ? "" : v).split(/\s+/).filter(Boolean).join(" ").slice(0, n);
const int = (v, lo, hi) => { const n = parseInt(v, 10); return Number.isFinite(n) && n >= lo && n <= hi ? n : undefined; };
const obj = (v) => v && typeof v === "object" && !Array.isArray(v);

function entries(list, max = 120) {
  return (Array.isArray(list) ? list : []).slice(0, max).filter(obj)
    .map((e) => ({ name: line(e.name, 200), text: line(e.text, 6000) })).filter((e) => e.name || e.text);
}

// Only known fields, of the right types and sizes. Throws for a card that can't be kept.
export function sanitize(raw) {
  if (!obj(raw)) throw new Error("That isn't a character card.");
  const c = {};
  for (const k of ["player", "character", "race", "class", "background", "ac_note", "hp_formula", "speed", "saves", "skills",
    "resistances", "immunities", "condition_immunities", "senses", "languages", "portrait"]) {
    if (raw[k] != null && raw[k] !== "") c[k] = line(raw[k], k === "skills" || k === "languages" ? 1000 : 400);
  }
  for (const [k, lo, hi] of [["level", 1, 30], ["ac", 0, 60], ["hp", 0, 2000], ["initiative", -20, 30], ["passive_perception", 0, 60]]) {
    const n = int(raw[k], lo, hi);
    if (n !== undefined) c[k] = n;
  }
  if (obj(raw.abilities)) {
    const a = {};
    for (const k of ["str", "dex", "con", "int", "wis", "cha"]) { const n = int(raw.abilities[k], 1, 30); if (n !== undefined) a[k] = n; }
    if (Object.keys(a).length) c.abilities = a;
  }
  if (obj(raw.proficiencies)) {
    const p = {};
    for (const k of ["armor", "weapons", "tools"]) if (raw.proficiencies[k]) p[k] = line(raw.proficiencies[k], 1000);
    if (Object.keys(p).length) c.proficiencies = p;
  }
  for (const k of ["features", "actions", "bonus_actions", "reactions"]) {
    const l = entries(raw[k]);
    if (l.length) c[k] = l;
  }
  if (Array.isArray(raw.spellcasting)) {
    const sc = raw.spellcasting.slice(0, 8).filter(obj).map((e) => {
      const out = { name: line(e.name, 120) };
      if (e.ability) out.ability = line(e.ability, 40);
      const dc = int(e.save_dc, 0, 40), at = int(e.attack, -10, 30);
      if (dc !== undefined) out.save_dc = dc;
      if (at !== undefined) out.attack = at;
      if (obj(e.slots)) {
        const s = {};
        for (const [lvl, n] of Object.entries(e.slots)) { const l = int(lvl, 1, 9), m = int(n, 0, 20); if (l && m) s[l] = m; }
        if (Object.keys(s).length) out.slots = s;
      }
      if (e.pact) out.pact = true;
      if (Array.isArray(e.cantrips)) out.cantrips = e.cantrips.slice(0, 60).map((x) => line(x, 120)).filter(Boolean);
      if (Array.isArray(e.spells)) {
        out.spells = e.spells.slice(0, 300).filter(obj).map((x) => Object.assign({ name: line(x.name, 120), level: int(x.level, 0, 9) || 0 },
          x.prepared ? { prepared: true } : {})).filter((x) => x.name);
      }
      return out;
    }).filter((e) => e.name);
    if (sc.length) c.spellcasting = sc;
  }
  if (Array.isArray(raw.inventory)) {
    const inv = raw.inventory.slice(0, 400).filter(obj).map((i) => {
      const out = { name: line(i.name, 200) };
      const q = int(i.qty, 0, 100000);
      if (q !== undefined && q !== 1) out.qty = q;
      for (const f of ["equipped", "attuned", "magic", "private"]) if (i[f]) out[f] = true;
      return out;
    }).filter((i) => i.name);
    if (inv.length) c.inventory = inv;
  }
  if (obj(raw.currency)) {
    const m = {};
    // In the order the card has them (party.yml's own), so getting players' changes doesn't reshuffle it.
    for (const k of Object.keys(raw.currency)) {
      if (!["pp", "gp", "ep", "sp", "cp"].includes(k)) continue;
      const n = int(raw.currency[k], 0, 100000000);
      if (n) m[k] = n;
    }
    if (Object.keys(m).length) c.currency = m;
  }
  if (obj(raw.persona)) {
    const p = {};
    for (const k of Object.keys(raw.persona)) {   // in the card's own order, as with the money
      const v = raw.persona[k];
      if (["ideal", "bond", "flaw", "appearance", "allies", "deity", "alignment"].includes(k)) { if (v) p[k] = line(v, 2000); }
      else if (k === "backstory") { if (v) p.backstory = str(v, 20000).trim(); }
      else if (k === "traits" && Array.isArray(v)) {
        const t = v.slice(0, 10).map((x) => line(x, 2000)).filter(Boolean);
        if (t.length) p.traits = t;
      }
    }
    if (Object.keys(p).length) c.persona = p;
  }
  if (Array.isArray(raw.private)) {
    const priv = [...new Set(raw.private.map(String))].filter((x) => PRIVATE_PATHS.includes(x));
    if (priv.length) c.private = priv;
  }
  if (obj(raw.source)) c.source = { from: line(raw.source.from, 40), imported: line(raw.source.imported, 20) };
  const ordered = {};
  for (const k of FIELDS) if (c[k] !== undefined) ordered[k] = c[k];
  if (new TextEncoder().encode(JSON.stringify(ordered)).length > MAX_CARD_BYTES) throw new Error("That card is too big to keep.");
  return ordered;
}

// A player's new card, keeping what only the DM changes.
export function fromPlayer(old, incoming) {
  const c = sanitize(incoming);
  for (const k of PROTECTED) {
    if (old && old[k] !== undefined) c[k] = old[k]; else delete c[k];
  }
  if (old && old.portrait && !c.portrait) c.portrait = old.portrait;
  return sanitize(c);
}

// ---------------------------------------------------------------- the DM's party.yml, arriving with each publish
// The same card, ignoring the portrait's address (party.yml keeps a file path; online it may be the uploaded one).
export function canonical(card) {
  const c = clone(card || {});
  delete c.portrait;
  const sort = (x) => Array.isArray(x) ? x.map(sort) : obj(x) ? Object.fromEntries(Object.keys(x).sort().map((k) => [k, sort(x[k])])) : x;
  return JSON.stringify(sort(c));
}

// stored: {card, rev, seed, by, at} or undefined; entry: the roster's {card, base, hash} for this character.
// Returns {stored, history} - history is a line for the DM's change history, or null.
export function reconcile(stored, entry, now = Date.now()) {
  const card = sanitize(entry.card || {});
  if (!stored) return { stored: { card, rev: 1, seed: entry.hash, by: "dm", at: now }, history: null };
  if (entry.hash === stored.seed) return { stored, history: null };                       // party.yml unchanged since
  if (canonical(card) === canonical(stored.card)) return { stored: Object.assign({}, stored, { seed: entry.hash }), history: null };
  // The DM's change applies if nobody changed the card online since the DM's last version went up (by: "dm"),
  // or if the DM had the latest card when they made it (base: the rev they got).
  if (stored.by === "dm" || (entry.base || 0) === stored.rev) {
    return { stored: { card, rev: stored.rev + 1, seed: entry.hash, by: "dm", at: now },
             history: { by: "dm", summary: "updated from party.yml: " + summary(stored.card, card), before: stored.card } };
  }
  // A player changed the card after the DM last got it: keep theirs, and say so.
  return { stored: Object.assign({}, stored, { seed: entry.hash }),
           history: { by: "dm", summary: "party.yml changes held back - the card changed online since the DM last got players' changes; get them, then edit and publish again", before: null } };
}

// A short line for the change history.
export function summary(before, after) {
  before = before || {}; after = after || {};
  const bits = [];
  for (const [k, label] of [["level", "level"], ["hp", "HP"], ["ac", "AC"]]) {
    if (before[k] !== after[k] && (before[k] !== undefined || after[k] !== undefined)) bits.push(`${label} ${before[k] ?? "-"} → ${after[k] ?? "-"}`);
  }
  const names = (c, k) => new Set((c[k] || []).map((e) => e.name));
  const added = (k) => [...names(after, k)].filter((n) => !names(before, k).has(n));
  const feats = added("features").concat(added("actions"), added("bonus_actions"), added("reactions"));
  if (feats.length) bits.push("+ " + feats.slice(0, 4).join(", ") + (feats.length > 4 ? ` and ${feats.length - 4} more` : ""));
  const nowPrivate = (after.private || []).filter((p) => !(before.private || []).includes(p));
  const nowShared = (before.private || []).filter((p) => !(after.private || []).includes(p));
  if (nowPrivate.length) bits.push("marked private: " + nowPrivate.join(", "));
  if (nowShared.length) bits.push("shared again: " + nowShared.join(", "));
  const hiddenItems = (c) => new Set((c.inventory || []).filter((i) => i.private).map((i) => i.name));
  const hid = [...hiddenItems(after)].filter((n) => !hiddenItems(before).has(n));
  const shown = [...hiddenItems(before)].filter((n) => !hiddenItems(after).has(n));
  if (hid.length) bits.push("hid " + hid.join(", "));
  if (shown.length) bits.push("showed " + shown.join(", "));
  if (!bits.length) bits.push(canonical(before) === canonical(after) ? "no change" : "details changed");
  return bits.join("; ");
}

// A card that gives no level of its own is at the party's (data/party.yml level:) - shown, and counted for
// hit dice, as such; the card itself is left as it is.
export function withLevel(card, partyLevel) {
  const lvl = parseInt(partyLevel, 10);
  return card && card.level == null && lvl > 0 ? Object.assign({}, card, { level: lvl }) : card;
}

// ---------------------------------------------------------------- live status: HP, conditions, the players' trackers
// Kept beside each card, not in it: it changes all through a session, never goes into party.yml, and
// isn't in the card's change history. hp null means "at full" (the card's HP); slots counts the slots
// *used*, keyed "<spellcasting entry>:<level>"; hd counts the hit dice used.
export const CONDITIONS = ["Blinded", "Charmed", "Deafened", "Frightened", "Grappled", "Incapacitated", "Invisible", "Paralyzed",
  "Petrified", "Poisoned", "Prone", "Restrained", "Stunned", "Unconscious", "Exhaustion", "Concentrating"];
const HIT_DIE = { barbarian: 12, fighter: 10, paladin: 10, ranger: 10, sorcerer: 6, wizard: 6 };

// A whole number held to lo..hi (undefined if it isn't a number at all).
const clamp = (v, lo, hi) => { const n = parseInt(v, 10); return Number.isFinite(n) ? Math.max(lo, Math.min(hi, n)) : undefined; };

export function blankStatus() {
  return { hp: null, temp: 0, conds: [], insp: false, slots: {}, hd: 0, death: { s: 0, f: 0 } };
}

// The card's hit die: from its HP formula (3d8 + 6) or else its class.
export function hitDie(card) {
  const m = String((card && card.hp_formula) || "").match(/d(\d+)/);
  if (m) return +m[1];
  const cls = String((card && card.class) || "").toLowerCase().split(/[\s(]/)[0];
  return HIT_DIE[cls] || 8;
}

// Every spell slot the card has: {"0:1": 4, "0:2": 2, "1:1": 1} (entry:level -> how many).
export function slotTotals(card) {
  const out = {};
  ((card && card.spellcasting) || []).forEach((sc, i) => {
    for (const [lvl, n] of Object.entries((sc && sc.slots) || {})) if (+n > 0) out[`${i}:${lvl}`] = +n;
  });
  return out;
}

// A change to a card's status - from its player ("owner") or the DM ("dm": the tracker, the Party page at
// home). Fields not in the patch stay. hp_delta is damage (negative, taken from temporary HP first) or
// healing (positive, up to the card's HP). Throws for a change that can't be kept.
export function applyStatus(card, old, patch, who) {
  if (!obj(patch)) throw new Error("That isn't a change.");
  const s = Object.assign(blankStatus(), clone(old || {}));
  const max = int(card && card.hp, 0, 2000);
  const has = (k) => Object.prototype.hasOwnProperty.call(patch, k);
  if (has("hp")) s.hp = patch.hp === null || patch.hp === "" ? null : clamp(patch.hp, 0, max != null ? max : 2000) ?? s.hp;
  if (has("temp")) s.temp = clamp(patch.temp, 0, 999) ?? s.temp;
  if (has("hp_delta")) {
    let d = int(patch.hp_delta, -5000, 5000) || 0;
    let cur = s.hp == null ? (max || 0) : s.hp;
    if (d < 0) { const t = Math.min(s.temp || 0, -d); s.temp -= t; d += t; }
    cur = Math.max(0, cur + d);
    if (max != null) cur = Math.min(cur, max);
    s.hp = cur;
  }
  if (has("conds")) {
    if (!Array.isArray(patch.conds)) throw new Error("Conditions should be a list.");
    s.conds = patch.conds.slice(0, 15).filter(obj).map((c) => {
      const out = { n: line(c.n, 30) };
      const r = int(c.r, 0, 99);
      out.r = r === undefined || c.r === null ? null : r;
      return out;
    }).filter((c) => c.n);
  }
  if (has("insp")) s.insp = !!patch.insp;
  if (has("slots")) {
    if (!obj(patch.slots)) throw new Error("Spell slots should be a map.");
    const totals = slotTotals(card), next = {};
    for (const [k, v] of Object.entries(patch.slots)) {
      if (!totals[k]) continue;
      const n = clamp(v, 0, totals[k]);
      if (n) next[k] = n;
    }
    s.slots = next;
  }
  if (has("hd")) s.hd = clamp(patch.hd, 0, int(card && card.level, 1, 30) || 1) ?? s.hd;
  if (has("death")) {
    if (!obj(patch.death)) throw new Error("Death saves should be {s, f}.");
    s.death = { s: clamp(patch.death.s, 0, 3) || 0, f: clamp(patch.death.f, 0, 3) || 0 };
  }
  // Back on their feet: the death saves start over.
  if ((has("hp") || has("hp_delta")) && s.hp != null && s.hp > 0) s.death = { s: 0, f: 0 };
  if (max != null && s.hp != null && s.hp >= max) s.hp = null;   // at full: follows the card's HP if it changes
  return s;
}

// What one viewer gets of a card's status: the other players don't see current HP unless the DM shows
// it (showHp), nor the slots of a player who keeps their spellcasting private.
export function statusView(card, status, who, showHp) {
  const s = Object.assign(blankStatus(), clone(status || {}));
  if (who === "other") {
    if (!showHp) { delete s.hp; delete s.temp; }
    if (((card && card.private) || []).includes("spellcasting")) delete s.slots;
  }
  return s;
}

// ---------------------------------------------------------------- the party treasury
// One shared pool: coins and items anyone in the party (or the DM) adds to or takes from. A change is
// {coins: {gp: +10, sp: -5}, add: {name, qty}, take: {name, qty}, note}; coins can't go below zero.
export const COINS = ["pp", "gp", "ep", "sp", "cp"];
export function blankTreasury() { return { coins: {}, items: [] }; }

export function applyTreasury(old, patch) {
  if (!obj(patch)) throw new Error("That isn't a change.");
  const t = Object.assign(blankTreasury(), clone(old || {}));
  const bits = [];
  if (obj(patch.coins)) {
    for (const k of COINS) {
      const d = int(patch.coins[k], -100000000, 100000000);
      if (!d) continue;
      const now = (t.coins[k] || 0) + d;
      if (now < 0) throw new Error(`The party only has ${t.coins[k] || 0} ${k}.`);
      if (now) t.coins[k] = now; else delete t.coins[k];
      bits.push((d > 0 ? "+" : "−") + Math.abs(d) + " " + k);
    }
  }
  if (obj(patch.add)) {
    const name = line(patch.add.name, 200), q = int(patch.add.qty, 1, 100000) || 1;
    if (!name) throw new Error("Name the item.");
    const it = t.items.find((i) => i.name.toLowerCase() === name.toLowerCase());
    if (it) it.qty = (it.qty || 1) + q; else t.items.push({ name, qty: q });
    if (t.items.length > 200) throw new Error("The treasury is full - 200 kinds of item at most.");
    bits.push("+ " + (q > 1 ? q + "× " : "") + name);
  }
  if (obj(patch.take)) {
    const name = line(patch.take.name, 200), q = int(patch.take.qty, 1, 100000) || 1;
    const it = t.items.find((i) => i.name.toLowerCase() === name.toLowerCase());
    if (!it) throw new Error(`The treasury has no ${name}.`);
    if ((it.qty || 1) < q) throw new Error(`The treasury has only ${it.qty || 1} ${it.name}.`);
    it.qty = (it.qty || 1) - q;
    if (!it.qty) t.items = t.items.filter((i) => i !== it);
    bits.push("− " + (q > 1 ? q + "× " : "") + it.name);
  }
  if (!bits.length) throw new Error("Nothing to change.");
  const note = line(patch.note, 200);
  return { treasury: t, text: bits.join(", ") + (note ? " — " + note : "") };
}
