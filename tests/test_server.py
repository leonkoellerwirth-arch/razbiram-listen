"""Net-free tests for the studio server's pure helpers (no socket, no Ollama)."""

from __future__ import annotations

from razbiram_listen.server import _safe_name, pick_gloss_model


def test_pick_gloss_model_prefers_multilingual() -> None:
    assert pick_gloss_model(["llama3.2:latest", "aya-expanse:8b"]) == "aya-expanse:8b"
    assert pick_gloss_model(["gemma2:9b", "phi3"]) == "gemma2:9b"
    # No known-good hint → first available.
    assert pick_gloss_model(["someweird:model"]) == "someweird:model"
    assert pick_gloss_model([]) is None


def test_safe_name_strips_paths_and_bad_chars() -> None:
    assert _safe_name("../../etc/passwd") == "passwd"
    assert _safe_name("my file (1).mp3") == "my_file_1_.mp3"
    assert _safe_name("") == "audio.m4a"
