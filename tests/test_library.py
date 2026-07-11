"""Tests for the local library store (net-free; a tmp RAZBIRAM_LISTEN_HOME)."""

from __future__ import annotations

import pytest

from razbiram_listen import library


@pytest.fixture
def lib_home(tmp_path, monkeypatch):
    monkeypatch.setenv("RAZBIRAM_LISTEN_HOME", str(tmp_path))
    return tmp_path


def test_reserve_creates_dir_with_typed_audio_path(lib_home) -> None:
    entry_id, audio = library.reserve("Мой филм.MP4")
    assert library.is_valid_id(entry_id)
    assert audio.parent.is_dir()
    assert audio.name == "audio.mp4"  # suffix normalised, lower-cased
    audio.write_bytes(b"xyz")
    assert library.audio_path(entry_id) == audio


def test_save_result_makes_entry_listable(lib_home) -> None:
    entry_id, audio = library.reserve("song.mp3")
    audio.write_bytes(b"\x00\x01")
    library.save_result(
        entry_id,
        '{"text":"hi","schemaVersion":"1.0.0"}',
        {
            "title": "song",
            "filename": "song.mp3",
            "createdAt": "2026-07-11T10:00:00Z",
            "mode": "core",
        },
    )
    entries = library.list_entries()
    assert len(entries) == 1
    assert entries[0]["id"] == entry_id
    assert entries[0]["hasAudio"] is True
    assert library.read_result(entry_id).startswith("{")


def test_in_progress_entry_without_result_is_not_listed(lib_home) -> None:
    entry_id, audio = library.reserve("x.mp3")
    audio.write_bytes(b"a")  # audio only, no result yet
    assert library.list_entries() == []


def test_entries_are_newest_first(lib_home) -> None:
    first, pa = library.reserve("a.mp3")
    pa.write_bytes(b"a")
    library.save_result(first, "{}", {"createdAt": "2026-01-01T00:00:00Z", "title": "a"})
    second, pb = library.reserve("b.mp3")
    pb.write_bytes(b"b")
    library.save_result(second, "{}", {"createdAt": "2026-02-01T00:00:00Z", "title": "b"})
    assert [e["id"] for e in library.list_entries()] == [second, first]


def test_delete_audio_keeps_transcript(lib_home) -> None:
    entry_id, audio = library.reserve("f.mp3")
    audio.write_bytes(b"a")
    library.save_result(entry_id, "{}", {"createdAt": "2026-01-01T00:00:00Z"})
    assert library.delete_audio(entry_id) is True
    assert library.audio_path(entry_id) is None
    assert library.read_result(entry_id) == "{}"  # transcript stays
    assert library.read_meta(entry_id)["hasAudio"] is False


def test_delete_removes_the_whole_entry(lib_home) -> None:
    entry_id, audio = library.reserve("f.mp3")
    audio.write_bytes(b"a")
    library.save_result(entry_id, "{}", {"createdAt": "z"})
    assert library.delete(entry_id) is True
    assert library.list_entries() == []


def test_invalid_id_is_rejected(lib_home) -> None:
    assert library.is_valid_id("../etc") is False
    assert library.is_valid_id("a1b2c3") is True
    assert library.read_result("../etc/passwd") is None
    assert library.audio_path("..") is None
    assert library.delete("..") is False
