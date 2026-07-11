import "./styles.css";
import { type KaraokeHandle, renderKaraoke } from "./karaoke";
import { ListenError, parseListenDocument } from "./loadListen";
import { Player } from "./player";
import { SeedBasket, toCrowdAnkiDeck, toRazbiramSeed } from "./seed";
import { activeSentenceIndex } from "./sync";
import type { ListenDocument, SegmentTiming } from "./types";

function el<T extends HTMLElement>(id: string): T {
  const node = document.getElementById(id);
  if (!node) throw new Error(`missing #${id}`);
  return node as T;
}

const themeBtn = el<HTMLButtonElement>("theme");
const loader = el<HTMLElement>("loader");
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
const seedbar = el<HTMLElement>("seedbar");
const seedCount = el<HTMLSpanElement>("seed-count");
const seedExportSeed = el<HTMLButtonElement>("seed-export-seed");
const seedExportDeck = el<HTMLButtonElement>("seed-export-deck");
const seedClear = el<HTMLButtonElement>("seed-clear");
const studio = el<HTMLElement>("studio");
const studioDrop = el<HTMLElement>("studio-drop");
const studioInput = el<HTMLInputElement>("studio-input");
const studioGloss = el<HTMLSelectElement>("studio-gloss");
const studioModel = el<HTMLSpanElement>("studio-model");
const studioEnrichHint = el<HTMLParagraphElement>("studio-enrich-hint");
const studioProgress = el<HTMLElement>("studio-progress");
const studioProgressLabel = el<HTMLElement>("studio-progress-label");
const studioProgressBar = el<HTMLElement>("studio-progress-bar");

const player = new Player();
const basket = new SeedBasket();
let glossModel: string | null = null;
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
async function handleDoc(file: File): Promise<void> {
  try {
    doc = parseListenDocument(await file.text());
    refreshLoadState();
  } catch (err) {
    doc = null;
    note(err instanceof ListenError ? err.message : "Konnte die .listen.json nicht lesen.", true);
  }
}

function handleAudio(file: File): void {
  if (audioUrl) URL.revokeObjectURL(audioUrl);
  audioUrl = URL.createObjectURL(file);
  audioName = file.name;
  player.load(audioUrl);
  refreshLoadState();
}

function route(file: File): void {
  if (file.name.toLowerCase().endsWith(".json")) void handleDoc(file);
  else if (file.type.startsWith("audio/") || /\.(mp3|wav|m4a|ogg|flac|aiff?)$/i.test(file.name)) {
    handleAudio(file);
  } else {
    note(`„${file.name}“ ist weder eine .listen.json noch eine Audiodatei.`, true);
  }
}

docInput.addEventListener("change", () => {
  const file = docInput.files?.[0];
  if (file) void handleDoc(file);
});

audioInput.addEventListener("change", () => {
  const file = audioInput.files?.[0];
  if (file) handleAudio(file);
});

// Drag & drop anywhere on the loader card — route each file by type.
loader.addEventListener("dragover", (e) => {
  e.preventDefault();
  loader.classList.add("is-over");
});
loader.addEventListener("dragleave", () => loader.classList.remove("is-over"));
loader.addEventListener("drop", (e) => {
  e.preventDefault();
  loader.classList.remove("is-over");
  for (const file of Array.from(e.dataTransfer?.files ?? [])) route(file);
});

/** Decide what to show based on which of the two files are loaded, and always
 *  tell the user what is still missing — the viewer never transcribes itself. */
