// The live Party page's rules (publish/players/party.mjs). Run: node --test tests/
import test from "node:test";
import assert from "node:assert/strict";
import { cardId, stripPrivate, view, sanitize, fromPlayer, reconcile, canonical, summary } from "../publish/players/party.mjs";

const tam = {
  player: "Sam", character: 'Tamsin "Tam" Underbough', race: "Lightfoot Halfling", class: "Rogue (Thief)", level: 3, ac: 14, hp: 24,
  skills: "Stealth +7", persona: { ideal: "Freedom.", bond: "Wim the apprentice.", backstory: "Long story.\n\nPart two." },
  inventory: [{ name: "Shortsword", equipped: true }, { name: "A letter from Wim", private: true }],
  private: ["persona.bond", "persona.backstory", "skills"],
};

test("card ids match the site's anchors", () => {
  assert.equal(cardId('Tamsin "Tam" Underbough'), "pc-tamsin-tam-underbough");
  assert.equal(cardId("Rak'tu"), "pc-raktu");
});

test("other players don't get what's private", () => {
  const seen = view(tam, "other");
  assert.equal(seen.persona.bond, undefined);
  assert.equal(seen.persona.backstory, undefined);
  assert.equal(seen.persona.ideal, "Freedom.");
  assert.equal(seen.skills, undefined);
  assert.equal(seen.private, undefined);
  assert.deepEqual(seen.inventory.map((i) => i.name), ["Shortsword"]);
  assert.ok(!JSON.stringify(seen).includes("Wim"));
});

test("the player and the DM see all of it", () => {
  for (const who of ["owner", "dm"]) {
    const seen = view(tam, who);
    assert.equal(seen.persona.bond, "Wim the apprentice.");
    assert.equal(seen.inventory.length, 2);
    assert.deepEqual(seen.private, tam.private);
  }
});

test("a whole persona marked private goes entirely", () => {
  const seen = stripPrivate({ character: "X", persona: { ideal: "a" }, private: ["persona"] });
  assert.equal(seen.persona, undefined);
});

test("sanitize keeps known fields only, in range, and the backstory's paragraphs", () => {
  const c = sanitize({ character: "X", level: 99, ac: "15", email: "x@y.z", note: "DM only", nonsense: 1,
    abilities: { str: 18, dex: 0, foo: 3 }, persona: { backstory: "A.\n\nB." }, private: ["persona.bond", "email", "note"] });
  assert.equal(c.level, undefined);
  assert.equal(c.ac, 15);
  assert.equal(c.email, undefined);
  assert.equal(c.note, undefined);
  assert.equal(c.nonsense, undefined);
  assert.deepEqual(c.abilities, { str: 18 });
  assert.equal(c.persona.backstory, "A.\n\nB.");
  assert.deepEqual(c.private, ["persona.bond"]);
  assert.throws(() => sanitize("nope"));
  assert.throws(() => sanitize({ character: "Big", features: [{ name: "x", text: "y".repeat(6000) }].concat(
    Array.from({ length: 100 }, (_, i) => ({ name: "f" + i, text: "z".repeat(5000) }))) }), /too big/);
});

test("a player can't rename their character or change the player", () => {
  const next = fromPlayer(tam, Object.assign({}, tam, { character: "Someone Else", player: "Mallory", level: 4 }));
  assert.equal(next.character, tam.character);
  assert.equal(next.player, "Sam");
  assert.equal(next.level, 4);
});

test("reconcile: a new card is seeded from party.yml", () => {
  const { stored, history } = reconcile(undefined, { card: tam, base: 0, hash: "h1" }, 1);
  assert.equal(stored.rev, 1);
  assert.equal(stored.seed, "h1");
  assert.equal(history, null);
});

test("reconcile: party.yml unchanged since the last publish leaves the card alone", () => {
  const s0 = { card: sanitize(Object.assign({}, tam, { level: 5 })), rev: 4, seed: "h1", by: "Sam" };
  assert.equal(reconcile(s0, { card: tam, base: 2, hash: "h1" }).stored, s0);
});

