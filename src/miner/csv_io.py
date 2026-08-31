"""Lectura y escritura de archivos CSV con pandas."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from miner.models import CandidateRepo, RepoResult

# Nombres habituales de la columna que contiene "owner/repo"
_NAME_COLUMNS = ("name", "full_name", "fullName", "nameWithOwner", "repository", "repo")
# ... o una URL desde la que se puede derivar
_URL_COLUMNS = ("url", "html_url", "htmlUrl", "link", "repoUrl")

# Columna auxiliar que Miner agrega internamente
FULL_NAME_COL = "_full_name"
RESULT_COL = "uses_ghaw"


def read_candidates(path: str | Path) -> pd.DataFrame:
    """Lee el CSV de entrada y agrega la columna auxiliar ``_full_name``.

    Conserva todas las columnas originales intactas.
    """
    df = pd.read_csv(path)
    if df.empty:
        raise ValueError(f"El CSV {path!r} no contiene filas.")
    df[FULL_NAME_COL] = _derive_full_names(df)
    return df


def _derive_full_names(df: pd.DataFrame) -> pd.Series:
    source = _pick_column(df)
    return df[source].map(lambda x: CandidateRepo(full_name=str(x)).full_name)


def _pick_column(df: pd.DataFrame) -> str:
    for col in (*_NAME_COLUMNS, *_URL_COLUMNS):
        if col in df.columns:
            return col
    raise ValueError(
        "No se encontró una columna con el identificador del repositorio "
        f"(owner/repo o URL). Columnas disponibles: {list(df.columns)}"
    )


def write_results(
    df: pd.DataFrame,
    results: dict[str, RepoResult],
    output_path: str | Path,
    *,
    enriched_path: str | Path | None = None,
) -> pd.DataFrame:
    """Agrega la columna binaria ``uses_ghaw`` y escribe el/los CSV de salida.

    * ``output_path``: solo las filas con ``uses_ghaw == 1`` (entrega final).
    * ``enriched_path`` (opcional): todas las filas, con la columna agregada.

    Devuelve el DataFrame filtrado que se escribió en ``output_path``.
    """
    enriched = df.copy()
    enriched[RESULT_COL] = (
        enriched[FULL_NAME_COL].map(lambda fn: int(results[fn].uses_ghaw)).astype(int)
    )
    enriched = enriched.drop(columns=[FULL_NAME_COL])

    if enriched_path is not None:
        enriched.to_csv(enriched_path, index=False)

    filtered = enriched[enriched[RESULT_COL] == 1].reset_index(drop=True)
    filtered.to_csv(output_path, index=False)
    return filtered