function refreshLoadState(): void {
  const haveDoc = doc !== null;
  const haveAudio = audioUrl !== null;

  if (haveDoc && haveAudio) {
    start();
    return;
  }

  transport.hidden = true;
  reader.hidden = true;
  seedbar.hidden = true;
  cancelAnimationFrame(rafId);

  if (haveAudio && !haveDoc) {
    const base = (audioName ?? "audio").replace(/\.[^.]+$/, "");
    noteHTML(
      `<strong>✓ Audio geladen:</strong> ${esc(audioName ?? "")}.<br>` +
        "Es fehlt das <strong>Transkript</strong> (<code>.listen.json</code>) — der Viewer " +
        "transkribiert bewusst nicht selbst. Erzeuge es einmalig lokal (synchroner " +
        "Transkript-Modus, schnell):<br>" +
        `<code class="rz-cmd">razbiram-listen process --audio "${esc(audioName ?? "")}" ` +
        `--out "${esc(base)}.listen.json"</code>` +
        "Für Übersetzung &amp; CEFR <code>--gloss de --gloss-model aya-expanse:8b</code> " +
        "ergänzen (braucht <code>razbiram-listen[enrich]</code>). Dann die erzeugte " +
        "<code>.listen.json</code> oben in Slot 1 laden.",
      true,
    );
  } else if (haveDoc && !haveAudio) {
    note(
      `✓ Transkript geladen (${doc?.sentences.length ?? 0} Sätze). Jetzt die passende Audiodatei laden.`,
      false,
    );
  }
}

