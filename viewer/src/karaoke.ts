import { bandClass, CEFR_BANDS } from "./cefr";
import { Popover } from "./popover";
import type { SeedItem } from "./seed";
import { activeSentenceIndex, activeTokenStart, tokenTimingByStart } from "./sync";
import type { ListenDocument, Token } from "./types";

export interface KaraokeHandle {
  /** Update highlights for the current audio time (seconds). */
  update(t: number): void;
}

export interface RenderOptions {
  onSeek: (seconds: number) => void;
  onCollect: (item: SeedItem) => void;
  isCollected: (item: SeedItem) => boolean;
}

const TIMED_KINDS = new Set(["word", "number"]);

/** Render the document as a Studio-style reading view (sentence rows with a
 *  per-sentence Listen button and an optional translation), and return a handle
 *  that syncs highlights to the audio clock. `onSeek(seconds)` fires on a word
 *  click or a sentence's Listen button; the popover's ＋ calls `onCollect`. */
export function renderKaraoke(
  doc: ListenDocument,
  root: HTMLElement,
  opts: RenderOptions,
): KaraokeHandle {
  const onSeek = opts.onSeek;
  root.innerHTML = "";
  root.dataset.translate = "off";

  const timingByStart = tokenTimingByStart(doc.timings);
  const segStartBySi = new Map<number, number>();
  for (const s of doc.timings?.segments ?? []) segStartBySi.set(s.sentence_index, s.t_start);
  // Key glosses case-insensitively so a token joins whether it carries a lemma
  // (morphology ran) or only a surface form (segmentation-only enrichment).
  const glossByKey = new Map<string, string>();
  for (const v of doc.vocab ?? []) {
    if (v.lemma && v.gloss?.text) glossByKey.set(v.lemma.toLowerCase(), v.gloss.text);
  }

  root.appendChild(buildHeader(doc, root));

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
        if (activeSi !== null) rowEls[activeSi]?.classList.remove("is-current");
        if (si !== null) {
          const el = rowEls[si];
          el?.classList.add("is-current");
          el?.scrollIntoView({ block: "center", behavior: "smooth" });
        }
        activeSi = si;
      }
    },
  };
}

/** The reader header: overall CEFR badge, language direction, translation toggle. */
function buildHeader(doc: ListenDocument, root: HTMLElement): HTMLElement {
  const head = document.createElement("div");
  head.className = "rz-reader-head";

  const meta = document.createElement("div");
  meta.className = "rz-reader-meta";
  const band = overallBand(doc);
  if (band) {
    const badge = document.createElement("span");
    badge.className = `rz-badge ${bandClass(band)}`;
    badge.textContent = band;
    meta.appendChild(badge);
  }
  const dir = document.createElement("span");
  dir.className = "rz-faint";
  dir.textContent = `${doc.lang ?? "bg"} → de`;
  meta.appendChild(dir);

  const toggle = document.createElement("button");
  toggle.className = "rz-btn rz-translate";
  toggle.type = "button";
  toggle.setAttribute("aria-pressed", "false");
  toggle.textContent = "Show translation";
  toggle.addEventListener("click", () => {
    const on = root.dataset.translate === "on";
    root.dataset.translate = on ? "off" : "on";
    toggle.setAttribute("aria-pressed", on ? "false" : "true");
    toggle.textContent = on ? "Show translation" : "Hide translation";
  });

  head.append(meta, toggle);
  return head;
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

/** Overall band = the document estimate if present, else the hardest word band. */
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
