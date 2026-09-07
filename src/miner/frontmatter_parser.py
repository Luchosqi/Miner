"""Separación y aplanamiento del frontmatter YAML de los archivos GH-AW.

Cada archivo ``.md`` de GH-AW tiene un frontmatter YAML (entre líneas ``---``)
seguido de un body en Markdown. El frontmatter es de esquema libre (claves y
anidamiento variables entre workflows), así que en vez de forzarlo a columnas
fijas se aplana a pares ``(ruta_clave, valor, tipo)`` -- un modelo
entidad-atributo-valor que representa cualquier YAML sin perder información.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import frontmatter
import yaml

# GH-AW usa la clave YAML "on:" (el disparador del workflow, igual que en GitHub
# Actions). El resolver de booleanos de YAML 1.1 interpreta las claves/valores
# sin comillas "on"/"off"/"yes"/"no" como booleanos, lo que rompe el parseo
# (una clave ``True`` no es válida) y perdería el nombre real de la clave. Este
# loader restringe el tipo booleano a "true"/"false" únicamente.
class _GhawSafeLoader(yaml.SafeLoader):
    pass


_GhawSafeLoader.yaml_implicit_resolvers = {
    first_char: [
        (tag, regexp) for tag, regexp in resolvers if tag != "tag:yaml.org,2002:bool"
    ]
    for first_char, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
}
_GhawSafeLoader.add_implicit_resolver(
    "tag:yaml.org,2002:bool",
    re.compile(r"^(?:true|True|TRUE|false|False|FALSE)$"),
    list("tTfF"),
)


@dataclass(frozen=True)
class ParsedWorkflow:
    """Frontmatter (YAML) y body (Markdown) de un archivo GH-AW."""

    metadata: dict[str, Any]
    body: str


@dataclass(frozen=True)
class FrontmatterEntry:
    """Un par clave/valor aplanado del frontmatter."""

    key_path: str
    value: str
    value_type: str


def split_frontmatter(raw_content: str) -> ParsedWorkflow:
    """Separa el frontmatter YAML del body Markdown de un archivo GH-AW."""
    handler = frontmatter.YAMLHandler()
    if not handler.detect(raw_content):
        return ParsedWorkflow(metadata={}, body=raw_content)
    fm_text, content = handler.split(raw_content)
    metadata = yaml.load(fm_text, Loader=_GhawSafeLoader) or {}
    return ParsedWorkflow(metadata=metadata, body=content)


def _type_name(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, (dict, list)):
        return "json"
    return "str"


def _scalar_to_str(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def flatten_frontmatter(metadata: dict[str, Any], *, sep: str = ".") -> list[FrontmatterEntry]:
    """Aplana un frontmatter YAML (posiblemente anidado) a una lista de entradas.

    * dicts  -> se recorren recursivamente, concatenando la clave con ``sep``.
    * lists  -> se serializan como JSON en una sola entrada (``value_type="json"``).
    * scalar -> una entrada con su tipo (``str``, ``int``, ``float``, ``bool``, ``null``).
    """
    import json

    entries: list[FrontmatterEntry] = []
    if not metadata:
        return entries

    def walk(prefix: str, value: Any) -> None:
        if isinstance(value, dict):
            if not value:
                entries.append(FrontmatterEntry(prefix, "{}", "json"))
                return
            for key, sub_value in value.items():
                child_prefix = f"{prefix}{sep}{key}" if prefix else str(key)
                walk(child_prefix, sub_value)
        elif isinstance(value, list):
            entries.append(FrontmatterEntry(prefix, json.dumps(value, ensure_ascii=False), "json"))
        else:
            entries.append(FrontmatterEntry(prefix, _scalar_to_str(value), _type_name(value)))

    walk("", metadata)
    return entries
