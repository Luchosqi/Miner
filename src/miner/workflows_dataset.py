"""Construcción de las tablas relacionales del dataset GH-AW.

Esquema entidad-relación (ver docs/er-diagram.md y docs/data-dictionary.md):

    repositories (1) ----< workflow_files (1) ----< frontmatter_entries

* ``repositories``: un repositorio de GitHub que usa GH-AW.
* ``workflow_files``: un archivo ``.md`` de ``.github/workflows/`` de ese repo,
  con su body en Markdown ya separado del frontmatter.
* ``frontmatter_entries``: el frontmatter de cada archivo, aplanado a pares
  clave/valor (modelo entidad-atributo-valor), porque su esquema YAML es libre
  y varía de un workflow a otro.

Este módulo es puro (sin red ni disco): recibe registros ya obtenidos y
devuelve ``pandas.DataFrame``. Quien orquesta la escritura a Parquet es
``dataset_pipeline.py``.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from miner.frontmatter_parser import flatten_frontmatter, split_frontmatter


@dataclass(frozen=True)
class WorkflowFileRecord:
    """Un archivo ``.md`` de GH-AW ya descargado, pendiente de parsear."""

    full_name: str
    path: str
    raw_content: str


def build_tables(records: list[WorkflowFileRecord]) -> dict[str, pd.DataFrame]:
    """Construye las tres tablas del esquema a partir de archivos GH-AW crudos.

    Las claves primarias (``repo_id``, ``file_id``, ``entry_id``) se generan de
    forma determinística según el orden de aparición, para que la salida sea
    reproducible entre corridas con la misma entrada.
    """
    repo_rows: list[dict] = []
    file_rows: list[dict] = []
    entry_rows: list[dict] = []

    repo_ids: dict[str, int] = {}
    entry_id = 0

    for file_id, record in enumerate(records):
        if record.full_name not in repo_ids:
            repo_id = len(repo_ids)
            repo_ids[record.full_name] = repo_id
            owner, _, name = record.full_name.partition("/")
            repo_rows.append(
                {"repo_id": repo_id, "full_name": record.full_name, "owner": owner, "name": name}
            )
        repo_id = repo_ids[record.full_name]

        parsed = split_frontmatter(record.raw_content)
        file_rows.append(
            {
                "file_id": file_id,
                "repo_id": repo_id,
                "path": record.path,
                "filename": record.path.rsplit("/", 1)[-1],
                "body_markdown": parsed.body,
            }
        )

        for entry in flatten_frontmatter(parsed.metadata):
            entry_rows.append(
                {
                    "entry_id": entry_id,
                    "file_id": file_id,
                    "key_path": entry.key_path,
                    "value": entry.value,
                    "value_type": entry.value_type,
                }
            )
            entry_id += 1

    return {
        "repositories": pd.DataFrame(
            repo_rows, columns=["repo_id", "full_name", "owner", "name"]
        ),
        "workflow_files": pd.DataFrame(
            file_rows, columns=["file_id", "repo_id", "path", "filename", "body_markdown"]
        ),
        "frontmatter_entries": pd.DataFrame(
            entry_rows, columns=["entry_id", "file_id", "key_path", "value", "value_type"]
        ),
    }


def write_tables(tables: dict[str, pd.DataFrame], output_dir: str) -> dict[str, str]:
    """Escribe cada tabla como ``<output_dir>/<nombre>.parquet``. Devuelve las rutas."""
    from pathlib import Path

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    paths: dict[str, str] = {}
    for name, df in tables.items():
        path = out / f"{name}.parquet"
        df.to_parquet(path, index=False)
        paths[name] = str(path)
    return paths
