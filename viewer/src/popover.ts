import { bandClass } from "./cefr";

export interface PopoverData {
  surface: string;
  lemma?: string | null;
  upos?: string | null;
  gloss?: string | null;
  band?: string | null;
}

/** A single floating popover reused for every token (lemma · POS · CEFR · gloss). */
export class Popover {
  private readonly el: HTMLDivElement;

  constructor() {
    this.el = document.createElement("div");
    this.el.className = "rz-popover";
    this.el.hidden = true;
    document.body.appendChild(this.el);
  }

  show(anchor: HTMLElement, d: PopoverData): void {
    const bc = bandClass(d.band);
    const head =
      `<span class="rz-pop-lemma">${esc(d.lemma || d.surface)}</span>` +
      (d.upos ? `<span class="rz-pop-pos">${esc(d.upos)}</span>` : "") +
      (bc ? `<span class="rz-badge ${bc}">${esc(d.band as string)}</span>` : "");
    const gloss = d.gloss
      ? `<div class="rz-pop-gloss">${esc(d.gloss)}</div>`
      : `<div class="rz-pop-gloss rz-faint">— keine Glosse</div>`;
    this.el.innerHTML = `<div class="rz-pop-head">${head}</div>${gloss}`;
    this.el.hidden = false;

    const r = anchor.getBoundingClientRect();
    const top = window.scrollY + r.top - this.el.offsetHeight - 8;
    const left = window.scrollX + r.left + r.width / 2 - this.el.offsetWidth / 2;
    this.el.style.top = `${Math.max(8, top)}px`;
    this.el.style.left = `${Math.max(8, left)}px`;
  }

  hide(): void {
    this.el.hidden = true;
  }
}

function esc(s: string): string {
  return s.replace(
    /[&<>"]/g,
    (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c] as string,
  );
}
