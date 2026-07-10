"""Open audio-source import (Briefing §8 amendment, 2026-07-10).

Fetches ONE user-named open audio resource: a direct audio-file URL, or a podcast
RSS feed (we take an ``<enclosure>``). This is deliberately NOT a downloader for
streaming/DRM platforms — those hosts are actively **blocked**, and we never parse
a platform *page* to resolve media. Open direct file: yes. Platform: no.

The network call is a single injectable seam (:func:`fetch_bytes`), so the
decision logic (host guard, classification, enclosure pick) is unit-tested with no
network.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

# Streaming / DRM platforms and their media CDNs — refused on sight (§8). This is a
# denylist of hosts we must never fetch from; open podcast hosts are allowed.
BLOCKED_HOSTS: frozenset[str] = frozenset(
    {
        "youtube.com",
        "youtu.be",
        "youtube-nocookie.com",
        "googlevideo.com",  # YouTube media CDN
        "spotify.com",
        "scdn.co",  # Spotify CDN
        "musixmatch.com",
        "soundcloud.com",
        "sndcdn.com",  # SoundCloud CDN
        "tiktok.com",
        "vimeo.com",
        "netflix.com",
        "deezer.com",
        "tidal.com",
        "music.apple.com",
        "audible.com",
    }
)

AUDIO_EXTS: frozenset[str] = frozenset({".mp3", ".m4a", ".wav", ".ogg", ".oga", ".flac", ".aac"})
_XML_HINT = re.compile(rb"^\s*<\?xml|<rss|<feed", re.IGNORECASE)


class SourceError(Exception):
    """A URL we cannot or must not fetch (blocked host, unsupported content, …)."""


@dataclass(frozen=True)
class FetchedResource:
    """A fetched resource: its final URL (after redirects), content type, bytes."""

    url: str
    content_type: str
    data: bytes


FetchFn = Callable[[str], FetchedResource]


def guard_url(url: str) -> None:
    """Raise :class:`SourceError` for a non-http(s) scheme or a blocked platform host."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise SourceError(f"Nur http(s)-URLs sind erlaubt (nicht „{parsed.scheme}:“).")
    host = (parsed.hostname or "").lower()
    if not host:
        raise SourceError("URL ohne Host.")
    for blocked in BLOCKED_HOSTS:
        if host == blocked or host.endswith(f".{blocked}"):
            raise SourceError(
                f"„{host}“ ist eine Streaming-/DRM-Plattform — Abruf ist verboten (Briefing §8). "
                "Erlaubt sind nur direkte Audiodateien oder Podcast-RSS-Feeds, "
                "an denen du Rechte hast."
            )


def looks_like_audio(content_type: str, url: str) -> bool:
    """True if the content type or URL extension indicates a direct audio file."""
    if content_type.split(";")[0].strip().lower().startswith("audio/"):
        return True
    ext = Path(urlparse(url).path).suffix.lower()
    return ext in AUDIO_EXTS


def looks_like_feed(content_type: str, data: bytes) -> bool:
    """True if the content type or the payload head indicates an RSS/Atom feed."""
    ct = content_type.split(";")[0].strip().lower()
    if ct in ("application/rss+xml", "application/atom+xml", "application/xml", "text/xml"):
        return True
    return bool(_XML_HINT.match(data[:200]))


def pick_enclosure(feed_bytes: bytes, *, episode: int | None = None) -> tuple[str, str | None]:
    """Return ``(audio_url, title)`` for a podcast RSS ``<enclosure>``.

    ``episode`` is a 1-based index into the feed's items in document order
    (typically newest first); the default is the first (newest) audio enclosure.
    """
    try:
        root = ET.fromstring(feed_bytes)
    except ET.ParseError as exc:
        raise SourceError(f"RSS-Feed konnte nicht geparst werden: {exc}") from exc

    items = root.findall(".//item") or root.findall(".//{http://www.w3.org/2005/Atom}entry")
    enclosures: list[tuple[str, str | None]] = []
    for item in items:
        url = _enclosure_url(item)
        if url:
            enclosures.append((url, _item_title(item)))

    if not enclosures:
        raise SourceError("Der RSS-Feed enthält keine Audio-Enclosure.")

    idx = 0 if episode is None else episode - 1
    if idx < 0 or idx >= len(enclosures):
        raise SourceError(
            f"Episode {episode} gibt es nicht (Feed hat {len(enclosures)} Audio-Episoden)."
        )
    return enclosures[idx]


