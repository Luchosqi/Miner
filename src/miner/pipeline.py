"""Orquestación del proceso completo de Miner."""

from __future__ import annotations

import json
from collections.abc import Iterator, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import Lock

import pandas as pd
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)

from miner.csv_io import FULL_NAME_COL, read_candidates, write_results
from miner.detector import find_ghaw_pairs
from miner.github_client import GitHubGraphQLClient
from miner.models import RepoResult


def _chunks(seq: Sequence[str], size: int) -> Iterator[list[str]]:
    for start in range(0, len(seq), size):
        yield list(seq[start : start + size])


def result_from_files(full_name: str, files: list[str] | None) -> RepoResult:
    """Construye el ``RepoResult`` a partir de los archivos de .github/workflows/."""
    if files is None:
        return RepoResult(full_name=full_name, uses_ghaw=False, error="repo no accesible")
    pairs = find_ghaw_pairs(files)
    return RepoResult(
        full_name=full_name,
        uses_ghaw=bool(pairs),
        ghaw_files=[f"{base}.md" for base in pairs],
    )


def _load_checkpoint(path: Path) -> dict[str, RepoResult]:
    if not path.exists():
        return {}
    done: dict[str, RepoResult] = {}
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                done_obj = RepoResult(**json.loads(line))
            except Exception:  # noqa: BLE001 - línea corrupta: se reintenta el repo
                continue
            done[done_obj.full_name] = done_obj
    return done


def run(
    input_csv: str | Path,
    output_csv: str | Path,
    token: str,
    *,
    batch_size: int = 50,
    workers: int = 4,
    enriched_csv: str | Path | None = None,
    checkpoint_path: str | Path | None = ".miner_checkpoint.jsonl",
) -> tuple[dict[str, RepoResult], pd.DataFrame]:
    """Pipeline completo: leer CSV -> consultar GitHub (GraphQL) -> filtrar -> escribir CSV.

    Escribe cada resultado en un checkpoint JSONL; si el proceso se interrumpe,
    volver a ejecutarlo retoma donde quedó.
    """
    df = read_candidates(input_csv)
    all_names = list(dict.fromkeys(df[FULL_NAME_COL].tolist()))  # únicos, orden estable

    checkpoint = Path(checkpoint_path) if checkpoint_path else None
    results: dict[str, RepoResult] = _load_checkpoint(checkpoint) if checkpoint else {}
    pending = [name for name in all_names if name not in results]

    ck_lock = Lock()
    ck_file = checkpoint.open("a", encoding="utf-8") if checkpoint else None

    columns = (
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        TextColumn("<"),
        TimeRemainingColumn(),
    )

    try:
        with GitHubGraphQLClient(token) as client, Progress(*columns) as progress:
            task = progress.add_task(
                "Analizando repositorios", total=len(all_names), completed=len(results)
            )

            def handle_batch(batch: list[str]) -> list[RepoResult]:
                mapping = client.fetch_workflow_files(batch)
                return [result_from_files(name, files) for name, files in mapping.items()]

            with ThreadPoolExecutor(max_workers=workers) as pool:
                futures = {
                    pool.submit(handle_batch, batch): batch
                    for batch in _chunks(pending, batch_size)
                }
                for future in as_completed(futures):
                    batch_results = future.result()
                    for res in batch_results:
                        results[res.full_name] = res
                    if ck_file is not None:
                        with ck_lock:
                            for res in batch_results:
                                ck_file.write(res.model_dump_json() + "\n")
                            ck_file.flush()
                    progress.advance(task, len(batch_results))
    finally:
        if ck_file is not None:
            ck_file.close()

    filtered = write_results(df, results, output_csv, enriched_path=enriched_csv)
    return results, filtered
