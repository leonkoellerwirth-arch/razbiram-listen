import "./styles.css";
import {
  audioUrl as libraryAudioUrl,
  cancelJob,
  deleteAudio,
  deleteEntry,
  fetchJobs,
  fetchLibrary,
  fetchResult,
  submitJob,
  translateEntry,
} from "./api";
import { type KaraokeHandle, renderKaraoke, renderReaderMeta } from "./karaoke";
import { ListenError, parseListenDocument } from "./loadListen";
import { Player } from "./player";
import { hasActive, newlyDone, renderJobs, renderLibrary } from "./queue";
import { SeedBasket, toCrowdAnkiDeck, toRazbiramSeed } from "./seed";
import { activeSentenceIndex } from "./sync";
import type { Job, ListenDocument, SegmentTiming } from "./types";

function el<T extends HTMLElement>(id: string): T {
  const node = document.getElementById(id);
  if (!node) throw new Error(`missing #${id}`);
  return node as T;
}

// --- Element refs ------------------------------------------------------------
const themeBtn = el<HTMLButtonElement>("theme");
const libraryBtn = el<HTMLButtonElement>("library-btn");
const drawerBackdrop = el<HTMLElement>("drawer-backdrop");
const drawerClose = el<HTMLButtonElement>("drawer-close");
// Loader (manual two-file mode)
const loader = el<HTMLElement>("loader");
const docInput = el<HTMLInputElement>("doc-input");
const audioInput = el<HTMLInputElement>("audio-input");
// Reader zone
const loadNote = el<HTMLParagraphElement>("load-note");
const readerHead = el<HTMLElement>("reader-head");
const readerMeta = el<HTMLElement>("reader-meta");
const langSelect = el<HTMLSelectElement>("lang-select");
const reader = el<HTMLElement>("reader");
// Player bar (Zone 3)
const transport = el<HTMLElement>("transport");
const playBtn = el<HTMLButtonElement>("play");
const curEl = el<HTMLSpanElement>("cur");
const durEl = el<HTMLSpanElement>("dur");
const scrubber = el<HTMLInputElement>("scrubber");
const rate = el<HTMLInputElement>("rate");
const rateVal = el<HTMLSpanElement>("rate-val");
const loopBtn = el<HTMLButtonElement>("loop");
// Seed bar
const seedbar = el<HTMLElement>("seedbar");
const seedCount = el<HTMLSpanElement>("seed-count");
const seedExportSeed = el<HTMLButtonElement>("seed-export-seed");
const seedExportDeck = el<HTMLButtonElement>("seed-export-deck");
const seedClear = el<HTMLButtonElement>("seed-clear");
// Studio (server mode)
const studio = el<HTMLElement>("studio");
const studioDrop = el<HTMLElement>("studio-drop");
const studioInput = el<HTMLInputElement>("studio-input");
const studioModel = el<HTMLSpanElement>("studio-model");
const studioEnrichHint = el<HTMLParagraphElement>("studio-enrich-hint");
const studioProgress = el<HTMLElement>("studio-progress");
const studioProgressLabel = el<HTMLElement>("studio-progress-label");
const studioProgressBar = el<HTMLElement>("studio-progress-bar");
// Queue/library drawer
const queuePanel = el<HTMLElement>("queue");
const queueJobsEl = el<HTMLElement>("queue-jobs");
const queueLibraryEl = el<HTMLElement>("queue-library");
// Spine
const spineSearch = el<HTMLInputElement>("spine-search");
const spineNav = el<HTMLElement>("spine-nav");
const spinePos = el<HTMLInputElement>("spine-pos");

const player = new Player();
const basket = new SeedBasket();
let glossModel: string | null = null;
let doc: ListenDocument | null = null;
let audioName: string | null = null;
let audioUrl: string | null = null;
let karaoke: KaraokeHandle | null = null;
let rafId = 0;
let studioActive = false;
let scrubbing = false;

// --- Theme -------------------------------------------------------------------
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

// --- Library/queue drawer ----------------------------------------------------
function openDrawer(): void {
  queuePanel.classList.add("is-open");
  drawerBackdrop.classList.add("is-open");
}
function closeDrawer(): void {
  queuePanel.classList.remove("is-open");
  drawerBackdrop.classList.remove("is-open");
}
libraryBtn.addEventListener("click", openDrawer);
drawerBackdrop.addEventListener("click", closeDrawer);
drawerClose.addEventListener("click", closeDrawer);
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") closeDrawer();
});

