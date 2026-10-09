// A CCC5e export (.ccc5e) as a Party page card - the same card tools/import_ccc5e.py makes, field for
// field (tests/smoke.py checks the two agree on the same file). The players' worker uses it when a
// player imports their character online; the DM's import at home uses the Python one.

const ABBR = { str: "Str", dex: "Dex", con: "Con", int: "Int", wis: "Wis", cha: "Cha" };
const ORDINAL = { 1: "1st", 2: "2nd", 3: "3rd" };

const signed = (n) => { n = parseInt(n, 10) || 0; return n >= 0 ? `+${n}` : `−${-n}`; };
const ordinal = (n) => ORDINAL[n] || `${n}th`;
const feet = (s) => String(s || "").trim().replace(/(\d)\s*ft\./g, "$1 ft.");
const text = (s) => String(s == null ? "" : s).split(/\s+/).filter(Boolean).join(" ");
const empty = (v) => v == null || v === "" || (Array.isArray(v) && !v.length) ||
  (typeof v === "object" && !Array.isArray(v) && !Object.keys(v).length);
const compact = (o) => Object.fromEntries(Object.entries(o).filter(([, v]) => !empty(v)));

export function joinRace(race, subrace) {
  race = String(race || "").trim(); subrace = String(subrace || "").trim();
  if (!subrace || race.toLowerCase().includes(subrace.toLowerCase())) return race;
  if (subrace.toLowerCase().includes(race.toLowerCase())) return subrace;
  return `${subrace} ${race}`;
}

export function parse(raw, name = "the file") {
  let data;
  try { data = JSON.parse(String(raw).replace(/^﻿/, "")); } catch (e) {
    throw new Error(`${name} isn't a CCC5e character (${e.message}).`);
  }
  if (!data || typeof data !== "object" || Array.isArray(data) || !(data.Name || data.Sheet)) {
    throw new Error(`${name} isn't a CCC5e character (.ccc5e).`);
  }
  return data;
}

export function card(data, today = new Date().toISOString().slice(0, 10)) {
  const s = data.Sheet;
  if (!s || typeof s !== "object") return basics(data, today);
  const classes = s.classes || [];
  let cls;
  if (classes.length > 1) {
    cls = classes.map((c) => `${c.name} ${c.level}` + (c.subclass ? ` (${c.subclass})` : "")).join(" / ");
  } else {
    cls = s.class || "";
    if (s.subclass) cls = `${cls} (${s.subclass})`;
  }
  const armor = [s.armor, s.shield].filter(Boolean).join(", ");
  const speed = s.speed || {};
  const speeds = [feet(speed.walk)].concat(["fly", "swim", "climb"].filter((k) => speed[k]).map((k) => `${k} ${feet(speed[k])}`));
  const abilities = s.abilities || {};
  const saves = Object.entries(abilities).filter(([k, v]) => v.saveProf && ABBR[k]).map(([k, v]) => `${ABBR[k]} ${signed(v.save)}`).join(", ");
  const skills = (s.skills || []).slice().sort((a, b) => (a.name < b.name ? -1 : a.name > b.name ? 1 : 0))
    .filter((x) => x.prof || x.expert).map((x) => `${x.name} ${signed(x.total)}`).join(", ");

  const entry = (f) => ({ name: f.name + (f.usage ? ` (${f.usage})` : ""), text: text(f.text) });
  const features = [], actions = [], bonus = [], reactions = [];
  for (const a of s.attacks || []) {
    const bits = [a.toHit ? `${a.toHit} to hit` : "", a.range ? `range ${a.range}` : ""].filter(Boolean).join(", ");
    let line = (bits ? `*Attack:* ${bits}. ` : "") + (a.damage ? `*Hit:* ${a.damage}.` : "");
    if (a.notes) line += ` ${a.notes}`;
    actions.push({ name: a.name, text: line.trim() });
  }
  for (const f of s.features || []) {
    ({ Action: actions, "Bonus Action": bonus, Reaction: reactions }[f.action || ""] || features).push(entry(f));
  }
  if (s.backgroundFeature) features.push({ name: s.backgroundFeature, text: text(s.backgroundFeatureText) });

  const byClass = Object.fromEntries((s.spells || []).map((sp) => [sp.class, sp]));
  const casting = [];
  for (const c of s.spellcasting || []) {
    const lists = byClass[c.name] || {};
    const slots = {};
    (c.slots || []).forEach((n, lvl) => { if (lvl && n) slots[lvl] = n; });
    const e = {
      name: c.name, ability: c.ability, save_dc: c.saveDc, attack: c.attackBonus, slots,
      cantrips: (lists.cantrips || []).map((x) => x.name),
      spells: (lists.spells || []).slice().sort((a, b) => a.level - b.level || (a.name < b.name ? -1 : a.name > b.name ? 1 : 0))
        .map((x) => Object.assign({ name: x.name, level: x.level }, x.prepared || x.alwaysPrepared ? { prepared: true } : {})),
    };
    if (c.pact && c.pactSlotCount) { e.slots = { [c.pactSlotLevel]: c.pactSlotCount }; e.pact = true; }
    casting.push(compact(e));
  }
  for (const g of s.innateSpells || []) {
    casting.push(compact({ name: `Innate (${g.sources})`, ability: g.ability, save_dc: g.saveDc, attack: g.attackBonus,
      spells: (g.spells || []).map((x) => ({ name: x.name, level: x.level })) }));
  }

  const inventory = (s.equipment || []).map((i) => {
    const item = { name: i.name };
    if ((i.quantity || 1) !== 1) item.qty = i.quantity;
    for (const flag of ["equipped", "attuned", "magic"]) if (i[flag]) item[flag] = true;
    return item;
  });
  const money = compact(Object.fromEntries(Object.entries(s.currency || {}).filter(([, v]) => v)));

  const p = s.persona || {};
  const looks = [p.age ? `${p.age} years` : "", p.gender, p.height, p.weight, p.eyes ? `${p.eyes} eyes` : "",
                 p.skin ? `${p.skin} skin` : "", p.hair ? `${p.hair} hair` : ""].filter(Boolean).join(", ");
  const persona = compact({
    traits: (p.traits || []).map(text).filter(Boolean), ideal: text(p.ideal), bond: text(p.bond), flaw: text(p.flaw),
    appearance: looks, backstory: String(p.backstory || "").trim(), allies: text(p.allies), deity: text(p.deity),
    alignment: text(s.alignment),
  });
  const hp = s.hp || {};
  const profs = Object.fromEntries(Object.entries(s.proficiencies || {}).filter(([k, v]) => v && k !== "languages"));
  return compact({
    character: s.name || data.Name,
    race: joinRace(s.race, s.subrace), class: cls, background: s.background, level: s.level,
    ac: s.ac, ac_note: armor ? armor.toLowerCase() : "",
    hp: hp.max, hp_formula: hp.hitDice,
    speed: speeds.filter(Boolean).join(", "),
    initiative: s.initiative, passive_perception: s.passivePerception,
    abilities: Object.fromEntries(Object.entries(abilities).filter(([k]) => ABBR[k]).map(([k, v]) => [k, v.score])),
    saves, skills, resistances: s.resistances || "", senses: s.senses || "",
    languages: (s.proficiencies || {}).languages || "", proficiencies: profs,
    features, actions, bonus_actions: bonus, reactions,
    spellcasting: casting, inventory, currency: money, persona,
    source: { from: "CCC5e", imported: today },
  });
}

