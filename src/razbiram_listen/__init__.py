"""razbiram-listen — a local-first Bulgarian listening studio.

Bring your own audio; the pipeline transcribes it locally (Whisper), enriches
the transcript through the razbiram-nlp hub, aligns Whisper word timings to the
enriched tokens, and emits a ``.listen.json`` (an EnrichedDocument extended with
timings) that the Karaoke viewer plays back word by word.

Public API
----------
    from razbiram_listen import ListenDocument
"""

from __future__ import annotations

from .models import (
    SCHEMA_VERSION,
    AudioRef,
    ListenDocument,
    ListenTimings,
    SegmentTiming,
    TokenTiming,
)

__version__ = "0.1.0"

__all__ = [
    "SCHEMA_VERSION",
    "AudioRef",
    "ListenDocument",
    "ListenTimings",
    "SegmentTiming",
    "TokenTiming",
    "__version__",
]
