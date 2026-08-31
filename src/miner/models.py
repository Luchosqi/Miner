"""Modelos de datos (Pydantic) que usa Miner."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class CandidateRepo(BaseModel):
    """Un repositorio candidato leído del CSV de entrada.

    Acepta tanto ``owner/repo`` como una URL de GitHub y la normaliza a
    ``owner/repo``.
    """

    full_name: str = Field(..., description="Identificador del repo en forma owner/repo")

    @field_validator("full_name")
    @classmethod
    def _normalize(cls, value: str) -> str:
        v = value.strip().strip("/")
        if v.startswith(("http://", "https://", "git@")):
            v = v.replace("git@github.com:", "").removesuffix(".git")
            parts = [p for p in v.split("/") if p]
            v = "/".join(parts[-2:])
        if v.count("/") != 1 or not all(v.split("/")):
            raise ValueError(f"{value!r} no tiene forma owner/repo")
        return v


class RepoResult(BaseModel):
    """Resultado del análisis de un repositorio."""

    full_name: str
    uses_ghaw: bool
    ghaw_files: list[str] = Field(default_factory=list)
    error: str | None = None
