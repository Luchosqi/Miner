"""Orquestación del proceso completo de Miner."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd
from rich.progress import BarColumn, MofNCompleteColumn, Progress, TextColumn, TimeElapsedColumn

from miner.csv_io import FULL_NAME_COL, read_candidates, write_results
from miner.detector import find_ghaw_pairs
from miner.github_client import GitHubClient
from miner.models import RepoResult


def analyze_repo(client: GitHubClient, full_name: str) -> RepoResult:
    """Consulta un repo y determina si usa GH-AW."""
    try:
        files = client.list_workflow_files(full_name)
    except Exception as exc:  # noqa: BLE001 - se registra en el resultado
        return RepoResult(full_name=full_name, uses_ghaw=False, error=str(exc))

    pairs = find_ghaw_pairs(files)
    return RepoResult(
        full_name=full_name,
        uses_ghaw=bool(pairs),
        ghaw_files=[f"{base}.md" for base in pairs],
    )


def run(
    input_csv: str | Path,
    output_csv: str | Path,
    token: str,
    *,
    workers: int = 8,
    enriched_csv: str | Path | None = None,
) -> tuple[dict[str, RepoResult], pd.DataFrame]:
    """Ejecuta el pipeline: leer CSV -> consultar GitHub -> filtrar -> escribir CSV."""
    df = read_candidates(input_csv)
    names = list(dict.fromkeys(df[FULL_NAME_COL].tolist()))  # únicos, orden estable
    client = GitHubClient(token)

    results: dict[str, RepoResult] = {}
    columns = (
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
    )
    with Progress(*columns) as progress, ThreadPoolExecutor(max_workers=workers) as pool:
        task = progress.add_task("Analizando repositorios", total=len(names))
        futures = {pool.submit(analyze_repo, client, name): name for name in names}
        for future in as_completed(futures):
            result = future.result()
            results[result.full_name] = result
            progress.advance(task)

    filtered = write_results(df, results, output_csv, enriched_path=enriched_csv)
    return results, filtered
