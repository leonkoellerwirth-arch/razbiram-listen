# Projekt-Briefing für Claude Code
## Repository: `razbiram-listen`

> **Anweisung an Claude Code:** Baue auf Basis dieses Briefings ein öffentliches GitHub-Repository. Arbeite die Milestones in Reihenfolge ab. Abschnitt 8 (Rechts-Leitplanken) ist VERBINDLICH und nicht verhandelbar — bei jedem Konflikt zwischen Feature-Wunsch und Abschnitt 8 gewinnt Abschnitt 8. Frage bei Unklarheiten nach.

---

## 1. Zweck & Zielgruppe

**Was dieses Repo ist:** Ein local-first Hörverstehen-Studio für bulgarisches Audio. Der Nutzer bringt eine eigene Audiodatei (Podcast, Hörbuch, eigene Aufnahme) mit; das Tool erzeugt lokal ein zeitgestempeltes Transkript (Whisper), reichert es mit razbiram-nlp an (Lemma, Glossen, CEFR-Band) und zeigt eine **synchronisierte Lese-Ansicht**: laufender Text im Karaoke-Stil, Wort-Hover mit Bedeutung, ein Klick legt die Vokabel in einen Lern-Export ("Seed") für razbiram bzw. razbiram-anki.

**Kern-Claim:** *Listen to any Bulgarian audio and understand it word by word — locally, privately, with a learning loop.* Das existiert für Bulgarisch nirgends; Streaming-Plattformen können es aus Lizenzgründen nicht bauen (siehe Abschnitt 8 — genau deshalb ist dieses Tool bewusst BYO-Audio).

**Wer es nutzt:** Bulgarisch-Lernende ab A2 (Podcasts/Hörbücher sind das wichtigste Hörmaterial), Lehrkräfte (razbiram.schule: Hörverstehens-Material aus beliebigem legalem Audio), und als Showcase: Prüfer, die die razbiram-Pipeline Audio-bis-Lernkarte sehen wollen.

**Familien-Einordnung:** razbiram-nlp = Engine · razbiram-anki = Karten-Brücke · razbiram-listen = Audio-Eingangstor. Alle drei konsumieren/produzieren dasselbe EnrichedDocument-JSON (bei listen: erweitert um Timings).

---

## 2. Architektur (bewusst zweiteilig)

**Teil A — Pipeline (Python, CLI):** `razbiram-listen process --audio episode.mp3 --gloss de --out episode.listen.json`
1. **Transcribe:** faster-whisper lokal, Modell konfigurierbar (Default: small für CPU-Tauglichkeit), Wort-Zeitstempel aktiviert
2. **Enrich:** Transkript-Text durch razbiram-nlp (als Dependency), EnrichedDocument erzeugen
3. **Align:** Whisper-Wort-Timings auf razbiram-Tokens mappen (normalisierter Textabgleich; Interpunktions-/Groß-Klein-tolerant; bei Mismatch Segment-Timing als Fallback — Alignment-Qualität als eigenes Testfeld behandeln)
4. Ausgabe: ein `.listen.json` (EnrichedDocument + `timings` je Token/Segment + Audio-Dateiname als Referenz, NICHT das Audio selbst)

**Teil B — Viewer (statische Web-App, Vite + Vanilla/leichtes Framework, konsistent zum razbiram-nlp Studio):**
- Lädt lokal `.listen.json` + Audiodatei (File-Picker; kein Upload, kein Server, keine Telemetrie)
- **Karaoke-Ansicht:** aktueller Satz groß, aktives Wort hervorgehoben, Auto-Scroll; Klick auf Wort = Audio springt dorthin
- **Hover/Tap-Popover:** Lemma, Wortart, Glosse, CEFR-Badge (Farbskala wie Studio)
- **Seed-Funktion:** Klick auf ＋ am Wort sammelt Vokabeln; Export-Button erzeugt (a) razbiram-Seed-JSON und (b) razbiram-anki-kompatibles EnrichedDocument-Subset → direkte Weiterverarbeitung zum Deck
- Tempo-Regler (0.5×–1.5×), Satz-Loop-Taste (A-B-Repeat für Shadowing), Dark Mode

---

## 3. Repository-Struktur

