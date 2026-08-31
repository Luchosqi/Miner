"""Interfaz de línea de comandos de Miner (Typer)."""

from __future__ import annotations

import os
from pathlib import Path

import typer
from dotenv import load_dotenv
from rich import print as rprint

from miner.pipeline import run

app = typer.Typer(
    add_completion=False,
    help="Miner: identifica repositorios de GitHub que usan GitHub Agentic Workflows (GH-AW).",
)


@app.command()
def main(
    input_csv: Path = typer.Argument(
        ...,
        exists=True,
        dir_okay=False,
        readable=True,
        help="CSV de entrada con los repositorios candidatos.",
    ),
    output: Path = typer.Option(
        "repositorios_ghaw.csv",
        "--output",
        "-o",
        help="CSV de salida: solo los repositorios que usan GH-AW.",
    ),
    enriched: Path = typer.Option(
        None,
        "--enriched",
        help="Opcional: CSV con TODAS las filas y la columna binaria 'uses_ghaw'.",
    ),
    workers: int = typer.Option(
        8, "--workers", "-w", min=1, max=32, help="Consultas concurrentes a la API de GitHub."
    ),
) -> None:
    """Lee el CSV, consulta cada repo en GitHub, detecta GH-AW y escribe el CSV filtrado."""
    load_dotenv()
    token = os.getenv("GITHUB_TOKEN", "").strip()
    if not token:
        rprint(
            "[red]Falta GITHUB_TOKEN.[/red] Crea un archivo .env junto a este proyecto con:\n"
            "  GITHUB_TOKEN=tu_token_de_github"
        )
        raise typer.Exit(code=1)

    results, filtered = run(
        input_csv, output, token, workers=workers, enriched_csv=enriched
    )

    total = len(results)
    hits = sum(1 for r in results.values() if r.uses_ghaw)
    errors = sum(1 for r in results.values() if r.error)

    rprint(
        f"\n[green]Proceso terminado.[/green] "
        f"{total} repos analizados · [bold]{hits}[/bold] usan GH-AW · {errors} con error."
    )
    rprint(f"CSV de salida: [bold]{output}[/bold] ({len(filtered)} filas)")
    if enriched:
        rprint(f"CSV enriquecido: [bold]{enriched}[/bold] ({total} filas)")


def entrypoint() -> None:
    """Punto de entrada para el script de consola ``miner``."""
    app()


if __name__ == "__main__":
    entrypoint()
