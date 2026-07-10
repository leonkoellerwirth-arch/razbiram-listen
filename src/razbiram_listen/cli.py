"""Command-line entry point for razbiram-listen.

M1 provides the CLI scaffold only. The end-to-end ``process`` command (audio →
``.listen.json``) is wired up in M4, once transcribe (M2) and align (M3) land.
"""

from __future__ import annotations

import click

from . import __version__


@click.group()
@click.version_option(__version__, prog_name="razbiram-listen")
def main() -> None:
    """Local-first Bulgarian listening studio (BYO audio)."""


if __name__ == "__main__":
    main()
