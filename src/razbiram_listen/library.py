"""Local library — a persistent store of processed audio + results for replay.

Everything is a plain directory on the user's own machine (local-first, no upload,
BIBLE D8): ``<home>/library/<id>/`` holds the user's ``audio.<ext>``, the
``result.listen.json``, and a small ``meta.json``. The owner keeps the audio so a
past result can be replayed with one click; the audio is deletable per entry to
reclaim space (the transcript stays).

``home`` is ``$RAZBIRAM_LISTEN_HOME`` or ``~/.razbiram-listen``. Entries are listed
newest-first by ``createdAt``; an entry counts as "in the library" only once its
``result.listen.json`` exists (an in-flight or failed job leaves no library entry).
"""

from __future__ import annotations

import json
import os
import re
import shutil
import uuid
from pathlib import Path

_AUDIO_STEM = "audio"
_RESULT_NAME = "result.listen.json"
_META_NAME = "meta.json"

# Entry ids are opaque hex we mint; validate anything coming from a URL against this
# to keep ids out of parent directories (path-traversal guard).
_ID_RE = re.compile(r"^[a-f0-9]{6,32}$")


def is_valid_id(entry_id: str) -> bool:
    """True if ``entry_id`` is a well-formed library id (safe as a path segment)."""
    return bool(_ID_RE.match(entry_id))


def home() -> Path:
    """The library root: ``$RAZBIRAM_LISTEN_HOME`` or ``~/.razbiram-listen``."""
    env = os.environ.get("RAZBIRAM_LISTEN_HOME")
    return Path(env).expanduser() if env else Path.home() / ".razbiram-listen"


def library_dir() -> Path:
    return home() / "library"


def entry_dir(entry_id: str) -> Path:
    return library_dir() / entry_id


def reserve(filename: str) -> tuple[str, Path]:
    """Create a fresh entry dir; return ``(id, audio_path)`` to stream the upload into."""
    entry_id = uuid.uuid4().hex[:12]
    directory = entry_dir(entry_id)
    directory.mkdir(parents=True, exist_ok=True)
    ext = re.sub(r"[^a-z0-9.]", "", Path(filename).suffix.lower()) or ".bin"
    return entry_id, directory / f"{_AUDIO_STEM}{ext}"


def audio_path(entry_id: str) -> Path | None:
    """The stored audio file for ``entry_id``, if it still exists."""
    if not is_valid_id(entry_id):
        return None
    directory = entry_dir(entry_id)
    if not directory.is_dir():
        return None
    for candidate in sorted(directory.glob(f"{_AUDIO_STEM}.*")):
        if candidate.is_file():
            return candidate
    return None


def save_result(entry_id: str, document_json: str, meta: dict) -> None:
    """Write ``result.listen.json`` + ``meta.json`` — the entry now counts as saved."""
    directory = entry_dir(entry_id)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / _RESULT_NAME).write_text(document_json, encoding="utf-8")
    record = dict(meta)
    record["id"] = entry_id
    record["hasAudio"] = audio_path(entry_id) is not None
    (directory / _META_NAME).write_text(
        json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def read_result(entry_id: str) -> str | None:
    """The stored ``.listen.json`` text, or ``None``."""
    if not is_valid_id(entry_id):
        return None
    path = entry_dir(entry_id) / _RESULT_NAME
    return path.read_text(encoding="utf-8") if path.is_file() else None


def read_meta(entry_id: str) -> dict | None:
    """The entry's meta, with ``hasAudio`` recomputed from disk, or ``None``."""
    if not is_valid_id(entry_id):
        return None
    path = entry_dir(entry_id) / _META_NAME
    if not path.is_file():
        return None
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    record["hasAudio"] = audio_path(entry_id) is not None
    return record


def list_entries() -> list[dict]:
    """All saved entries (those with a result), newest-first by ``createdAt``."""
    directory = library_dir()
    if not directory.is_dir():
        return []
    entries: list[dict] = []
    for child in directory.iterdir():
        if child.is_dir() and (child / _RESULT_NAME).is_file():
            meta = read_meta(child.name)
            if meta is not None:
                entries.append(meta)
    entries.sort(key=lambda m: m.get("createdAt", ""), reverse=True)
    return entries


def delete(entry_id: str) -> bool:
    """Remove the whole entry (audio + result + meta)."""
    if not is_valid_id(entry_id):
        return False
    directory = entry_dir(entry_id)
    if directory.is_dir():
        shutil.rmtree(directory, ignore_errors=True)
        return True
    return False


def delete_audio(entry_id: str) -> bool:
    """Remove only the audio (reclaim space); the transcript stays, ``hasAudio`` false."""
    path = audio_path(entry_id)
    if path is None or not path.is_file():
        return False
    path.unlink()
    meta = read_meta(entry_id)  # recomputes hasAudio = False now the file is gone
    if meta is not None:
        (entry_dir(entry_id) / _META_NAME).write_text(
            json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return True


def discard(entry_id: str) -> None:
    """Drop a reserved-but-unfinished entry (e.g. after a failed job)."""
    delete(entry_id)
