"""The local 'studio' server — one step: drop audio in the browser, read it.

Binds to 127.0.0.1 only. It serves the built viewer AND exposes ``POST /process``:
the browser sends an audio file's bytes to localhost, the server transcribes and
aligns them and **streams progress**, then returns the ``.listen.json``. Enrichment
(glosses/CEFR via the optional razbiram-nlp plugin) is opt-in per request; without
it the core still returns a synced transcript instantly. Still local-first —
nothing leaves the machine except the call to the local Ollama gloss provider. The
audio plays from the browser's own object URL; only its bytes are handed to
localhost for transcription.

Progress and result are streamed as newline-delimited JSON (one event per line),
read by the viewer via a ``fetch`` stream reader.
"""

from __future__ import annotations

import json
import os
import tempfile
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from . import enrichment, library
from .jobs import JobManager
from .pipeline import process_audio

# Read/write large files (uploads, audio) in 1 MiB chunks — never load a multi-GB
# body into memory.
_CHUNK = 1 << 20

_CTYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".mjs": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json",
    ".svg": "image/svg+xml",
    ".woff2": "font/woff2",
    ".wasm": "application/wasm",
    ".ico": "image/x-icon",
}


def _viewer_dist() -> Path | None:
    """The built viewer, if present (repo layout: ``<repo>/viewer/dist``)."""
    dist = Path(__file__).resolve().parents[2] / "viewer" / "dist"
    return dist if (dist / "index.html").is_file() else None


def _ollama_models() -> list[str]:
    """Locally available Ollama models (empty if Ollama isn't running)."""
    try:
        from urllib.request import urlopen

        host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
        with urlopen(f"{host}/api/tags", timeout=2) as resp:  # noqa: S310 - localhost
            data = json.load(resp)
        return [m["name"] for m in data.get("models", []) if m.get("name")]
    except Exception:
        return []


def pick_gloss_model(models: list[str]) -> str | None:
    """Prefer a multilingual model for BG→DE/EN glossing; else the first available."""
    for hint in ("aya", "gemma", "qwen", "mistral", "command-r", "llama3.1", "llama3", "llama"):
        for m in models:
            if hint in m.lower():
                return m
    return models[0] if models else None


