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
    batch_size: int = typer.Option(
        50, "--batch-size", "-b", min=1, max=100, help="Repositorios por consulta GraphQL."
    ),
    workers: int = typer.Option(
        2, "--workers", "-w", min=1, max=16, help="Consultas GraphQL concurrentes."
    ),
    request_delay: float = typer.Option(
        0.3,
        "--request-delay",
        min=0.0,
        help="Pausa (s) tras cada consulta, para no gatillar el rate limit secundario.",
    ),
    checkpoint: Path = typer.Option(
        ".miner_checkpoint.jsonl",
        "--checkpoint",
        help="Archivo de avance; volver a ejecutar retoma donde quedó.",
    ),
    no_checkpoint: bool = typer.Option(
        False, "--no-checkpoint", help="Desactiva el checkpoint (empieza de cero)."
    ),
) -> None:
    """Lee el CSV, consulta cada repo en GitHub vía GraphQL, detecta GH-AW y escribe el CSV filtrado."""
    load_dotenv()
    token = os.getenv("GITHUB_TOKEN", "").strip()
    if not token:
        rprint(
            "[red]Falta GITHUB_TOKEN.[/red] Crea un archivo .env junto a este proyecto con:\n"
            "  GITHUB_TOKEN=tu_token_de_github"
        )
        raise typer.Exit(code=1)

    results, filtered = run(
        input_csv,
        output,
        token,
        batch_size=batch_size,
        workers=workers,
        request_delay=request_delay,
        enriched_csv=enriched,
        checkpoint_path=None if no_checkpoint else checkpoint,
    )

    total = len(results)
    hits = sum(1 for r in results.values() if r.uses_ghaw)
    errors = sum(1 for r in results.values() if r.error)

    rprint(
        f"\n[green]Proceso terminado.[/green] "
        f"{total} repos analizados · [bold]{hits}[/bold] usan GH-AW · {errors} no accesibles."
    )
    rprint(f"CSV de salida: [bold]{output}[/bold] ({len(filtered)} filas)")
    if enriched:
        rprint(f"CSV enriquecido: [bold]{enriched}[/bold] ({total} filas)")


def entrypoint() -> None:
    """Punto de entrada para el script de consola ``miner``."""
    app()


if __name__ == "__main__":
    entrypoint()