function start(): void {
  if (!doc || !audioUrl) return;
  const d = doc;

  transport.hidden = false;
  reader.hidden = false;
  karaoke = renderKaraoke(d, reader, {
    onSeek: (seconds) => {
      player.seek(seconds);
      if (player.paused) void player.play();
    },
    onCollect: (itemToCollect) => {
      basket.toggle(itemToCollect);
      updateSeedBar();
    },
    isCollected: (candidate) => basket.has(candidate),
  });
  updateSeedBar();

  const expected = d.audioRef?.filename;
  const hasGloss = d.sentences.some((s) => s.gloss?.text);
  if (expected && audioName && expected !== audioName) {
    note(`Hinweis: Diese .listen.json wurde für „${expected}“ erzeugt, geladen ist „${audioName}“.`, true);
  } else if (hasGloss) {
    note(`Bereit — ${d.sentences.length} Sätze. Play drücken; „Show translation“ zeigt die Übersetzung.`, false);
  } else {
    note(`Bereit — ${d.sentences.length} Sätze, synchroner Transkript-Modus. Play drücken.`, false);
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

// --- seed export -------------------------------------------------------------
function updateSeedBar(): void {
  seedbar.hidden = basket.size === 0;
  seedCount.textContent = String(basket.size);
}

function deckName(): string {
  const base = audioName?.replace(/\.[^.]+$/, "");
  return base ? `${base} — razbiram-listen seed` : "razbiram-listen seed";
}

seedExportSeed.addEventListener("click", () =>
  downloadJson(
    toRazbiramSeed(basket.list(), { lang: doc?.lang, glossLang: "de" }),
    "razbiram-seed.json",
  ),
);
seedExportDeck.addEventListener("click", () =>
  downloadJson(toCrowdAnkiDeck(basket.list(), deckName()), "deck.json"),
);
seedClear.addEventListener("click", () => {
  basket.clear();
  updateSeedBar();
});

function downloadJson(data: unknown, filename: string): void {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
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

function noteHTML(html: string, warn: boolean): void {
  loadNote.innerHTML = html;
  loadNote.hidden = false;
  loadNote.classList.toggle("is-warn", warn);
}

function esc(s: string): string {
  return s.replace(
    /[&<>"]/g,
    (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c] as string,
  );
}

function fmt(seconds: number): string {
  const s = Math.max(0, Math.floor(seconds));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

// --- studio mode (served by `razbiram-listen studio`) ------------------------
// When a local studio server is present, one drop does everything: the audio is
// sent to localhost, transcribed + translated with a live progress bar, then
// shown. Falls back to the manual two-file loader when there's no server.
async function initStudioMode(): Promise<void> {
  let health: { defaultGlossModel?: string | null; enrichAvailable?: boolean } | null = null;
  try {
    const resp = await fetch("/health");
    if (resp.ok) health = await resp.json();
  } catch {
    health = null;
  }
  if (!health) return; // manual mode: keep #loader

  glossModel = health.defaultGlossModel ?? null;
  const enrichAvailable = health.enrichAvailable === true;
  loader.hidden = true;
  studio.hidden = false;
  studioModel.textContent = glossModel ? `Modell: ${glossModel}` : "kein lokales LLM gefunden";

  // Translation & CEFR need the razbiram-nlp plugin (+ a local LLM). Without it the
  // core still works: keep it selectable, but make the requirement clear.
  if (!enrichAvailable) {
    for (const opt of Array.from(studioGloss.options)) {
      if (opt.value !== "none") opt.disabled = true;
    }
    studioGloss.value = "none";
    studioEnrichHint.hidden = false;
    studioEnrichHint.textContent =
      "Übersetzung & CEFR: „pip install razbiram-listen[enrich]“ + ein lokales Ollama-Modell. " +
      "Ohne das läuft der synchrone Transkript-Modus sofort.";
  }

  studioDrop.addEventListener("click", () => studioInput.click());
  studioInput.addEventListener("change", () => {
    const file = studioInput.files?.[0];
    if (file) void studioProcess(file);
  });
  studioDrop.addEventListener("dragover", (e) => {
    e.preventDefault();
    studioDrop.classList.add("is-over");
  });
  studioDrop.addEventListener("dragleave", () => studioDrop.classList.remove("is-over"));
  studioDrop.addEventListener("drop", (e) => {
    e.preventDefault();
    studioDrop.classList.remove("is-over");
    const file = e.dataTransfer?.files?.[0];
    if (file) void studioProcess(file);
  });
}

async function studioProcess(file: File): Promise<void> {
  if (audioUrl) URL.revokeObjectURL(audioUrl);
  audioUrl = URL.createObjectURL(file);
  audioName = file.name;
  player.load(audioUrl);

  showProgress("Starte …", 0.02, false);
  const choice = studioGloss.value; // "none" → core mode; "de"/"en" → enrich
  const wantEnrich = choice !== "none";
  const params = new URLSearchParams({ enrich: wantEnrich ? "1" : "0" });
  if (wantEnrich) {
    params.set("gloss", choice);
    if (glossModel) params.set("model", glossModel);
  }
  let resp: Response;
  try {
    resp = await fetch(`/process?${params.toString()}`, {
      method: "POST",
      headers: { "X-Filename": file.name },
      body: file,
    });
  } catch {
    showProgress("Verbindung zum lokalen Server fehlgeschlagen.", 1, true);
    return;
  }
  if (!resp.ok || !resp.body) {
    showProgress(`Serverfehler (${resp.status}).`, 1, true);
    return;
  }

  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let nl: number;
    while ((nl = buffer.indexOf("\n")) >= 0) {
      const line = buffer.slice(0, nl).trim();
      buffer = buffer.slice(nl + 1);
      if (line) handleStudioEvent(JSON.parse(line));
    }
  }
}

function handleStudioEvent(ev: {
  stage: string;
  fraction?: number | null;
  message?: string;
  document?: ListenDocument;
}): void {
  switch (ev.stage) {
    case "transcribe":
      showProgress(`Transkribiere … ${Math.round((ev.fraction ?? 0) * 100)}%`, (ev.fraction ?? 0) * 0.6, false);
      break;
    case "enrich":
      if (ev.fraction == null) {
        // Cheap analysis (morphology/CEFR) before glossing — no count yet.
        showProgress("Analysiere (Morphologie & CEFR) …", 0.62, false, true);
      } else {
        // Honest translate progress: fraction = uncached gloss calls done / total.
        showProgress(
          `Übersetze … ${Math.round(ev.fraction * 100)}%`,
          0.62 + ev.fraction * 0.32,
          false,
        );
      }
      break;
    case "align":
      showProgress("Richte Timings aus …", 0.96, false);
      break;
    case "done":
      showProgress("Fertig", 1, false);
      break;
    case "result":
      if (ev.document) {
        doc = ev.document;
        studioProgress.hidden = true;
        studio.hidden = true;
        start();
      }
      break;
    case "error":
      showProgress(`Fehler: ${ev.message ?? "unbekannt"}`, 1, true);
      break;
  }
}

function showProgress(
  label: string,
  fraction: number,
  isError: boolean,
  indeterminate = false,
): void {
  studioProgress.hidden = false;
  studioProgress.classList.toggle("is-error", isError);
  studioProgress.classList.toggle("is-indeterminate", indeterminate);
  studioProgressLabel.textContent = label;
  studioProgressBar.style.width = indeterminate ? "" : `${Math.round(fraction * 100)}%`;
}

initTheme();
void initStudioMode();
