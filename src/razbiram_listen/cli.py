"""Command-line entry point for razbiram-listen.

``process`` runs the end-to-end pipeline (M4): a local audio file → a
``.listen.json`` (EnrichedDocument + audio timings) the Karaoke viewer plays.
Everything runs locally; the audio never leaves the machine (BYO-audio).
"""

from __future__ import annotations

from pathlib import Path

import click
from rich.console import Console
from rich.progress import BarColumn, Progress, TaskProgressColumn, TextColumn, TimeElapsedColumn

from . import __version__
from .enrichment import is_available
from .pipeline import process_audio
from .sources import SourceError, fetch_audio
from .transcribe import DEFAULT_MODEL


@click.group()
@click.version_option(__version__, prog_name="razbiram-listen")
def main() -> None:
    """Local-first Bulgarian listening studio (BYO audio)."""


@main.command()
@click.option("--port", default=7332, show_default=True, help="Local port.")
@click.option("--no-open", is_flag=True, help="Don't open the browser automatically.")
def studio(port: int, no_open: bool) -> None:
    """Open the studio: drop an audio file in the browser and read it — one step.

    Starts a local server (127.0.0.1 only) that serves the viewer and does the
    transcription + translation for you. No files to juggle, no flags to type.
    """
    from .server import serve

    serve(port=port, open_browser=not no_open)


@main.command()
@click.option(
    "--audio",
    "audio",
    default=None,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Local audio file to process (never uploaded).",
)
@click.option(
    "--url",
    "url",
    default=None,
    help="Open audio URL to import: a direct audio file or a podcast RSS feed you "
    "have rights to. Streaming/DRM platforms (YouTube, Spotify, …) are refused.",
)
@click.option(
    "--episode",
    "episode",
    type=int,
    default=None,
    help="With an RSS --url: 1-based episode to pick (default: newest).",
)
@click.option(
    "--out",
    "out",
    required=True,
    type=click.Path(dir_okay=False, path_type=Path),
    help="Where to write the .listen.json.",
)
@click.option(
    "--enrich/--no-enrich",
    "enrich",
    default=False,
    help="Add glosses/CEFR/morphology via the razbiram-nlp plugin. Off by default "
    "(the core emits a synced transcript). A --gloss language implies --enrich.",
)
@click.option(
    "--gloss",
    "gloss",
    default=None,
    help="Gloss language: 'de', 'en', or omit for no glosses (implies --enrich).",
)
@click.option(
    "--gloss-model",
    "gloss_model",
    default=None,
    help="Local Ollama model for glosses, e.g. 'aya-expanse:8b'. Omit for the hub default.",
)
@click.option(
    "--model", "model", default=DEFAULT_MODEL, show_default=True, help="Whisper model size."
)
@click.option("--language", "language", default="bg", show_default=True, help="Spoken language.")
def process(
    audio: Path | None,
    url: str | None,
    episode: int | None,
    out: Path,
    enrich: bool,
    gloss: str | None,
    gloss_model: str | None,
    model: str,
    language: str,
) -> None:
    """Transcribe and align audio into a .listen.json (enrichment optional).

    Provide exactly one source: a local --audio file, or an open --url (a direct
    audio file or a podcast RSS enclosure). The audio never leaves your machine.
    By default this emits a synced transcript; add --gloss/--enrich for glosses
    and CEFR (needs the razbiram-nlp plugin).
    """
    console = Console()
    if (audio is None) == (url is None):
        raise click.UsageError("Gib genau eine Quelle an: --audio ODER --url.")

    want_enrich = enrich or gloss is not None
    if want_enrich and not is_available():
        raise click.ClickException(
            "Enrichment (--gloss/--enrich) needs the razbiram-nlp plugin. Install it with "
            "'pip install razbiram-listen[enrich]', or drop --gloss/--enrich for a synced "
            "transcript only."
        )

    if url is not None:
        try:
            audio = fetch_audio(url, dest_dir=out.parent, episode=episode)
        except SourceError as err:
            raise click.ClickException(str(err)) from err
        console.print(f"[green]↓[/green] geladen: [bold]{audio.name}[/bold]")

    assert audio is not None
    console.print(f"[bold]Processing[/bold] {audio.name} (model: {model}) …")

    labels = {
        "transcribe": "Transcribing",
        "enrich": "Analysing & translating",
        "align": "Aligning",
    }
    with Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        transient=True,
    ) as prog:
        task = prog.add_task("Transcribing", total=1.0)

        def on_event(stage: str, frac: float | None) -> None:
            if stage in labels:
                prog.update(task, description=labels[stage])
            if frac is None:
                if stage == "enrich":
                    prog.update(task, completed=0.0)  # restart the bar for glossing
            else:
                prog.update(task, completed=frac)

        result = process_audio(
            audio,
            gloss_lang=gloss,
            gloss_model=gloss_model,
            enrich=want_enrich,
            model_size=model,
            language=language,
            show_progress=False,
            on_event=on_event,
        )

    out.write_text(result.document.to_json(), encoding="utf-8")

    coverage = f"{result.stats.coverage:.0%}"
    tokens = result.stats.matched_word_tokens
    total = result.stats.total_word_tokens
    mode = "enriched (glosses/CEFR)" if result.enriched else "core (transcript only)"
    console.print(
        f"[green]✓[/green] wrote [bold]{out}[/bold] · {mode} · "
        f"{result.duration:.1f}s audio · alignment {coverage} ({tokens}/{total} words)"
    )
    if result.stats.total_word_tokens and result.stats.coverage < 0.5:
        console.print(
            "[yellow]![/yellow] low alignment coverage — the transcript may need editing "
            "in the viewer before the karaoke sync is reliable."
        )


if __name__ == "__main__":
    main()
