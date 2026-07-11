"""The local 'studio' server — one step: drop audio in the browser, read it.

Binds to 127.0.0.1 only. It serves the built viewer AND exposes ``POST /process``:
the browser sends an audio file's bytes to localhost, the server runs the pipeline
(transcribe → enrich → gloss → align) and **streams progress**, then returns the
``.listen.json``. Still local-first — nothing leaves the machine except the call to
the local Ollama gloss provider. The audio plays from the browser's own object URL;
only its bytes are handed to localhost for transcription.

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

from .pipeline import process_audio

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

    def log_message(self, *_args: object) -> None:  # keep the console clean
        pass

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/health":
            models = _ollama_models()
            self._json(
                {"ok": True, "glossModels": models, "defaultGlossModel": pick_gloss_model(models)}
            )
            return
        self._static(path)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != "/process":
            self.send_error(404)
            return
        query = parse_qs(parsed.query)
        gloss = (query.get("gloss", ["de"])[0]) or None
        if gloss in ("none", ""):
            gloss = None
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

        tmp = Path(tempfile.mkdtemp(prefix="rzl_")) / _safe_name(filename)
        tmp.write_bytes(audio_bytes)
        try:
            result = process_audio(
                tmp,
                gloss_lang=gloss,
                gloss_model=model,
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

    def _json(self, obj: dict[str, object]) -> None:
        body = json.dumps(obj).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def serve(*, host: str = "127.0.0.1", port: int = 7332, open_browser: bool = True) -> None:
    """Start the studio server (blocking). Serves the built viewer + ``/process``."""
    dist = _viewer_dist()
    if dist is None:
        raise RuntimeError("The viewer isn't built yet. Run:  cd viewer && npm ci && npm run build")
    _Handler.dist = dist
    httpd = ThreadingHTTPServer((host, port), _Handler)
    url = f"http://{host}:{port}/"
    print(f"razbiram-listen studio → {url}  (Ctrl+C to stop)")
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
