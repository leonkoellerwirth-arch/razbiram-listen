import { describe, expect, it } from "vitest";
import { SeedBasket, type SeedItem, toCrowdAnkiDeck, toRazbiramSeed } from "../src/seed";

const item = (over: Partial<SeedItem> = {}): SeedItem => ({
  surface: "времето",
  lemma: "време",
  upos: "NOUN",
  band: "A2",
  gloss: "das Wetter",
  ...over,
});

/** Mirror of razbiram-anki's CrowdAnki shape check (loadDeckJson) — the roundtrip
 *  target: what we export must parse as a CrowdAnki deck over there. */
function isCrowdAnkiDeck(d: unknown): boolean {
  if (d === null || typeof d !== "object") return false;
  const r = d as Record<string, unknown>;
  return (
    r.__type__ === "Deck" ||
    Array.isArray(r.notes) ||
    Array.isArray(r.note_models) ||
    Array.isArray(r.children)
  );
}

describe("SeedBasket", () => {
  it("dedupes by lemma and toggles", () => {
    const b = new SeedBasket();
    b.add(item());
    b.add(item({ surface: "Времето" })); // same lemma → no duplicate
    expect(b.size).toBe(1);
    expect(b.has(item())).toBe(true);
    b.toggle(item());
    expect(b.size).toBe(0);
  });

  it("clears", () => {
    const b = new SeedBasket();
    b.add(item());
    b.add(item({ lemma: "кафе", surface: "кафе", gloss: "Kaffee" }));
    expect(b.size).toBe(2);
    b.clear();
    expect(b.size).toBe(0);
  });
});

describe("toRazbiramSeed", () => {
  it("produces the seed contract", () => {
    const seed = toRazbiramSeed([item()], { lang: "bg", glossLang: "de" });
    expect(seed.kind).toBe("razbiram-seed");
    expect(seed.lang).toBe("bg");
    expect(seed.items).toHaveLength(1);
    expect(seed.items[0]).toMatchObject({ lemma: "време", gloss: "das Wetter", band: "A2" });
  });
});

describe("toCrowdAnkiDeck (roundtrip → razbiram-anki)", () => {
  it("emits a valid CrowdAnki deck that razbiram-anki would accept", () => {
    const deck = toCrowdAnkiDeck([item(), item({ lemma: "кафе", surface: "кафе", gloss: "Kaffee", band: "A1" })], "demo seed");
    expect(isCrowdAnkiDeck(deck)).toBe(true);

    const d = deck as Record<string, any>;
    expect(d.__type__).toBe("Deck");
    expect(d.note_models[0].flds.map((f: any) => f.name)).toEqual(["Front", "Back"]);
    expect(d.notes).toHaveLength(2);
    // Front = lemma, Back = gloss.
    expect(d.notes[0].fields).toEqual(["време", "das Wetter"]);
    expect(d.notes[0].tags).toContain("A2");
    // Every note references the deck's single model.
    for (const n of d.notes) expect(n.note_model_uuid).toBe(d.note_models[0].crowdanki_uuid);
  });

  it("gives stable, distinct guids per lemma", () => {
    const deck = toCrowdAnkiDeck([item(), item({ lemma: "кафе", surface: "кафе" })], "x") as Record<string, any>;
    const again = toCrowdAnkiDeck([item()], "x") as Record<string, any>;
    expect(deck.notes[0].guid).toBe(again.notes[0].guid); // stable
    expect(deck.notes[0].guid).not.toBe(deck.notes[1].guid); // distinct
  });

  it("uses an empty back when a word has no gloss", () => {
    const deck = toCrowdAnkiDeck([item({ gloss: null })], "x") as Record<string, any>;
    expect(deck.notes[0].fields[1]).toBe("");
  });
});
