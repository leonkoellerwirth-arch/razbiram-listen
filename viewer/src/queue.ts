// The queue & library sidebar: active jobs (with live progress) on top, the saved
// library below. Pure helpers here are unit-tested; the renderers build DOM.
import type { Job, LibraryEntry } from "./types";

export function isActive(job: Job): boolean {
  return job.status === "queued" || job.status === "running";
}

export function hasActive(jobs: Job[]): boolean {
  return jobs.some(isActive);
}

/** Jobs shown in the queue: active + failed (done/cancelled ones drop off). */
export function queueJobs(jobs: Job[]): Job[] {
  return jobs.filter((j) => j.status !== "done" && j.status !== "cancelled");
}

/** Ids that transitioned to "done" between two snapshots (for auto-open + refresh). */
export function newlyDone(prev: Job[], cur: Job[]): string[] {
  const wasDone = new Set(prev.filter((j) => j.status === "done").map((j) => j.id));
  return cur.filter((j) => j.status === "done" && !wasDone.has(j.id)).map((j) => j.id);
}

export function fmtDuration(seconds?: number | null): string {
  if (seconds == null || !isFinite(seconds)) return "";
  const s = Math.round(seconds);
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = String(s % 60).padStart(2, "0");
  return h > 0 ? `${h}:${String(m).padStart(2, "0")}:${sec}` : `${m}:${sec}`;
}

export interface JobProgress {
  label: string;
  fraction: number;
  indeterminate: boolean;
}

/** Map a job's stage/fraction to a bar label + width (mirrors the studio stages). */
export function jobProgress(job: Job): JobProgress {
  const pct = (f?: number | null) => `${Math.round((f ?? 0) * 100)}%`;
  if (job.status === "queued") return { label: "Wartet …", fraction: 0.02, indeterminate: false };
  if (job.status === "error") {
    return { label: job.error ?? "Fehler", fraction: 1, indeterminate: false };
  }
  const f = job.fraction ?? null;
  switch (job.stage) {
    case "transcribe":
      return { label: `Transkribiere … ${pct(f)}`, fraction: (f ?? 0) * 0.6, indeterminate: false };
    case "enrich":
      return f == null
        ? { label: "Analysiere …", fraction: 0.62, indeterminate: true }
        : { label: `Übersetze … ${pct(f)}`, fraction: 0.62 + f * 0.33, indeterminate: false };
    case "align":
      return { label: "Richte aus …", fraction: 0.96, indeterminate: false };
    case "done":
      return { label: "Fertig", fraction: 1, indeterminate: false };
    default:
      return { label: "Läuft …", fraction: 0.05, indeterminate: true };
  }
}

function el<T extends HTMLElement>(tag: string, className?: string, text?: string): T {
  const node = document.createElement(tag) as T;
  if (className) node.className = className;
  if (text != null) node.textContent = text;
  return node;
}

export interface JobHandlers {
  onCancel: (id: string) => void;
}

/** Render the active-jobs list into `container`; active jobs get a cancel ✕. */
export function renderJobs(container: HTMLElement, jobs: Job[], handlers?: JobHandlers): void {
  container.textContent = "";
  const shown = queueJobs(jobs);
  if (shown.length === 0) return;
  for (const job of shown) {
    const p = jobProgress(job);
    const row = el("div", `rz-job${job.status === "error" ? " is-error" : ""}`);
    const main = el("div", "rz-job-main");
    main.appendChild(el("div", "rz-job-title", job.title));
    main.appendChild(el("div", "rz-job-label", p.label));
    const track = el("div", "rz-progress-track");
    const bar = el<HTMLElement>("div", `rz-progress-bar${p.indeterminate ? " is-anim" : ""}`);
    if (!p.indeterminate) bar.style.width = `${Math.round(p.fraction * 100)}%`;
    track.appendChild(bar);
    main.appendChild(track);
    row.appendChild(main);
    if (handlers && isActive(job)) {
      const cancel = el<HTMLButtonElement>("button", "rz-icon-btn", "✕");
      cancel.type = "button";
      cancel.title = "Abbrechen";
      cancel.addEventListener("click", () => handlers.onCancel(job.id));
      row.appendChild(cancel);
    }
    container.appendChild(row);
  }
}

export interface LibraryHandlers {
  onOpen: (id: string) => void;
  onDelete: (id: string) => void;
  onRemoveAudio: (id: string) => void;
}

/** Render the saved-library list into `container`. */
export function renderLibrary(
  container: HTMLElement,
  entries: LibraryEntry[],
  handlers: LibraryHandlers,
): void {
  container.textContent = "";
  if (entries.length === 0) {
    container.appendChild(el("p", "rz-faint", "Noch nichts gespeichert."));
    return;
  }
  for (const entry of entries) {
    const row = el("div", "rz-lib");
    const open = el<HTMLButtonElement>("button", "rz-lib-open");
    open.type = "button";
    open.disabled = !entry.hasAudio;
    open.title = entry.hasAudio ? "Abspielen" : "Audio entfernt — nicht abspielbar";
    open.appendChild(el("span", "rz-lib-title", entry.title));
    const parts = [fmtDuration(entry.durationS), entry.mode === "enriched" ? "de/CEFR" : "Transkript"];
    open.appendChild(el("span", "rz-lib-meta", parts.filter(Boolean).join(" · ")));
    if (entry.hasAudio) open.addEventListener("click", () => handlers.onOpen(entry.id));

    const actions = el("div", "rz-lib-actions");
    if (entry.hasAudio) {
      const rm = el<HTMLButtonElement>("button", "rz-icon-btn", "⤓");
      rm.type = "button";
      rm.title = "Audio entfernen (Transkript behalten)";
      rm.addEventListener("click", () => handlers.onRemoveAudio(entry.id));
      actions.appendChild(rm);
    }
    const del = el<HTMLButtonElement>("button", "rz-icon-btn", "✕");
    del.type = "button";
    del.title = "Eintrag löschen";
    del.addEventListener("click", () => handlers.onDelete(entry.id));
    actions.appendChild(del);

    row.appendChild(open);
    row.appendChild(actions);
    container.appendChild(row);
  }
}