def fetch_audio(
    url: str,
    dest_dir: str | Path,
    *,
    fetch: FetchFn | None = None,
    episode: int | None = None,
) -> Path:
    """Fetch one open audio resource to ``dest_dir`` and return the local path.

    Accepts a direct audio URL or a podcast RSS feed (one enclosure). Blocked
    hosts, platform pages, and non-audio/non-feed content are refused. The audio
    stays local afterwards so the viewer can load it (BYO principle preserved).
    """
    fetch = fetch or _default_fetch
    dest_dir = Path(dest_dir)

    guard_url(url)
    res = fetch(url)
    guard_url(res.url)  # re-check after any redirects

    if looks_like_audio(res.content_type, res.url):
        return _write(res.data, dest_dir, res.url)

    if looks_like_feed(res.content_type, res.data):
        enclosure_url, _title = pick_enclosure(res.data, episode=episode)
        guard_url(enclosure_url)
        audio = fetch(enclosure_url)
        guard_url(audio.url)
        if not looks_like_audio(audio.content_type, audio.url):
            raise SourceError("Die RSS-Enclosure verweist nicht auf eine Audiodatei.")
        return _write(audio.data, dest_dir, audio.url)

    raise SourceError(
        "Das ist weder eine direkte Audiodatei noch ein Podcast-RSS-Feed. "
        "Plattform-/HTML-Seiten werden nicht aufgelöst (Briefing §8)."
    )


# --- helpers ------------------------------------------------------------------


def _enclosure_url(item: ET.Element) -> str | None:
    enc = item.find("enclosure")
    if enc is not None:
        etype = (enc.get("type") or "").lower()
        url = enc.get("url")
        if url and (
            etype.startswith("audio/") or Path(urlparse(url).path).suffix.lower() in AUDIO_EXTS
        ):
            return url
    # Atom <link rel="enclosure" .../>
    for link in item.findall("{http://www.w3.org/2005/Atom}link"):
        if link.get("rel") == "enclosure" and (link.get("type") or "").lower().startswith("audio/"):
            return link.get("href")
    return None


def _item_title(item: ET.Element) -> str | None:
    title = item.find("title")
    if title is None:
        title = item.find("{http://www.w3.org/2005/Atom}title")
    return title.text if title is not None else None


def _write(data: bytes, dest_dir: Path, url: str) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    name = _safe_name(url)
    path = dest_dir / name
    path.write_bytes(data)
    return path


def _safe_name(url: str) -> str:
    raw = Path(urlparse(url).path).name or "audio.mp3"
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", raw).strip("_") or "audio"
    if Path(cleaned).suffix.lower() not in AUDIO_EXTS:
        cleaned += ".mp3"
    return cleaned


def _default_fetch(
    url: str, *, timeout: float = 30.0, max_bytes: int = 300 * 1024 * 1024
) -> FetchedResource:
    """The real network seam: a single GET with redirects, size- and time-capped."""
    from urllib.request import Request, urlopen

    req = Request(url, headers={"User-Agent": "razbiram-listen/0.1 (+local)"})
    with urlopen(req, timeout=timeout) as resp:  # noqa: S310 - scheme guarded by guard_url
        data = resp.read(max_bytes + 1)
        if len(data) > max_bytes:
            raise SourceError(f"Datei ist größer als das Limit ({max_bytes // (1024 * 1024)} MB).")
        content_type = resp.headers.get("Content-Type", "")
        return FetchedResource(url=resp.geturl(), content_type=content_type, data=data)