```
razbiram-listen/
├── README.md
├── LICENSE                          # MIT (Tool, bewusst offen — wie razbiram-anki)
├── pyproject.toml                   # Python ≥3.11; deps: faster-whisper, pydantic, click, rich; razbiram-nlp als Dependency
├── src/razbiram_listen/
│   ├── __init__.py
│   ├── models.py                    # ListenDocument = EnrichedDocument + TokenTiming/SegmentTiming
│   ├── transcribe.py                # faster-whisper-Wrapper (Modellwahl, Wort-Timestamps, Fortschritt)
│   ├── align.py                     # Whisper-Wörter ↔ razbiram-Tokens (Kernstück, gut getestet)
│   ├── pipeline.py                  # Orchestrierung transcribe → enrich → align
│   └── cli.py
├── viewer/                          # Vite-App (eigenes package.json), Build wird nach docs/ oder GitHub Pages deploybar
│   ├── index.html
│   └── src/ (player, karaoke, popover, seed-export)
├── examples/
│   ├── sample-audio/                # NUR eigene Aufnahme oder CC-lizenziert; Quelle+Lizenz in SOURCES.md
│   ├── sample.listen.json
│   └── SOURCES.md                   # Pflicht: Herkunft & Lizenz jedes Beispiel-Assets
├── docs/img/                        # Screenshots/GIF der Karaoke-Ansicht (hell/dunkel)
├── tests/                           # pytest: align-Golden-Cases, Modell-Verträge; Whisper in Unit-Tests gemockt
└── .github/workflows/ci.yml         # ruff + pytest (Python) + build-check Viewer
```

---

## 4. Fachliche Kernvorgaben

- **Alignment ist das Qualitäts-Herzstück:** eigenes Golden-Set (5–8 kurze eigene Audio-Schnipsel mit handverifiziertem Transkript und erwartetem Token-Mapping). Jede Änderung an align.py läuft dagegen. Gleiches Evaluator-Prinzip wie razbiram-nlp — im README als Methodik-Merkmal benennen.
- **Whisper-Realismus dokumentieren:** Transkriptionsfehler sind normal; der Viewer bekommt einen dezenten "Transkript bearbeiten"-Modus (Korrektur einzelner Wörter, Re-Enrich des Satzes) — das macht das Tool praxistauglich und ehrlich.
- **CEFR-/Glossen-Ehrlichkeit** wie in razbiram-nlp: Heuristik-Labels, keine Zertifizierungs-Sprache.
- **Performance-Boden:** small-Modell + 10-Minuten-Podcast muss auf normaler CPU in akzeptabler Zeit laufen; Hinweis auf GPU/medium für Vielnutzer.

---

## 5. README — Aufbau

1. Ein-Satz-Pitch + **animiertes GIF der Karaoke-Ansicht direkt oben** (das Feature verkauft sich visuell oder gar nicht)
2. "Why BYO-audio": drei ehrliche Sätze — Lyrics/Streaming-Inhalte sind lizenzrechtlich geschützt; dieses Tool verarbeitet Audio, das dir gehört oder frei lizenziert ist; für Podcasts & Hörbücher ist genau das der Normalfall
3. Quickstart: Installation → ein Befehl → Viewer öffnen → Beispiel läuft
4. Familien-Diagramm (Mermaid): Audio → listen → EnrichedDocument+Timings → Viewer / → razbiram-anki
5. Roadmap als "planned": Spotify-Metadaten via offizieller API (Now-Playing-Anzeige, KEINE Texte), AnkiConnect-Push, weitere Sprachen
6. Disclaimer + Autor-Zeile + Links

---

## 6. Arbeits-Milestones

1. **M1 — Modelle + Gerüst:** ListenDocument, Struktur, CI.
2. **M2 — Transcribe:** faster-whisper-Wrapper mit Wort-Timestamps, gemockte Tests, ein echter Slow-Test.
3. **M3 — Align (Kern):** Mapping-Algorithmus + Golden-Set; erst weiter, wenn Golden-Cases grün.
4. **M4 — Pipeline + CLI:** Ende-zu-Ende vom MP3 zum .listen.json.
5. **M5 — Viewer MVP:** Laden, Karaoke-Sync, Hover-Popover, Tempo/Loop, Dark Mode.
6. **M6 — Seed-Export:** Vokabel-Sammlung, beide Export-Formate, Roundtrip-Test bis razbiram-anki-Deck.
7. **M7 — Politur:** Beispiel-Audio (eigene Aufnahme!), GIF/Screenshots, README, Transkript-Korrektur-Modus, Endabnahme mit frischem Clone.