class _Handler(BaseHTTPRequestHandler):
    dist: Path
    jobs: JobManager

    def log_message(self, *_args: object) -> None:  # keep the console clean
        pass

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/health":
            models = _ollama_models()
            self._json(
                {
                    "ok": True,
                    # Enrichment (glosses/CEFR) needs the razbiram-nlp plugin AND a
                    # local gloss model; the viewer offers translation only if both.
                    "enrichAvailable": enrichment.is_available() and bool(models),
                    "glossModels": models,
                    "defaultGlossModel": pick_gloss_model(models),
                    "workers": self.jobs.workers,
                }
            )
            return
        if path == "/jobs":
            self._json({"jobs": self.jobs.snapshot()})
            return
        if path == "/library":
            self._json({"entries": library.list_entries()})
            return
        parts = [p for p in path.split("/") if p]
        if len(parts) == 3 and parts[0] == "library":
            entry_id, what = parts[1], parts[2]
            if what == "result":
                self._serve_result(entry_id)
                return
            if what == "audio":
                self._serve_audio(entry_id)
                return
        self._static(path)

    def do_HEAD(self) -> None:
        # Browsers may probe the audio with a HEAD before ranged GETs.
        parts = [p for p in urlparse(self.path).path.split("/") if p]
        if len(parts) == 3 and parts[0] == "library" and parts[2] == "audio":
            self._serve_audio(parts[1])
            return
        self.send_error(404)

    def do_DELETE(self) -> None:
        parts = [p for p in urlparse(self.path).path.split("/") if p]
        if len(parts) == 2 and parts[0] == "jobs":  # cancel a queued/running job
            ok = self.jobs.cancel(parts[1])
            self._json({"ok": ok}, status=200 if ok else 404)
            return
        if len(parts) >= 2 and parts[0] == "library":
            entry_id = parts[1]
            if not library.is_valid_id(entry_id):
                self.send_error(404)
                return
            if len(parts) == 2:  # delete the whole entry
                ok = library.delete(entry_id)
            elif len(parts) == 3 and parts[2] == "audio":  # reclaim space, keep transcript
                ok = library.delete_audio(entry_id)
            else:
                self.send_error(404)
                return
            self._json({"ok": ok}, status=200 if ok else 404)
            return
        self.send_error(404)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/jobs":
            self._submit_job(parsed)
            return
        parts = [p for p in parsed.path.split("/") if p]
        if len(parts) == 3 and parts[0] == "library" and parts[2] == "translate":
            self._translate_entry(parts[1], parse_qs(parsed.query))
            return
        if parsed.path != "/process":
            self.send_error(404)
            return
        query = parse_qs(parsed.query)
        enrich_param = query.get("enrich", ["0"])[0] in ("1", "true", "yes", "on")
        gloss = (query.get("gloss", [None])[0]) or None
        if gloss in ("none", ""):
            gloss = None
        # Enrichment is opt-in; a chosen gloss language implies it.
        want_enrich = enrich_param or gloss is not None
        model = query.get("model", [None])[0] or None
        filename = self.headers.get("X-Filename", "audio.m4a")
        length = int(self.headers.get("Content-Length", "0"))
        audio_bytes = self.rfile.read(length)

        self.send_response(200)
        self.send_header("Content-Type", "application/x-ndjson; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()

        def emit(event: dict[str, object]) -> None:
            self.wfile.write((json.dumps(event, ensure_ascii=False) + "\n").encode("utf-8"))
            self.wfile.flush()

        if want_enrich and not enrichment.is_available():
            emit(
                {
                    "stage": "error",
                    "message": "Übersetzung/CEFR brauchen das razbiram-nlp-Plugin. "
                    "Installiere es mit 'pip install razbiram-listen[enrich]' — oder "
                    "wähle „nur Transkript“ für den sofortigen synchronen Text.",
                }
            )
            return

        tmp = Path(tempfile.mkdtemp(prefix="rzl_")) / _safe_name(filename)
        tmp.write_bytes(audio_bytes)
        try:
            result = process_audio(
                tmp,
                gloss_lang=gloss if want_enrich else None,
                gloss_model=model,
                enrich=want_enrich,
                show_progress=False,
                on_event=lambda stage, frac: emit({"stage": stage, "fraction": frac}),
            )
            emit(
                {
                    "stage": "result",
                    "coverage": result.stats.coverage,
                    "document": json.loads(result.document.to_json()),
                }
            )
        except Exception as exc:  # surface the real reason to the UI
            emit({"stage": "error", "message": f"{type(exc).__name__}: {exc}"})
        finally:
            try:
                tmp.unlink()
                tmp.parent.rmdir()
            except OSError:
                pass

    # --- jobs & library -------------------------------------------------------

    def _submit_job(self, parsed: object) -> None:
        query = parse_qs(getattr(parsed, "query", ""))
        enrich_param = query.get("enrich", ["0"])[0] in ("1", "true", "yes", "on")
        gloss = (query.get("gloss", [None])[0]) or None
        if gloss in ("none", ""):
            gloss = None
        want_enrich = enrich_param or gloss is not None
        model = query.get("model", [None])[0] or None
        filename = self.headers.get("X-Filename", "audio")
        length = int(self.headers.get("Content-Length", "0"))

        if want_enrich and not enrichment.is_available():
            self._json(
                {
                    "error": "enrich_unavailable",
                    "message": "Übersetzung/CEFR brauchen das razbiram-nlp-Plugin "
                    "(pip install razbiram-listen[enrich]).",
                },
                status=409,
            )
            return

        def write_audio(path: Path) -> None:
            left = length
            with open(path, "wb") as fh:
                while left > 0:
                    chunk = self.rfile.read(min(_CHUNK, left))
                    if not chunk:
                        break
                    fh.write(chunk)
                    left -= len(chunk)

        job_id = self.jobs.submit(
            filename=filename,
            enrich=want_enrich,
            gloss=gloss,
            model=model,
            write_audio=write_audio,
        )
        self._json({"jobId": job_id})

    def _translate_entry(self, entry_id: str, query: dict) -> None:
        if not library.is_valid_id(entry_id) or library.read_result(entry_id) is None:
            self.send_error(404)
            return
        if not enrichment.is_available():
            self._json(
                {
                    "error": "enrich_unavailable",
                    "message": "Übersetzen braucht das razbiram-nlp-Plugin "
                    "(pip install razbiram-listen[enrich]).",
                },
                status=409,
            )
            return
        lang = (query.get("lang", ["en"])[0]) or "en"
        model = query.get("model", [None])[0] or None
        job_id = self.jobs.submit_translate(entry_id, lang=lang, model=model)
        self._json({"jobId": job_id})

    def _serve_result(self, entry_id: str) -> None:
        text = library.read_result(entry_id)
        if text is None:
            self.send_error(404)
            return
        body = text.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_audio(self, entry_id: str) -> None:
        path = library.audio_path(entry_id)
        if path is None:
            self.send_error(404)
            return
        self._serve_file_range(path)

    def _serve_file_range(self, path: Path) -> None:
        """Serve a file with HTTP Range support so <audio> can seek in large files."""
        size = path.stat().st_size
        ctype = _CTYPES.get(path.suffix.lower(), "application/octet-stream")
        start, end, status = 0, size - 1, 200
        header = self.headers.get("Range")
        if header and header.startswith("bytes=") and size > 0:
            spec = header[len("bytes=") :].split(",")[0].strip()
            lo, _, hi = spec.partition("-")
            try:
                if lo == "":  # suffix range: bytes=-N (last N bytes)
                    start, end = max(0, size - int(hi)), size - 1
                else:
                    start, end = int(lo), (int(hi) if hi else size - 1)
            except ValueError:
                start, end = 0, size - 1
            if start > end or start >= size:
                self.send_response(416)
                self.send_header("Content-Range", f"bytes */{size}")
                self.end_headers()
                return
            end = min(end, size - 1)
            status = 206

        length = end - start + 1
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(length))
        if status == 206:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.end_headers()
        if self.command == "HEAD":
            return
        with open(path, "rb") as fh:
            fh.seek(start)
            left = length
            while left > 0:
                chunk = fh.read(min(_CHUNK, left))
                if not chunk:
                    break
                self.wfile.write(chunk)
                left -= len(chunk)

    # --- static viewer --------------------------------------------------------

    def _static(self, path: str) -> None:
        rel = path.lstrip("/") or "index.html"
        target = (self.dist / rel).resolve()
        if not str(target).startswith(str(self.dist)) or not target.is_file():
            target = self.dist / "index.html"  # SPA fallback
        body = target.read_bytes()
        self.send_response(200)
        self.send_header(
            "Content-Type", _CTYPES.get(target.suffix.lower(), "application/octet-stream")
        )
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj: dict[str, object], status: int = 200) -> None:
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def serve(*, host: str = "127.0.0.1", port: int = 7332, open_browser: bool = True) -> None:
    """Start the studio server (blocking). Serves the built viewer + ``/process``."""
    dist = _viewer_dist()
    if dist is None:
        raise RuntimeError("The viewer isn't built yet. Run:  cd viewer && npm ci && npm run build")
    manager = JobManager()
    manager.start()
    _Handler.dist = dist
    _Handler.jobs = manager
    httpd = ThreadingHTTPServer((host, port), _Handler)
    url = f"http://{host}:{port}/"
    print(
        f"razbiram-listen studio → {url}  "
        f"({manager.workers} worker(s), library: {library.home()})  (Ctrl+C to stop)"
    )
    if open_browser:
        try:
            webbrowser.open(url)
        except Exception:
            pass
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped.")
    finally:
        httpd.server_close()


def _safe_name(name: str) -> str:
    import re

    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(name).name).strip("_")
    return cleaned or "audio.m4a"
