import { Popover } from "./popover";
import { activeSentenceIndex, activeTokenStart, tokenTimingByStart } from "./sync";
import type { ListenDocument } from "./types";

export interface KaraokeHandle {
  /** Update highlights for the current audio time (seconds). */
  update(t: number): void;
}

const TIMED_KINDS = new Set(["word", "number"]);

/** Render the document into `root` and return a handle that syncs highlights to
 *  the audio clock. `onSeek(seconds)` fires when a timed word is clicked. */
export function renderKaraoke(
  doc: ListenDocument,
  root: HTMLElement,
  onSeek: (seconds: number) => void,
): KaraokeHandle {
  root.innerHTML = "";
  const timingByStart = tokenTimingByStart(doc.timings);
  const glossByLemma = new Map<string, string>();
  for (const v of doc.vocab ?? []) {
    if (v.lemma && v.gloss?.text) glossByLemma.set(v.lemma, v.gloss.text);
  }

  const popover = new Popover();
  const tokenEls = new Map<number, HTMLElement>();
  const sentenceEls: HTMLElement[] = [];

  doc.sentences.forEach((sent, si) => {
    const p = document.createElement("p");
    p.className = "rz-sentence";
    p.dataset.si = String(si);

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
      span.addEventListener("mouseenter", () =>
        popover.show(span, {
          surface: tok.text,
          lemma: tok.lemma,
          upos: tok.upos,
          band: tok.band,
          gloss: tok.lemma ? (glossByLemma.get(tok.lemma) ?? null) : null,
        }),
      );
      span.addEventListener("mouseleave", () => popover.hide());
      p.appendChild(span);
    });

    root.appendChild(p);
    sentenceEls.push(p);
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
        if (activeSi !== null) sentenceEls[activeSi]?.classList.remove("is-current");
        if (si !== null) {
          const el = sentenceEls[si];
          el?.classList.add("is-current");
          el?.scrollIntoView({ block: "center", behavior: "smooth" });
        }
        activeSi = si;
      }
    },
  };
}
