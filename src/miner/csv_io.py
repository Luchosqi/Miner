"""Lectura y escritura de archivos CSV con pandas.

El CSV de entrada puede pesar cientos de MB (una fila por repositorio, con
columnas que guardan JSON extenso). Para no agotar la memoria, se lee siempre
**por trozos** (``chunksize``): nunca hay un DataFrame con el archivo completo.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pandas as pd

from miner.models import CandidateRepo

# Nombres habituales de la columna que contiene "owner/repo"
_NAME_COLUMNS = ("name", "full_name", "fullName", "nameWithOwner", "repository", "repo")
# ... o una URL desde la que se puede derivar
_URL_COLUMNS = ("url", "html_url", "htmlUrl", "link", "repoUrl")

RESULT_COL = "uses_ghaw"
_CHUNK_ROWS = 20_000


def detect_name_column(path: str | Path) -> str:
    """Devuelve el nombre de la columna que identifica al repositorio."""
    header = pd.read_csv(path, nrows=0)
    for col in (*_NAME_COLUMNS, *_URL_COLUMNS):
        if col in header.columns:
            return col
    raise ValueError(
        "No se encontró una columna con el identificador del repositorio "
        f"(owner/repo o URL). Columnas disponibles: {list(header.columns)}"
    )


def iter_candidate_names(
    path: str | Path, *, chunksize: int = _CHUNK_ROWS
) -> Iterator[str]:
    """Itera los ``owner/repo`` del CSV, normalizados, leyendo por trozos."""
    column = detect_name_column(path)
    seen_any = False
    for chunk in pd.read_csv(path, usecols=[column], chunksize=chunksize):
        for raw in chunk[column]:
            seen_any = True
            yield CandidateRepo(full_name=str(raw)).full_name
    if not seen_any:
        raise ValueError(f"El CSV {str(path)!r} no contiene filas.")


def write_filtered(
    input_path: str | Path,
    hits: set[str],
    output_path: str | Path,
    *,
    enriched_path: str | Path | None = None,
    chunksize: int = _CHUNK_ROWS,
) -> int:
    """Reescribe el CSV agregando la columna binaria ``uses_ghaw``.

    * ``output_path``: solo las filas cuyo repo está en ``hits`` (entrega final).
    * ``enriched_path`` (opcional): todas las filas, con la columna agregada.

    Lee y escribe por trozos. Devuelve el número de filas escritas en
    ``output_path``.
    """
    column = detect_name_column(input_path)
    written = 0
    out_header_done = False
    enr_header_done = False

    for chunk in pd.read_csv(input_path, chunksize=chunksize):
        full_names = chunk[column].map(lambda x: CandidateRepo(full_name=str(x)).full_name)
        chunk = chunk.copy()
        chunk[RESULT_COL] = full_names.isin(hits).astype(int)

        if enriched_path is not None:
            chunk.to_csv(
                enriched_path, index=False, mode="w" if not enr_header_done else "a",
                header=not enr_header_done,
            )
            enr_header_done = True

        keep = chunk[chunk[RESULT_COL] == 1]
        if not keep.empty:
            keep.to_csv(
                output_path, index=False, mode="w" if not out_header_done else "a",
                header=not out_header_done,
            )
            out_header_done = True
            written += len(keep)

    if not out_header_done:  # ningún repo cumplió: dejar el CSV solo con encabezados
        header = pd.read_csv(input_path, nrows=0)
        header[RESULT_COL] = pd.Series(dtype=int)
        header.to_csv(output_path, index=False)

    return written