// --- File loading (manual two-file mode) ------------------------------------
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
  setAudioSource(URL.createObjectURL(file), file.name);
  refreshLoadState();
}

/** Point the player at a new source, revoking a previous object URL (not server URLs). */
function setAudioSource(url: string, name: string): void {
  if (audioUrl && audioUrl.startsWith("blob:")) URL.revokeObjectURL(audioUrl);
  audioUrl = url;
  audioName = name;
  player.load(url);
}

function route(file: File): void {
  if (file.name.toLowerCase().endsWith(".json")) void handleDoc(file);
  else if (file.type.startsWith("audio/") || /\.(mp3|wav|m4a|ogg|flac|aiff?)$/i.test(file.name)) {
    handleAudio(file);
  } else {
    note(`„${file.name}" ist weder eine .listen.json noch eine Audiodatei.`, true);
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

// Drag & drop on the loader card (manual mode).
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

  reader.hidden = true;
  readerHead.hidden = true;
  seedbar.hidden = true;
  cancelAnimationFrame(rafId);

  if (haveAudio && !haveDoc) {
    const base = (audioName ?? "audio").replace(/\.[^.]+$/, "");
    noteHTML(
      `<strong>✓ Audio geladen:</strong> ${esc(audioName ?? "")}.<br>` +
        "Es fehlt das <strong>Transkript</strong> (<code>.listen.json</code>) — der Viewer " +
        "transkribiert bewusst nicht selbst. Erzeuge es einmalig lokal:<br>" +
        `<code class="rz-cmd">razbiram-listen process --audio "${esc(audioName ?? "")}" ` +
        `--out "${esc(base)}.listen.json"</code>` +
        "Für Übersetzung &amp; CEFR <code>--gloss de --gloss-model aya-expanse:8b</code> " +
        "ergänzen (braucht <code>razbiram-listen[enrich]</code>). Dann die erzeugte " +
        "<code>.listen.json</code> in den Slot 1 laden.",
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

  // Hide empty states; show the reading interface
  studio.hidden = true;
  loader.hidden = true;
  readerHead.hidden = false;
  reader.hidden = false;
  transport.hidden = false;

  // Set translation visibility from the current lang-select value
  reader.dataset.translate = langSelect.value !== "off" ? "on" : "off";

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

  // Populate the sticky reader header
  renderReaderMeta(d, readerMeta);

  updateSeedBar();
  buildSpineNav();

  const expected = d.audioRef?.filename;
  const hasGloss = d.sentences.some((s) => s.gloss?.text);
  if (expected && audioName && expected !== audioName) {
    note(
      `Hinweis: Diese .listen.json wurde für „${expected}" erzeugt, geladen ist „${audioName}".`,
      true,
    );
  } else if (hasGloss) {
    note(`Bereit — ${d.sentences.length} Sätze. Play drücken.`, false);
  } else {
    note(`Bereit — ${d.sentences.length} Sätze, synchroner Transkript-Modus.`, false);
  }

  cancelAnimationFrame(rafId);
  tick();
}

// --- Spine navigation --------------------------------------------------------
/** Build jump marks in the spine from evenly-spaced segment timings. */
function buildSpineNav(): void {
  spineNav.innerHTML = "";
  const segments = doc?.timings?.segments ?? [];
  if (segments.length === 0) return;
  const count = Math.min(segments.length, 12);
  const step = Math.max(1, Math.floor(segments.length / count));
  for (let i = 0; i < segments.length; i += step) {
    const seg = segments[i];
    const btn = document.createElement("button");
    btn.className = "rz-spine-mark";
    btn.type = "button";
    btn.textContent = fmt(seg.t_start);
    btn.title = `Springe zu ${fmt(seg.t_start)}`;
    btn.dataset.si = String(seg.sentence_index);
    btn.addEventListener("click", () => {
      player.seek(seg.t_start);
      if (player.paused) void player.play();
    });
    spineNav.appendChild(btn);
  }
}

/** Highlight the spine mark nearest to the current sentence. */
function updateSpineMark(si: number | null): void {
  for (const btn of spineNav.querySelectorAll<HTMLElement>(".rz-spine-mark")) {
    const btnSi = Number(btn.dataset.si);
    btn.classList.toggle("is-current", si !== null && btnSi === si);
  }
}

spineSearch.addEventListener("input", () => {
  karaoke?.filter(spineSearch.value);
});

spinePos.addEventListener("change", () => {
  if (player.duration > 0) {
    player.seek((Number(spinePos.value) / 1000) * player.duration);
  }
});

// --- Player bar (Zone 3) -----------------------------------------------------
playBtn.addEventListener("click", () => player.toggle());
player.audio.addEventListener("play", () => (playBtn.textContent = "⏸ Pause"));
player.audio.addEventListener("pause", () => (playBtn.textContent = "▶ Play"));
player.audio.addEventListener("loadedmetadata", () => {
  durEl.textContent = fmt(player.duration);
  buildSpineNav(); // refresh with actual duration info
});

rate.addEventListener("input", () => {
  const r = Number(rate.value);
  player.setRate(r);
  rateVal.textContent = `${r.toFixed(1)}×`;
});

// Scrubber: prevent feedback while dragging
scrubber.addEventListener("pointerdown", () => { scrubbing = true; });
scrubber.addEventListener("pointerup", () => {
  scrubbing = false;
  if (player.duration > 0) player.seek((Number(scrubber.value) / 1000) * player.duration);
});
scrubber.addEventListener("input", () => {
  // Update time display while dragging (no seek yet)
  curEl.textContent = fmt((Number(scrubber.value) / 1000) * (player.duration || 0));
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

// --- Seed export -------------------------------------------------------------
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

// --- Animation loop ----------------------------------------------------------
function tick(): void {
  const t = player.currentTime;
  karaoke?.update(t);
  curEl.textContent = fmt(t);

  // Keep scrubber and spine position rail in sync (skip when user is dragging)
  if (!scrubbing && player.duration > 0) {
    const pct = String((t / player.duration) * 1000);
    scrubber.value = pct;
    spinePos.value = pct;
  }

  // Keep the nearest spine mark highlighted
  const segs = doc?.timings?.segments;
  if (segs) {
    updateSpineMark(activeSentenceIndex(segs, t));
  }

  rafId = requestAnimationFrame(tick);
}

// --- Helpers -----------------------------------------------------------------
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

// --- Language control (unified) ---------------------------------------------
// The single #lang-select drives:
//   • Translation visibility on the reader (data-translate attribute)
//   • Initial gloss language when submitting a studio job
//   • Re-translation of an already-saved entry (via POST /library/<id>/translate)

langSelect.addEventListener("change", () => {
  const val = langSelect.value;
  // Always update translate visibility immediately
  reader.dataset.translate = val !== "off" ? "on" : "off";
  // If a library entry is loaded and we want a different gloss lang, re-translate
  if (val !== "off" && currentEntryId) {
    const currentLang = doc?.sentences.find((s) => s.gloss?.text)?.gloss?.lang;
    if (currentLang !== val) void switchLanguage(val);
  }
});

// Switch the current entry's translation language: queue a re-gloss job (reusing
// the transcript), then reopen the entry when it finishes (cached → quick).
async function switchLanguage(lang: string): Promise<void> {
  if (!currentEntryId) return;
  try {
    const jobId = await translateEntry(currentEntryId, lang, glossModel);
    pendingOpen[jobId] = currentEntryId; // reopen this entry when the job is done
    await refreshQueue();
    kickPolling();
  } catch (err) {
    note(err instanceof Error ? err.message : "Übersetzen fehlgeschlagen.", true);
  }
}

// --- Studio mode (served by `razbiram-listen studio`) -----------------------
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
  if (!health) return; // no server — manual mode: keep #loader

  studioActive = true;
  glossModel = health.defaultGlossModel ?? null;
  const enrichAvailable = health.enrichAvailable === true;

  loader.hidden = true;
  studio.hidden = false;
  libraryBtn.hidden = false;
  studioModel.textContent = glossModel ? `Modell: ${glossModel}` : "kein lokales LLM gefunden";

  // Translation & CEFR need the razbiram-nlp plugin + a local LLM.
  // Disable those options when the plugin is missing.
  if (!enrichAvailable) {
    for (const opt of Array.from(langSelect.options)) {
      if (opt.value !== "off") opt.disabled = true;
    }
    langSelect.value = "off";
    studioEnrichHint.hidden = false;
    studioEnrichHint.textContent =
      "Uebersetzung & CEFR: 'pip install razbiram-listen[enrich]' + ein lokales Ollama-Modell. " +
      "Ohne das laeuft der synchrone Transkript-Modus sofort.";
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

  // Also accept drops anywhere on the page (e.g. when the reader is showing)
  document.addEventListener("dragover", (e) => {
    if (studioActive && studio.hidden) e.preventDefault(); // only when studio is hidden
  });
  document.addEventListener("drop", (e) => {
    if (!studioActive || !studio.hidden) return; // let the studio-drop handler take it
    e.preventDefault();
    const file = e.dataTransfer?.files?.[0];
    if (file) void studioProcess(file);
  });

  // Make the drawer available; load existing entries.
  queuePanel.hidden = false; // no-op (drawer not hidden in HTML), kept for clarity
  await refreshLibrary();
  await refreshQueue();
  kickPolling();
}

// Submit a drop as a background job. The dropzone stays so more files can be
// queued. The unified lang-select determines the initial gloss language.
async function studioProcess(file: File): Promise<void> {
  const choice = langSelect.value; // "off" → core; "de"/"en" → enrich
  const wantEnrich = choice !== "off";
  showProgress("Lädt in die Warteschlange …", 0.06, false, true);
  try {
    const jobId = await submitJob(file, {
      enrich: wantEnrich,
      gloss: wantEnrich ? choice : undefined,
      model: glossModel,
    });
    pendingOpen[jobId] = jobId; // a process job's entry id == its job id
    studioProgress.hidden = true;
    await refreshQueue();
    kickPolling();
  } catch (err) {
    showProgress(err instanceof Error ? err.message : "Fehler beim Absenden.", 1, true);
  }
}

// --- Queue polling + library -------------------------------------------------
let polling = false;
let prevJobs: Job[] = [];
let currentEntryId: string | null = null;
// job id → library entry to (re)open when that job finishes (process or translate).
const pendingOpen: Record<string, string> = {};

async function refreshQueue(): Promise<boolean> {
  const jobs = await fetchJobs();
  renderJobs(queueJobsEl, jobs, {
    onCancel: async (id) => {
      await cancelJob(id);
      await refreshQueue();
    },
  });
  const done = newlyDone(prevJobs, jobs);
  prevJobs = jobs;
  if (done.length > 0) {
    await refreshLibrary();
    for (const id of done) {
      const entryId = pendingOpen[id];
      if (entryId) {
        delete pendingOpen[id];
        void openLibraryItem(entryId);
      }
    }
  }
  return hasActive(jobs);
}

// Poll /jobs while anything is active; stop when the queue is idle (localhost, cheap).
function kickPolling(): void {
  if (polling) return;
  polling = true;
  const tick = async (): Promise<void> => {
    const active = await refreshQueue();
    if (active) window.setTimeout(() => void tick(), 1200);
    else polling = false;
  };
  void tick();
}

async function refreshLibrary(): Promise<void> {
  const entries = await fetchLibrary();
  renderLibrary(queueLibraryEl, entries, {
    onOpen: (id) => {
      closeDrawer(); // close drawer when opening an entry
      void openLibraryItem(id);
    },
    onDelete: async (id) => {
      await deleteEntry(id);
      await refreshLibrary();
    },
    onRemoveAudio: async (id) => {
      await deleteAudio(id);
      await refreshLibrary();
    },
  });
}

// Open a saved entry: load its transcript + point the player at the range-served
// audio (seeking works on large files), then show the reader.
async function openLibraryItem(id: string): Promise<void> {
  try {
    const loaded = await fetchResult(id);
    setAudioSource(libraryAudioUrl(id), loaded.audioRef?.filename ?? "audio");
    doc = loaded;
    currentEntryId = id;
    // Sync lang-select to the language already present in this entry
    const current = loaded.sentences.find((s) => s.gloss)?.gloss?.lang;
    if (current === "de" || current === "en") langSelect.value = current;
    refreshLoadState();
  } catch (err) {
    note(err instanceof Error ? err.message : "Konnte den Eintrag nicht öffnen.", true);
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