export function basics(data, today = new Date().toISOString().slice(0, 10)) {
  const race = joinRace(data.RaceDisplayName, data.SubraceDisplayName);
  let cls = data.ClassDisplayName || "";
  if (data.SubclassDisplayName) cls = `${cls} (${data.SubclassDisplayName})`;
  const multi = data.MulticlassEntries || [];
  if (multi.length) {
    const main = (data.Level || 0) - multi.reduce((n, m) => n + (m.Level || 0), 0);
    cls = [`${data.ClassDisplayName} ${main}`].concat(multi.map((m) => `${m.ClassDisplayName} ${m.Level}`)).join(" / ");
  }
  return compact({ character: data.Name, race, class: cls, background: data.BackgroundDisplayName, level: data.Level,
    source: { from: "CCC5e", imported: today } });
}

// What an import never replaces.
export const KEEP = ["player", "email", "note", "private"];

export function merge(old, fresh) {
  const out = Object.assign({}, fresh);
  for (const k of KEEP) if (old && !empty(old[k])) out[k] = old[k];
  if (old && old.portrait && !out.portrait) out.portrait = old.portrait;
  return out;
}

// [[field, before, after]] for the import preview - the same list tools/import_ccc5e.py changes() makes.
export function changes(old, fresh) {
  const out = [];
  for (const key of ["race", "class", "background", "level", "ac", "hp", "speed", "initiative", "passive_perception",
    "saves", "skills", "senses", "languages", "resistances"]) {
    if (String(old[key] ?? "") !== String(fresh[key] ?? "")) out.push([key, old[key] ?? "", fresh[key] ?? ""]);
  }
  const ab = (a) => Object.entries(a || {}).map(([k, v]) => `${k.toUpperCase()} ${v}`).join(", ");
  if (JSON.stringify(old.abilities || null) !== JSON.stringify(fresh.abilities || null)) {
    out.push(["abilities", ab(old.abilities), ab(fresh.abilities)]);
  }
  const names = (l) => new Set((l || []).map((e) => e.name));
  const minus = (a, b) => [...a].filter((x) => !b.has(x)).sort();
  for (const key of ["features", "actions", "bonus_actions", "reactions", "inventory"]) {
    const before = names(old[key]), after = names(fresh[key]);
    if (minus(after, before).length) out.push([key, "", "+ " + minus(after, before).join(", ")]);
    if (minus(before, after).length) out.push([key, "- " + minus(before, after).join(", "), ""]);
  }
  const sp = (c) => new Set((c || []).flatMap((e) => (e.spells || []).map((x) => x.name).concat(e.cantrips || [])));
  const sb = sp(old.spellcasting), sa = sp(fresh.spellcasting);
  if (minus(sa, sb).length) out.push(["spells", "", "+ " + minus(sa, sb).join(", ")]);
  if (minus(sb, sa).length) out.push(["spells", "- " + minus(sb, sa).join(", "), ""]);
  for (const key of ["currency", "persona"]) {
    if (JSON.stringify(old[key] || null) !== JSON.stringify(fresh[key] || null)) {
      out.push([key, old[key] ? "changed" : "", fresh[key] ? "updated" : "(none)"]);
    }
  }
  return out;
}
