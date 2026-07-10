import { bandClass } from "./cefr";
import type { SeedItem } from "./seed";

export interface PopoverData {
  surface: string;
  lemma?: string | null;
  upos?: string | null;
  gloss?: string | null;
  band?: string | null;
}

export interface PopoverCallbacks {
  onCollect: (item: SeedItem) => void;
  isCollected: (item: SeedItem) => boolean;
}

/** A single interactive popover reused for every token: lemma · POS · CEFR ·
 *  gloss, plus a ＋ "collect" button (M6). A short hide delay bridges the gap
 *  between the word and the popover so the button is clickable. */
export class Popover {
  private readonly el: HTMLDivElement;
  private hideTimer: number | undefined;

  constructor(private readonly cb: PopoverCallbacks) {
    this.el = document.createElement("div");
    this.el.className = "rz-popover";
    this.el.hidden = true;
    this.el.addEventListener("mouseenter", () => this.cancelHide());
    this.el.addEventListener("mouseleave", () => this.hide());
    document.body.appendChild(this.el);
  }

  show(anchor: HTMLElement, data: PopoverData, item: SeedItem): void {
    this.cancelHide();
    this.el.replaceChildren();

    const head = document.createElement("div");
    head.className = "rz-pop-head";
    head.appendChild(span("rz-pop-lemma", data.lemma || data.surface));
    if (data.upos) head.appendChild(span("rz-pop-pos", data.upos));
    const bc = bandClass(data.band);
    if (bc) head.appendChild(span(`rz-badge ${bc}`, data.band as string));
    this.el.appendChild(head);

    const gloss = document.createElement("div");
    gloss.className = data.gloss ? "rz-pop-gloss" : "rz-pop-gloss rz-faint";
    gloss.textContent = data.gloss ?? "— keine Glosse";
    this.el.appendChild(gloss);

    const collect = document.createElement("button");
    collect.className = "rz-collect";
    collect.type = "button";
    const paint = () => {
      const on = this.cb.isCollected(item);
      collect.textContent = on ? "✓ gesammelt" : "＋ sammeln";
      collect.setAttribute("aria-pressed", on ? "true" : "false");
    };
    paint();
    collect.addEventListener("click", () => {
      this.cb.onCollect(item);
      paint();
    });
    this.el.appendChild(collect);

    this.el.hidden = false;
    const r = anchor.getBoundingClientRect();
    const top = window.scrollY + r.top - this.el.offsetHeight - 8;
    const left = window.scrollX + r.left + r.width / 2 - this.el.offsetWidth / 2;
    this.el.style.top = `${Math.max(8, top)}px`;
    this.el.style.left = `${Math.max(8, left)}px`;
  }

  scheduleHide(): void {
    this.cancelHide();
    this.hideTimer = window.setTimeout(() => this.hide(), 220);
  }

  private cancelHide(): void {
    if (this.hideTimer !== undefined) {
      clearTimeout(this.hideTimer);
      this.hideTimer = undefined;
    }
  }

  hide(): void {
    this.cancelHide();
    this.el.hidden = true;
  }
}

function span(className: string, text: string): HTMLSpanElement {
  const s = document.createElement("span");
  s.className = className;
  s.textContent = text;
  return s;
}
