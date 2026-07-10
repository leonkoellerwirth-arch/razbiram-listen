import "./styles.css";
import { type KaraokeHandle, renderKaraoke } from "./karaoke";
import { ListenError, parseListenDocument } from "./loadListen";
import { Player } from "./player";
import { activeSentenceIndex } from "./sync";
import type { ListenDocument, SegmentTiming } from "./types";

function el<T extends HTMLElement>(id: string): T {
  const node = document.getElementById(id);
  if (!node) throw new Error(`missing #${id}`);
  return node as T;
}

const themeBtn = el<HTMLButtonElement>("theme");
const docInput = el<HTMLInputElement>("doc-input");
const audioInput = el<HTMLInputElement>("audio-input");
const loadNote = el<HTMLParagraphElement>("load-note");
const transport = el<HTMLElement>("transport");
const reader = el<HTMLElement>("reader");
const playBtn = el<HTMLButtonElement>("play");
const curEl = el<HTMLSpanElement>("cur");
const durEl = el<HTMLSpanElement>("dur");
const rate = el<HTMLInputElement>("rate");
const rateVal = el<HTMLSpanElement>("rate-val");
const loopBtn = el<HTMLButtonElement>("loop");

const player = new Player();
let doc: ListenDocument | null = null;
let audioName: string | null = null;
let audioUrl: string | null = null;
let karaoke: KaraokeHandle | null = null;
let rafId = 0;

// --- theme -------------------------------------------------------------------
function initTheme(): void {
  const dark = window.matchMedia("(prefers-color-scheme: dark)").matches;
  setTheme(dark ? "dark" : "light");
}
function setTheme(theme: "light" | "dark"): void {
  document.documentElement.setAttribute("data-theme", theme);
  themeBtn.textContent = theme === "dark" ? "☀ Light" : "☾ Dark";
}
themeBtn.addEventListener("click", () => {
  const next = document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
  setTheme(next);
});

// --- file loading ------------------------------------------------------------
docInput.addEventListener("change", async () => {
  const file = docInput.files?.[0];
  if (!file) return;
  try {
    doc = parseListenDocument(await file.text());
    maybeStart();
  } catch (err) {
    doc = null;
    note(err instanceof ListenError ? err.message : "Konnte die .listen.json nicht lesen.", true);
  }
});

audioInput.addEventListener("change", () => {
  const file = audioInput.files?.[0];
  if (!file) return;
  if (audioUrl) URL.revokeObjectURL(audioUrl);
  audioUrl = URL.createObjectURL(file);
  audioName = file.name;
  player.load(audioUrl);
  maybeStart();
});

function maybeStart(): void {
  if (!doc || !audioUrl) return;

  transport.hidden = false;
  reader.hidden = false;
  karaoke = renderKaraoke(doc, reader, (seconds) => {
    player.seek(seconds);
    if (player.paused) void player.play();
  });

  const expected = doc.audioRef?.filename;
  if (expected && audioName && expected !== audioName) {
    note(`Hinweis: Diese .listen.json wurde für „${expected}“ erzeugt, geladen ist „${audioName}“.`, true);
  } else {
    note(`Bereit — ${doc.sentences.length} Sätze geladen.`, false);
  }

  cancelAnimationFrame(rafId);
  tick();
}

// --- transport ---------------------------------------------------------------
playBtn.addEventListener("click", () => player.toggle());
player.audio.addEventListener("play", () => (playBtn.textContent = "⏸ Pause"));
player.audio.addEventListener("pause", () => (playBtn.textContent = "▶ Play"));
player.audio.addEventListener("loadedmetadata", () => (durEl.textContent = fmt(player.duration)));

rate.addEventListener("input", () => {
  const r = Number(rate.value);
  player.setRate(r);
  rateVal.textContent = `${r.toFixed(1)}×`;
});

loopBtn.addEventListener("click", () => {
  if (player.looping) {
    player.clearLoop();
    loopBtn.setAttribute("aria-pressed", "false");
    return;
  }
  const seg = currentSegment();
  if (!seg) {
    note("Zum Loopen zuerst einen Satz abspielen.", true);
    return;
  }
  player.setLoop(seg.t_start, seg.t_end);
  loopBtn.setAttribute("aria-pressed", "true");
});

function currentSegment(): SegmentTiming | null {
  const segs = doc?.timings?.segments;
  if (!segs) return null;
  const si = activeSentenceIndex(segs, player.currentTime);
  return si === null ? null : (segs.find((s) => s.sentence_index === si) ?? null);
}

// --- animation loop ----------------------------------------------------------
function tick(): void {
  const t = player.currentTime;
  karaoke?.update(t);
  curEl.textContent = fmt(t);
  rafId = requestAnimationFrame(tick);
}

// --- helpers -----------------------------------------------------------------
function note(message: string, warn: boolean): void {
  loadNote.textContent = message;
  loadNote.hidden = false;
  loadNote.classList.toggle("is-warn", warn);
}

function fmt(seconds: number): string {
  const s = Math.max(0, Math.floor(seconds));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

initTheme();
