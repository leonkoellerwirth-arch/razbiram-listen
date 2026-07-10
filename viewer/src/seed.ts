// Seed export (M6): collect vocabulary from the reading view and export it in two
// formats — a razbiram Seed JSON (for razbiram.com seeding) and a CrowdAnki
// deck.json (razbiram-anki-compatible → straight to a deck). Pure & unit-tested.

export interface SeedItem {
  surface: string;
  lemma: string;
  upos: string | null;
  band: string | null;
  gloss: string | null;
}

/** A deduplicated collection of words the learner picked, keyed by lemma. */
export class SeedBasket {
  private readonly items = new Map<string, SeedItem>();

  private key(i: SeedItem): string {
    return (i.lemma || i.surface).toLowerCase();
  }
  add(i: SeedItem): void {
    this.items.set(this.key(i), i);
  }
  remove(i: SeedItem): void {
    this.items.delete(this.key(i));
  }
  toggle(i: SeedItem): void {
    if (this.has(i)) this.remove(i);
    else this.add(i);
  }
  has(i: SeedItem): boolean {
    return this.items.has(this.key(i));
  }
  clear(): void {
    this.items.clear();
  }
  get size(): number {
    return this.items.size;
  }
  list(): SeedItem[] {
    return [...this.items.values()];
  }
}

export const SEED_SCHEMA_VERSION = "1.0.0";

export interface RazbiramSeed {
  schemaVersion: string;
  kind: "razbiram-seed";
  lang: string;
  glossLang: string;
  items: Array<{
    lemma: string;
    surface: string;
    upos: string | null;
    band: string | null;
    gloss: string | null;
  }>;
}

/** razbiram Seed JSON — the lightweight vocab-seed format for razbiram.com. */
export function toRazbiramSeed(
  items: SeedItem[],
  opts: { lang?: string; glossLang?: string } = {},
): RazbiramSeed {
  return {
    schemaVersion: SEED_SCHEMA_VERSION,
    kind: "razbiram-seed",
    lang: opts.lang ?? "bg",
    glossLang: opts.glossLang ?? "de",
    items: items.map((i) => ({
      lemma: i.lemma,
      surface: i.surface,
      upos: i.upos,
      band: i.band,
      gloss: i.gloss,
    })),
  };
}

const MODEL_UUID = "rz-listen-basic-0001";

/** A CrowdAnki deck.json — exactly the shape razbiram-anki emits and razbiram.com
 *  reads, so the collected words go straight to a deck (front = lemma, back = gloss). */
export function toCrowdAnkiDeck(items: SeedItem[], name: string): unknown {
  return {
    __type__: "Deck",
    crowdanki_uuid: `rz-listen-seed-${hash(name)}`,
    name,
    desc: "Seed exported from razbiram-listen.",
    media_files: [],
    note_models: [
      {
        __type__: "NoteModel",
        crowdanki_uuid: MODEL_UUID,
        name: "razbiram Basic",
        css: ".card{font-family:sans-serif;font-size:20px;text-align:center;}",
        flds: [
          { name: "Front", ord: 0 },
          { name: "Back", ord: 1 },
        ],
        tmpls: [
          { name: "Card 1", ord: 0, qfmt: "{{Front}}", afmt: "{{FrontSide}}<hr id=answer>{{Back}}" },
        ],
      },
    ],
    notes: items.map((i) => ({
      __type__: "Note",
      guid: `rzl-${hash(i.lemma || i.surface)}`,
      note_model_uuid: MODEL_UUID,
      fields: [i.lemma || i.surface, i.gloss ?? ""],
      tags: ["razbiram-listen", ...(i.band ? [i.band] : []), ...(i.upos ? [i.upos] : [])],
    })),
    children: [],
  };
}

/** Deterministic FNV-1a hash → 8 hex chars (stable guids, no crypto needed). */
function hash(s: string): string {
  let h = 2166136261 >>> 0;
  for (let k = 0; k < s.length; k++) {
    h ^= s.charCodeAt(k);
    h = Math.imul(h, 16777619);
  }
  return (h >>> 0).toString(16).padStart(8, "0");
}