test("reconcile: the same card under a new hash just notes it", () => {
  const s0 = { card: sanitize(tam), rev: 4, seed: "old", by: "Sam" };
  const { stored, history } = reconcile(s0, { card: Object.assign({}, tam, { portrait: "party/portraits/x.jpg" }), base: 4, hash: "new" });
  assert.equal(stored.rev, 4);
  assert.equal(stored.seed, "new");
  assert.equal(history, null);
});

test("reconcile: the DM's change applies when they had the latest card", () => {
  const s0 = { card: sanitize(tam), rev: 4, seed: "old", by: "Sam" };
  const { stored, history } = reconcile(s0, { card: Object.assign({}, tam, { hp: 30 }), base: 4, hash: "new" }, 9);
  assert.equal(stored.rev, 5);
  assert.equal(stored.card.hp, 30);
  assert.equal(stored.by, "dm");
  assert.match(history.summary, /HP 24 → 30/);
  assert.equal(history.before.hp, 24);
});

test("reconcile: the DM's change is held back when the player changed the card since", () => {
  const s0 = { card: sanitize(Object.assign({}, tam, { level: 4 })), rev: 6, seed: "old", by: "Sam" };
  const { stored, history } = reconcile(s0, { card: Object.assign({}, tam, { hp: 30 }), base: 4, hash: "new" });
  assert.equal(stored.rev, 6);
  assert.equal(stored.card.level, 4);
  assert.equal(stored.card.hp, 24);
  assert.match(history.summary, /held back/);
});

test("reconcile: a card nobody changed online takes the DM's change, even without getting players' changes first", () => {
  const s0 = { card: sanitize(tam), rev: 1, seed: "h1", by: "dm" };
  const { stored, history } = reconcile(s0, { card: Object.assign({}, tam, { hp: 30 }), base: 0, hash: "h2" });
  assert.equal(stored.rev, 2);
  assert.equal(stored.card.hp, 30);
  assert.match(history.summary, /updated from party.yml/);
});

test("canonical ignores the portrait's address", () => {
  assert.equal(canonical(Object.assign({}, tam, { portrait: "a" })), canonical(Object.assign({}, tam, { portrait: "b" })));
});

test("summary says what changed", () => {
  const after = Object.assign({}, tam, { level: 4, features: [{ name: "Uncanny Dodge", text: "" }], private: tam.private.concat("currency") });
  const s = summary(tam, after);
  assert.match(s, /level 3 → 4/);
  assert.match(s, /\+ Uncanny Dodge/);
  assert.match(s, /marked private: currency/);
  assert.equal(summary(tam, tam), "no change");
});

test("sanitize keeps the card's own order for money and persona", () => {
  const c = sanitize({ character: "X", currency: { cp: 3, gp: 2 }, persona: { traits: ["a"], ideal: "b", backstory: "c", alignment: "d" } });
  assert.deepEqual(Object.keys(c.currency), ["cp", "gp"]);
  assert.deepEqual(Object.keys(c.persona), ["traits", "ideal", "backstory", "alignment"]);
});

// ---------------------------------------------------------------- live status and the treasury
import { applyStatus, statusView, hitDie, slotTotals, applyTreasury, blankStatus } from "../publish/players/party.mjs";

const wiz = { character: "Ilvara", class: "Wizard", level: 3, hp: 17, spellcasting: [{ name: "Wizard", slots: { 1: 4, 2: 2 } }], private: [] };

