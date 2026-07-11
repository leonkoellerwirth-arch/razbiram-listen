import { bandClass, CEFR_BANDS } from "./cefr";
import { Popover } from "./popover";
import type { SeedItem } from "./seed";
import { activeSentenceIndex, activeTokenStart, tokenTimingByStart } from "./sync";
import type { ListenDocument, Token } from "./types";

export interface KaraokeHandle {
  /** Update highlights for the current audio time (seconds). */
  update(t: number): void;
  /** Filter sentence rows by query string (empty = show all). */
  filter(query: string): void;
}

export interface RenderOptions {
  onSeek: (seconds: number) => void;
  onCollect: (item: SeedItem) => void;
  isCollected: (item: SeedItem) => boolean;
}

const TIMED_KINDS = new Set(["word", "number"]);

/** Populate the reader-meta element with the CEFR badge + language direction.
 *  Called from main.ts after the document loads; does not touch #reader itself. */
export function renderReaderMeta(doc: ListenDocument, container: HTMLElement): void {
  container.innerHTML = "";
  const band = overallBand(doc);
  if (band) {
    const badge = document.createElement("span");
    badge.className = `rz-badge ${bandClass(band)}`;
    badge.textContent = band;
    container.appendChild(badge);
  }
  const glossLang = doc.sentences.find((s) => s.gloss?.text)?.gloss?.lang ?? null;
  const dir = document.createElement("span");
  dir.className = "rz-faint";
  dir.textContent = glossLang ? `${doc.lang ?? "bg"} → ${glossLang}` : (doc.lang ?? "bg");
  container.appendChild(dir);
}

/** Render the document as a Studio-style reading view (sentence rows with a
 *  per-sentence Listen button and an optional translation), and return a handle
 *  that syncs highlights to the audio clock. `onSeek(seconds)` fires on a word
 *  click or a sentence's Listen button; the popover's ＋ calls `onCollect`.
 *
 *  The reader header (CEFR badge, lang direction) is NOT rendered here — call
 *  `renderReaderMeta(doc, container)` separately to populate `#reader-meta`. */
export function renderKaraoke(
  doc: ListenDocument,
  root: HTMLElement,
  opts: RenderOptions,
): KaraokeHandle {
  const onSeek = opts.onSeek;
  root.innerHTML = "";
  // data-translate is controlled externally by the unified lang-select in main.ts

  const timingByStart = tokenTimingByStart(doc.timings);
  const segStartBySi = new Map<number, number>();
  for (const s of doc.timings?.segments ?? []) segStartBySi.set(s.sentence_index, s.t_start);
  // Key glosses case-insensitively so a token joins whether it carries a lemma
  // (morphology ran) or only a surface form (segmentation-only enrichment).
  const glossByKey = new Map<string, string>();
  for (const v of doc.vocab ?? []) {
    if (v.lemma && v.gloss?.text) glossByKey.set(v.lemma.toLowerCase(), v.gloss.text);
  }

  const popover = new Popover({ onCollect: opts.onCollect, isCollected: opts.isCollected });
  const tokenEls = new Map<number, HTMLElement>();
  const rowEls: HTMLElement[] = [];

  doc.sentences.forEach((sent, si) => {
    const row = document.createElement("div");
    row.className = "rz-srow";
    row.dataset.si = String(si);

    const listen = document.createElement("button");
    listen.className = "rz-listen";
    listen.type = "button";
    listen.setAttribute("aria-label", "Play from this sentence");
    listen.textContent = "▶";
    const segStart = segStartBySi.get(si);
    if (segStart !== undefined) listen.addEventListener("click", () => onSeek(segStart));
    else listen.disabled = true;

    const body = document.createElement("div");
    body.className = "rz-sbody";

    const p = document.createElement("p");
    p.className = "rz-sentence";
    sent.tokens.forEach((tok, ti) => {
      if (ti > 0 && tok.kind !== "punct") p.appendChild(document.createTextNode(" "));
      if (!TIMED_KINDS.has(tok.kind)) {
        p.appendChild(document.createTextNode(tok.text));
        return;
      }
      const span = document.createElement("span");
      span.className = "rz-tok";
      span.textContent = tok.text;
      const timing = timingByStart.get(tok.start);
      if (timing) {
        span.classList.add("is-timed");
        span.addEventListener("click", () => onSeek(timing.t_start));
        tokenEls.set(tok.start, span);
      }
      const gloss = glossByKey.get((tok.lemma || tok.text).toLowerCase()) ?? null;
      const item = seedItem(tok, gloss);
      span.addEventListener("mouseenter", () =>
        popover.show(
          span,
          { surface: tok.text, lemma: tok.lemma, upos: tok.upos, band: tok.band, gloss },
          item,
        ),
      );
      span.addEventListener("mouseleave", () => popover.scheduleHide());
      p.appendChild(span);
    });
    body.appendChild(p);

    if (sent.gloss?.text) {
      const tr = document.createElement("p");
      tr.className = "rz-translation";
      tr.textContent = sent.gloss.text;
      body.appendChild(tr);
    }

    row.append(listen, body);
    root.appendChild(row);
    rowEls.push(row);
  });

  const tokens = doc.timings?.tokens ?? [];
  const segments = doc.timings?.segments ?? [];
  let activeStart: number | null = null;
  let activeSi: number | null = null;

  return {
    update(t: number): void {
      const start = activeTokenStart(tokens, t);
      if (start !== activeStart) {
        if (activeStart !== null) tokenEls.get(activeStart)?.classList.remove("is-active");
        if (start !== null) tokenEls.get(start)?.classList.add("is-active");
        activeStart = start;
      }

      const si = activeSentenceIndex(segments, t);
      if (si !== activeSi) {
        // Clear classes from old active row and its spotlight neighbours
        if (activeSi !== null) {
          rowEls[activeSi]?.classList.remove("is-current");
          for (let d = 1; d <= 2; d++) {
            rowEls[activeSi - d]?.classList.remove(`is-near-${d}`);
            rowEls[activeSi + d]?.classList.remove(`is-near-${d}`);
          }
        }

        if (si !== null) {
          const activeEl = rowEls[si];
          activeEl?.classList.add("is-current");
          activeEl?.scrollIntoView({ block: "center", behavior: "smooth" });
          for (let d = 1; d <= 2; d++) {
            rowEls[si - d]?.classList.add(`is-near-${d}`);
            rowEls[si + d]?.classList.add(`is-near-${d}`);
          }
          root.classList.add("has-active");
        } else {
          root.classList.remove("has-active");
        }

        activeSi = si;
      }
    },

    filter(query: string): void {
      const q = query.toLowerCase().trim();
      for (const row of rowEls) {
        const text =
          row.querySelector(".rz-sentence")?.textContent?.toLowerCase() ?? "";
        row.hidden = q !== "" && !text.includes(q);
      }
    },
  };
}

function seedItem(tok: Token, gloss: string | null): SeedItem {
  return {
    surface: tok.text,
    lemma: tok.lemma || tok.text,
    upos: tok.upos ?? null,
    band: tok.band ?? null,
    gloss,
  };
}

/** Overall band = the hardest word band present in the document. */
function overallBand(doc: ListenDocument): string | null {
  let best = -1;
  for (const s of doc.sentences) {
    for (const tok of s.tokens) {
      const i = tok.band ? CEFR_BANDS.indexOf(tok.band as (typeof CEFR_BANDS)[number]) : -1;
      if (i > best) best = i;
    }
  }
  return best >= 0 ? CEFR_BANDS[best] : null;
}
