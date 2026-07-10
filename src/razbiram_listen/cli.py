"""Command-line entry point for razbiram-listen.

``process`` runs the end-to-end pipeline (M4): a local audio file → a
``.listen.json`` (EnrichedDocument + audio timings) the Karaoke viewer plays.
Everything runs locally; the audio never leaves the machine (BYO-audio).
"""

from __future__ import annotations

from pathlib import Path

import click
from rich.console import Console

from . import __version__
from .pipeline import process_audio
from .transcribe import DEFAULT_MODEL


@click.group()
@click.version_option(__version__, prog_name="razbiram-listen")
def main() -> None:
    """Local-first Bulgarian listening studio (BYO audio)."""


@main.command()
@click.option(
    "--audio",
    "audio",
    required=True,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Local audio file to process (never uploaded).",
)
@click.option(
    "--out",
    "out",
    required=True,
    type=click.Path(dir_okay=False, path_type=Path),
    help="Where to write the .listen.json.",
)
@click.option(
    "--gloss",
    "gloss",
    default=None,
    help="Gloss language: 'de', 'en', or omit for no glosses.",
)
@click.option(
    "--model", "model", default=DEFAULT_MODEL, show_default=True, help="Whisper model size."
)
@click.option("--language", "language", default="bg", show_default=True, help="Spoken language.")
def process(audio: Path, out: Path, gloss: str | None, model: str, language: str) -> None:
    """Transcribe, enrich, and align AUDIO into a .listen.json."""
    console = Console()
    console.print(f"[bold]Processing[/bold] {audio.name} (model: {model}) …")

    result = process_audio(audio, gloss_lang=gloss, model_size=model, language=language)

    out.write_text(result.document.to_json(), encoding="utf-8")

    coverage = f"{result.stats.coverage:.0%}"
    tokens = result.stats.matched_word_tokens
    total = result.stats.total_word_tokens
    console.print(
        f"[green]✓[/green] wrote [bold]{out}[/bold] · "
        f"{result.duration:.1f}s audio · alignment {coverage} ({tokens}/{total} words)"
    )
    if result.stats.total_word_tokens and result.stats.coverage < 0.5:
        console.print(
            "[yellow]![/yellow] low alignment coverage — the transcript may need editing "
            "in the viewer before the karaoke sync is reliable."
        )


if __name__ == "__main__":
    main()
