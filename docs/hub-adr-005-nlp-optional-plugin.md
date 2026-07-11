# ADR 005 (Vorschlag) — razbiram-nlp als optionales Enrichment-Plugin für razbiram-listen

> **Ablageort-Ziel:** `razbiram-nlp/docs/adr/005-nlp-optional-plugin.md`.
> Dieser Entwurf lebt versioniert in `razbiram-listen/docs/`, bis er im Hub
> eingereicht/committet ist (ECOSYSTEM §6). Autorisiert vom Eigentümer (2026-07-11).

**Status:** vorgeschlagen · **Datum:** 2026-07-11
**Bezug:** ECOSYSTEM §2 (EnrichedDocument-Vertrag), §3 (Code-Wiederverwendung) · ADR 001 (Familien-Vertrag) · ADR 003 (BYO-Prinzip)

## Kontext

razbiram-listen bestand aus zwei Teilen mit sehr unterschiedlichem Gewicht:

- **Kern:** Whisper-Transkription → zeitgetreue Ausrichtung → Karaoke-Viewer. Das ist
  der eigentliche Mehrwert von listen und das, was der Hub *nicht* kann.
- **Anreicherung:** Glossen, Morphologie (classla), CEFR — das kann razbiram-nlp
  bereits hervorragend.

Bisher war `razbiram-nlp` eine **harte** Abhängigkeit (git-Pin), und `ListenDocument`
**erbte** von `razbiram_nlp.EnrichedDocument`. Damit brauchte selbst der reine
Transkript-Modus den ganzen Hub, und das seriell-blockierende Glossing ließ die UI
auf langen Dateien „eingefroren" wirken. Der Eigentümer möchte, dass sich die beiden
Tools **wie Adapter/Plugin** verhalten: listen läuft allein, und *wenn* razbiram-nlp
installiert ist, klinkt sich die Anreicherung automatisch ein.

Spannung mit der Nicht-verhandelbaren „Vertrag konsumieren, nie forken" (ECOSYSTEM §2):
Ist der Hub optional, braucht der Kern trotzdem ein Dokumentmodell.

## Entscheidung

1. **razbiram-nlp wird optionaler Extra** von razbiram-listen (`pip install
   razbiram-listen[enrich]`), nicht mehr Pflicht-Dependency. Der Kern (transcribe →
   align → karaoke) läuft ohne den Hub.
2. **listen hält eine formgleiche Kopie des Vertrags** (`razbiram_listen/contract.py`)
   — feldidentisch zu `razbiram_nlp.models` (gleiche Namen, JSON-Keys, Defaults,
   `extra="forbid"`). Das ist **kein Fork, sondern ein gespiegelter Vertrag**, gesichert
   durch einen **Kompatibilitätstest** (`test_contract_compat.py`), der — wenn der Hub
   installiert ist — ein Hub-`EnrichedDocument` durch die Kopie round-trippt und
   byte-identisches JSON verlangt. Drift schlägt in CI fehl (Evaluator-Prinzip, §5).
3. **Der Hub bleibt reine Engine:** die Anreicherung nutzt Hub-Primitive
   (`enrich_text`, `apply_glosses`, `plan_glosses`) und füllt das Ergebnis in listens
   Kopie. `plan_glosses` liefert die Gesamtzahl → ehrlicher „Satz X von N"-Fortschritt.
4. **Auslöser dieser Kopplung ist eine Hub-Lücke:** der Hub veröffentlicht (noch) kein
   `schemas/enriched-document.vN.json` und kein `schemaVersion`-Feld (siehe listen
   HANDOFF/BIBLE). Sobald der Hub ein JSON-Schema publiziert, wird `contract.py` gegen
   dieses generiert/validiert statt handgepflegt.

## Konsequenzen

- **+** listen ist sofort nützlich ohne schwere Abhängigkeiten; die Anreicherung ist
  ein echtes Opt-in-Plugin; der Kern hängt nie „in der Luft".
- **+** Der Familienvertrag bleibt die eine Wahrheit; die Kopie ist testgesichert.
- **−** Eine feldweise Kopie muss im Gleichschritt mit `razbiram_nlp/models.py`
  gepflegt werden — genau deshalb der Kompatibilitätstest und diese ADR.
- **Folge-ADR-Kandidat:** Hub veröffentlicht `schemas/…vN.json` + `schemaVersion`;
  dann konsumiert listen das Schema statt der handgepflegten Kopie.
