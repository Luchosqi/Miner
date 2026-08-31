"""Lógica pura para identificar GitHub Agentic Workflows (GH-AW).

Un repositorio usa GH-AW cuando, dentro de ``.github/workflows/``, existe al
menos un par de archivos que comparten el mismo nombre base:

* ``<base>.md``       (definición del workflow agéntico)
* ``<base>.lock.yml`` (workflow compilado por GH-AW)

Ejemplo: ``daily-report.md`` + ``daily-report.lock.yml``.

Este módulo no depende de la red ni de GitHub: recibe una lista de nombres de
archivo y responde. Por eso es el núcleo cubierto por las pruebas.
"""

from __future__ import annotations

from collections.abc import Iterable

MD_SUFFIX = ".md"
LOCK_SUFFIX = ".lock.yml"


def _bases_with_suffix(filenames: Iterable[str], suffix: str) -> set[str]:
    """Nombres base de los archivos que terminan exactamente en ``suffix``."""
    return {
        name[: -len(suffix)]
        for name in filenames
        if name.endswith(suffix) and len(name) > len(suffix)
    }


def find_ghaw_pairs(filenames: Iterable[str]) -> list[str]:
    """Devuelve, ordenadas, las bases que tienen tanto ``.md`` como ``.lock.yml``.

    Un archivo ``x.lock.yml`` termina en ``.yml`` pero nunca en ``.md``, así que
    los dos conjuntos de bases no se contaminan entre sí.
    """
    names = list(filenames)
    md_bases = _bases_with_suffix(names, MD_SUFFIX)
    lock_bases = _bases_with_suffix(names, LOCK_SUFFIX)
    return sorted(md_bases & lock_bases)


def uses_ghaw(filenames: Iterable[str]) -> bool:
    """``True`` si hay al menos un par (``.md`` + ``.lock.yml``) con la misma base."""
    return bool(find_ghaw_pairs(filenames))
