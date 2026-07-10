"""Tests for the open-URL import (§8-scoped). Net-free: the HTTP seam is injected.

The critical assertions are the guardrails — streaming/DRM platforms and
platform/HTML pages must be refused; only direct audio and podcast RSS enclosures
are fetched.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from razbiram_listen.sources import (
    FetchedResource,
    SourceError,
    fetch_audio,
    guard_url,
    looks_like_audio,
    looks_like_feed,
    pick_enclosure,
)

RSS = b"""<?xml version="1.0"?>
<rss version="2.0"><channel>
  <title>Demo Podcast</title>
  <item><title>Episode 2</title>
    <enclosure url="https://cdn.example.com/ep2.mp3" type="audio/mpeg" length="1"/></item>
  <item><title>Episode 1</title>
    <enclosure url="https://cdn.example.com/ep1.mp3" type="audio/mpeg" length="1"/></item>
</channel></rss>"""


@pytest.mark.parametrize(
    "url",
    [
        "https://www.youtube.com/watch?v=x",
        "https://youtu.be/x",
        "https://open.spotify.com/track/x",
        "https://music.apple.com/x",
        "https://soundcloud.com/x",
        "https://www.musixmatch.com/lyrics/x",
    ],
)
def test_guard_blocks_streaming_platforms(url: str) -> None:
    with pytest.raises(SourceError, match="verboten|Plattform"):
        guard_url(url)


@pytest.mark.parametrize("url", ["ftp://host/a.mp3", "file:///etc/passwd", "data:audio/mp3,x"])
def test_guard_blocks_non_http_schemes(url: str) -> None:
    with pytest.raises(SourceError):
        guard_url(url)


def test_guard_allows_open_hosts() -> None:
    guard_url("https://cdn.example.com/ep1.mp3")  # no raise
    guard_url("https://feeds.buzzsprout.com/1.rss")


def test_classification() -> None:
    assert looks_like_audio("audio/mpeg", "https://x/y")
    assert looks_like_audio("application/octet-stream", "https://x/y.mp3")
    assert not looks_like_audio("text/html", "https://x/page")
    assert looks_like_feed("application/rss+xml", b"")
    assert looks_like_feed("text/html", b"<?xml version='1.0'?><rss>")


def test_pick_enclosure_defaults_to_first_and_indexes() -> None:
    assert pick_enclosure(RSS) == ("https://cdn.example.com/ep2.mp3", "Episode 2")
    assert pick_enclosure(RSS, episode=2)[0] == "https://cdn.example.com/ep1.mp3"
    with pytest.raises(SourceError, match="Episode 9"):
        pick_enclosure(RSS, episode=9)


def test_fetch_direct_audio(tmp_path: Path) -> None:
    def fake(url: str) -> FetchedResource:
        return FetchedResource(url=url, content_type="audio/mpeg", data=b"ID3AUDIO")

    path = fetch_audio("https://cdn.example.com/song.mp3", tmp_path, fetch=fake)
    assert path.exists()
    assert path.name == "song.mp3"
    assert path.read_bytes() == b"ID3AUDIO"


def test_fetch_rss_then_enclosure(tmp_path: Path) -> None:
    calls: list[str] = []

    def fake(url: str) -> FetchedResource:
        calls.append(url)
        if url.endswith(".rss"):
            return FetchedResource(url=url, content_type="application/rss+xml", data=RSS)
        return FetchedResource(url=url, content_type="audio/mpeg", data=b"EP2BYTES")

    path = fetch_audio("https://feeds.example.com/show.rss", tmp_path, fetch=fake)
    assert path.name == "ep2.mp3"
    assert path.read_bytes() == b"EP2BYTES"
    assert calls == ["https://feeds.example.com/show.rss", "https://cdn.example.com/ep2.mp3"]


def test_fetch_refuses_html_pages(tmp_path: Path) -> None:
    def fake(url: str) -> FetchedResource:
        return FetchedResource(url=url, content_type="text/html", data=b"<html></html>")

    with pytest.raises(SourceError, match="weder|Plattform"):
        fetch_audio("https://example.com/page", tmp_path, fetch=fake)


def test_fetch_rechecks_host_after_redirect(tmp_path: Path) -> None:
    # A URL that looks fine but redirects to a blocked host must still be refused.
    def fake(url: str) -> FetchedResource:
        return FetchedResource(
            url="https://youtube.com/watch?v=x", content_type="audio/mpeg", data=b"x"
        )

    with pytest.raises(SourceError, match="verboten|Plattform"):
        fetch_audio("https://redirector.example.com/go", tmp_path, fetch=fake)