**MVP-Scope-Freeze:** Lokale Dateien, Bulgarisch, Glossen de/en. Alles andere ist Roadmap-Text, kein Code.

---

## 7. Verwertung (Notiz für den Autor)

- 5.–6. Showcase-Repo nach razbiram-anki; Featured-work-Zeile im Profil-README; Companion-Verweise in razbiram-nlp/-anki
- razbiram.schule-Story: "Vom Podcast zur Hörverstehens-Stunde"
- Das Feature selbst (mit lizenziertem/eigenem Content) später als razbiram.com-Produktfunktion — die Plattform-Frage (Musik via Musixmatch-/Verlagslizenz) ist eine Geschäftsentscheidung, kein Repo-Thema

---

## 8. RECHTS-LEITPLANKEN (VERBINDLICH, NICHT VERHANDELBAR)

1. **Kein Scraping, keine inoffiziellen Endpunkte:** Keinerlei Code, der Lyrics, Untertitel oder Transkripte von Spotify, YouTube, Musixmatch o. ä. abruft, parst oder auch nur als "optionales Plugin" andeutet. Auch nicht in Beispielen, Kommentaren, Roadmap-Code oder Tests.
2. **Kein geschützter Content im Repo:** Keine Songtexte, keine kommerziellen Podcast-Ausschnitte, keine fremden Übersetzungen. Beispiel-Audio ausschließlich eigene Aufnahme oder ausdrücklich CC-lizenziert, mit SOURCES.md (Quelle, Lizenz, Link).
3. **Tool-Charakter wahren:** Das Repo verarbeitet, was der Nutzer lokal bereitstellt. Kein Download-Feature, keine Katalog-Anbindung, keine "so bekommst du das Audio"-Anleitungen.
4. **Spotify nur offiziell und nur Metadaten** (Roadmap, nicht MVP): ausschließlich dokumentierte Web-API, ausschließlich Now-Playing/Cover/Playback — niemals Textinhalte.
5. **Local-first & privat:** kein Server-Upload, keine Telemetrie, keine Cloud-Pflicht; LLM-Glossen via Ollama lokal (Anthropic-Provider optional, klar als solcher gekennzeichnet).
6. **Übliche Qualitätsregeln:** korrektes Bulgarisch in allen Beispielen; Type Hints, Docstrings, ruff-clean, pytest grün; keine razbiram-Produktinterna.

---

### §8 — Zusatz (Amendment, 2026-07-10, vom Autor autorisiert)

> Der ursprüngliche §8 oben bleibt vollständig gültig. Dieser Zusatz **scoped** ihn präzise:
> er erlaubt **offene, direkte** Audioquellen und lässt das Scraping-Verbot **unangetastet**.

**Erlaubt (neu):** ein Import einer **vom Nutzer angegebenen, direkten Audiodatei-URL** oder eines
**Podcast-RSS-Enclosures**, an dem der Nutzer Rechte hat. Das Tool lädt genau **diese eine, benannte
offene Datei** (wie es jede Podcast-App tut), transkribiert lokal, fertig.

**Weiterhin strikt verboten (unverändert):** Abruf/Parsing von **Streaming-/DRM-Plattformen**
(Spotify, YouTube, Musixmatch o. ä.); Lyrics-/Untertitel-/Transkript-Endpunkte; Umgehung technischer
Schutzmaßnahmen; das **Auflösen von Plattform-Seiten** zu Mediendateien; Katalog-Anbindung;
„so bekommst du das Audio von Plattform X"-Anleitungen. Kurz: **offene Direktdatei ja, Plattform nein.**

*Governance-Hinweis:* §8 gilt familienweit (ECOSYSTEM §7). Dieses Scoping sollte als Hub-ADR
nachgezogen werden, damit alle Repos dieselbe Grenze teilen.
