"""Orquestación del proceso que construye el dataset relacional GH-AW.

Toma el CSV de repositorios que usan GH-AW (salida de ``miner mine``), vuelve a
listar ``.github/workflows/`` de cada uno para ubicar los archivos ``.md``
válidos (los que tienen su ``.lock.yml`` correspondiente), descarga su
contenido y arma las tablas ``repositories`` / ``workflow_files`` /
``frontmatter_entries`` como Parquet.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path

from miner.csv_io import iter_candidate_names
from miner.detector import find_ghaw_pairs
from miner.github_client import FileRef, GitHubGraphQLClient, _log
from miner.workflows_dataset import WorkflowFileRecord, build_tables, write_tables

WORKFLOWS_DIR = ".github/workflows"


@dataclass
class DatasetSummary:
    repos_analyzed: int
    files_found: int
    files_downloaded: int
    table_paths: dict[str, str]


def _chunks(seq: Sequence, size: int) -> Iterator[list]:
    for start in range(0, len(seq), size):
        yield list(seq[start : start + size])


def _list_md_files(
    client: GitHubGraphQLClient, full_names: list[str], *, batch_size: int
) -> list[FileRef]:
    """Para cada repo, lista .github/workflows/ y devuelve los .md con par .lock.yml."""
    refs: list[FileRef] = []
    for batch in _chunks(full_names, batch_size):
        mapping = client.fetch_workflow_files(batch)
        for full_name, files in mapping.items():
            if not files:
                continue
            for base in find_ghaw_pairs(files):
                refs.append((full_name, f"{WORKFLOWS_DIR}/{base}.md"))
    return refs


def _download_contents(
    client: GitHubGraphQLClient, refs: list[FileRef], *, batch_size: int
) -> list[WorkflowFileRecord]:
    records: list[WorkflowFileRecord] = []
    for batch in _chunks(refs, batch_size):
        contents = client.fetch_file_contents(batch)
        for ref, text in contents.items():
            if text is None:
                continue
            full_name, path = ref
            records.append(WorkflowFileRecord(full_name=full_name, path=path, raw_content=text))
    return records


def run(
    input_csv: str | Path,
    output_dir: str | Path,
    token: str,
    *,
    batch_size: int = 50,
    request_delay: float = 0.3,
) -> DatasetSummary:
    """Pipeline completo: leer CSV -> listar workflows -> descargar .md -> Parquet."""
    full_names = list(dict.fromkeys(iter_candidate_names(input_csv)))
    _log(f"{len(full_names)} repos en el CSV de entrada")

    with GitHubGraphQLClient(token, request_delay=request_delay) as client:
        refs = _list_md_files(client, full_names, batch_size=batch_size)
        _log(f"{len(refs)} archivos .md de GH-AW encontrados; descargando contenido...")
        records = _download_contents(client, refs, batch_size=batch_size)

    _log(f"{len(records)} archivos descargados; construyendo tablas...")
    tables = build_tables(records)
    table_paths = write_tables(tables, str(output_dir))

    return DatasetSummary(
        repos_analyzed=len(full_names),
        files_found=len(refs),
        files_downloaded=len(records),
        table_paths=table_paths,
    )