test("damage comes off temporary HP first, healing stops at the card's HP", () => {
  let s = applyStatus(wiz, null, { temp: 5 }, "owner");
  s = applyStatus(wiz, s, { hp_delta: -8 }, "dm");
  assert.equal(s.temp, 0);
  assert.equal(s.hp, 14);
  s = applyStatus(wiz, s, { hp_delta: -40 }, "dm");
  assert.equal(s.hp, 0);
  s = applyStatus(wiz, s, { death: { s: 1, f: 2 } }, "owner");
  assert.deepEqual(s.death, { s: 1, f: 2 });
  s = applyStatus(wiz, s, { hp_delta: 50 }, "owner");
  assert.equal(s.hp, null, "back at full: follows the card");
  assert.deepEqual(s.death, { s: 0, f: 0 }, "up again: death saves start over");
  assert.equal(applyStatus(wiz, null, { hp: 99 }, "dm").hp, null, "set above the maximum: full");
  assert.equal(applyStatus(wiz, null, { hp: 9 }, "dm").hp, 9);
});

test("slots used only up to what the card has; hit dice up to the level", () => {
  assert.deepEqual(slotTotals(wiz), { "0:1": 4, "0:2": 2 });
  const s = applyStatus(wiz, null, { slots: { "0:1": 9, "0:2": 1, "0:3": 1, "1:1": 1 }, hd: 7, insp: true }, "owner");
  assert.deepEqual(s.slots, { "0:1": 4, "0:2": 1 });
  assert.equal(s.hd, 3);
  assert.equal(s.insp, true);
  assert.equal(hitDie(wiz), 6);
  assert.equal(hitDie({ hp_formula: "3d8 + 6", class: "Wizard" }), 8);
  assert.equal(hitDie({ class: "Monk (Way of the Open Hand)" }), 8);
});

test("conditions are kept tidy", () => {
  const s = applyStatus(wiz, null, { conds: [{ n: "Prone" }, { n: "Poisoned", r: 3 }, { n: "" }, "junk"] }, "dm");
  assert.deepEqual(s.conds, [{ n: "Prone", r: null }, { n: "Poisoned", r: 3 }]);
  assert.throws(() => applyStatus(wiz, null, { conds: "Prone" }, "dm"));
});

test("other players see current HP only when the DM shows it, and no private slots", () => {
  const s = applyStatus(wiz, null, { hp: 9, temp: 2, slots: { "0:1": 1 } }, "dm");
  assert.equal(statusView(wiz, s, "other", false).hp, undefined);
  assert.equal(statusView(wiz, s, "other", false).temp, undefined);
  assert.equal(statusView(wiz, s, "other", true).hp, 9);
  assert.equal(statusView(wiz, s, "owner", false).hp, 9);
  assert.equal(statusView(wiz, s, "dm", false).hp, 9);
  const shy = Object.assign({}, wiz, { private: ["spellcasting"] });
  assert.equal(statusView(shy, s, "other", true).slots, undefined);
  assert.deepEqual(statusView(shy, s, "owner", true).slots, { "0:1": 1 });
  assert.deepEqual(statusView(wiz, null, "other", true), Object.assign(blankStatus(), {}));
});

test("the treasury: coins in and out, never below zero; items added up and taken", () => {
  let r = applyTreasury(null, { coins: { gp: 50, sp: 12 }, note: "sold the bell" });
  assert.deepEqual(r.treasury.coins, { gp: 50, sp: 12 });
  assert.equal(r.text, "+50 gp, +12 sp — sold the bell");
  r = applyTreasury(r.treasury, { coins: { gp: -20 }, add: { name: "Potion of Healing", qty: 2 } });
  assert.equal(r.treasury.coins.gp, 30);
  r = applyTreasury(r.treasury, { add: { name: "potion of healing" } });
  assert.deepEqual(r.treasury.items, [{ name: "Potion of Healing", qty: 3 }]);
  r = applyTreasury(r.treasury, { take: { name: "Potion of Healing", qty: 3 } });
  assert.deepEqual(r.treasury.items, []);
  assert.throws(() => applyTreasury(r.treasury, { coins: { gp: -31 } }), /only has 30 gp/);
  assert.throws(() => applyTreasury(r.treasury, { take: { name: "Wand" } }), /no Wand/);
  assert.throws(() => applyTreasury(r.treasury, {}), /Nothing/);
});
