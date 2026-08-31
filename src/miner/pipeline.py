"""Orquestación del proceso completo de Miner.

Diseñado para operar con memoria acotada aunque el CSV tenga cientos de miles
de filas: el CSV se lee por trozos y durante la fase de red no se acumulan
objetos por repositorio, solo un conjunto de nombres y contadores.
"""

from __future__ import annotations

import json
from collections.abc import Iterator, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from threading import Lock

from miner.csv_io import iter_candidate_names, write_filtered
from miner.detector import find_ghaw_pairs
from miner.github_client import GitHubGraphQLClient, _log
from miner.models import RepoResult


@dataclass
class RunSummary:
    analyzed: int
    hits: int
    errors: int
    written: int


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


def _load_checkpoint(path: Path) -> tuple[set[str], set[str], int]:
    """Devuelve ``(procesados, con_ghaw, n_errores)`` a partir del checkpoint JSONL."""
    processed: set[str] = set()
    hits: set[str] = set()
    errors = 0
    if not path.exists():
        return processed, hits, errors
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                name = obj["full_name"]
            except Exception:  # noqa: BLE001 - línea corrupta: se reintenta el repo
                continue
            processed.add(name)
            if obj.get("uses_ghaw"):
                hits.add(name)
            if obj.get("error"):
                errors += 1
    return processed, hits, errors


def run(
    input_csv: str | Path,
    output_csv: str | Path,
    token: str,
    *,
    batch_size: int = 50,
    workers: int = 2,
    request_delay: float = 0.3,
    enriched_csv: str | Path | None = None,
    checkpoint_path: str | Path | None = ".miner_checkpoint.jsonl",
) -> RunSummary:
    """Pipeline completo: leer CSV -> consultar GitHub (GraphQL) -> filtrar -> escribir CSV.

    Escribe cada resultado en un checkpoint JSONL; si el proceso se interrumpe,
    volver a ejecutarlo retoma donde quedó.
    """
    all_names = list(dict.fromkeys(iter_candidate_names(input_csv)))  # únicos, orden estable

    checkpoint = Path(checkpoint_path) if checkpoint_path else None
    processed, hits, errors = _load_checkpoint(checkpoint) if checkpoint else (set(), set(), 0)
    pending = [name for name in all_names if name not in processed]

    ck_lock = Lock()
    ck_file = checkpoint.open("a", encoding="utf-8") if checkpoint else None

    _log(f"{len(all_names)} repos en el CSV · {len(processed)} ya procesados · {len(pending)} pendientes")

    try:
        with GitHubGraphQLClient(token, request_delay=request_delay) as client:

            def handle_batch(batch: list[str]) -> list[RepoResult]:
                mapping = client.fetch_workflow_files(batch)
                return [result_from_files(name, files) for name, files in mapping.items()]

            done_since_log = 0
            with ThreadPoolExecutor(max_workers=workers) as pool:
                futures = {
                    pool.submit(handle_batch, batch): batch
                    for batch in _chunks(pending, batch_size)
                }
                for future in as_completed(futures):
                    batch_results = future.result()
                    for res in batch_results:
                        processed.add(res.full_name)
                        if res.uses_ghaw:
                            hits.add(res.full_name)
                        if res.error:
                            errors += 1
                    if ck_file is not None:
                        with ck_lock:
                            for res in batch_results:
                                ck_file.write(res.model_dump_json() + "\n")
                            ck_file.flush()
                    done_since_log += len(batch_results)
                    if done_since_log >= 5000:
                        done_since_log = 0
                        _log(f"{len(processed)}/{len(all_names)} repos · {len(hits)} usan GH-AW")
    finally:
        if ck_file is not None:
            ck_file.close()

    _log("Consultas terminadas; escribiendo CSV de salida...")
    written = write_filtered(input_csv, hits, output_csv, enriched_path=enriched_csv)
    return RunSummary(
        analyzed=len(processed), hits=len(hits), errors=errors, written=written
    )
