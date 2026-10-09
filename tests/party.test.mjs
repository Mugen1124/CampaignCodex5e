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
