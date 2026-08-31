"""Acceso a la API de GitHub mediante HTTPX y GraphQL.

El dataset de candidatos tiene cientos de miles de repositorios. Consultarlos
uno por uno con la API REST (una petición por repo) es inviable frente al límite
de 5.000 peticiones/hora. GraphQL permite pedir el contenido de
``.github/workflows/`` de **muchos repositorios en una sola petición** mediante
alias, y ese lote completo cuesta 1 punto del presupuesto horario.

Este módulo separa dos responsabilidades:

* funciones puras (``build_query`` / ``parse_batch_response``) — cubiertas por tests;
* la clase ``GitHubGraphQLClient`` — la parte que habla por red.
"""

from __future__ import annotations

import sys
import time
from collections.abc import Sequence

import httpx


def _log(message: str) -> None:
    print(f"[miner] {message}", file=sys.stderr, flush=True)

GRAPHQL_URL = "https://api.github.com/graphql"
WORKFLOWS_EXPRESSION = "HEAD:.github/workflows"

# Nombres de archivo dentro de .github/workflows/, o None si el repo no es
# accesible (no existe, es privado, fue renombrado, etc.).
WorkflowFiles = list[str] | None


def _alias(index: int) -> str:
    return f"r{index}"


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def build_query(full_names: Sequence[str]) -> str:
    """Arma una consulta GraphQL que pide, por cada repo, los archivos que hay
    dentro de ``.github/workflows/`` (en su rama por defecto)."""
    parts = ["rateLimit { cost remaining resetAt }"]
    for i, full_name in enumerate(full_names):
        owner, _, name = full_name.partition("/")
        parts.append(
            f'{_alias(i)}: repository(owner: "{_escape(owner)}", name: "{_escape(name)}") {{ '
            f'object(expression: "{WORKFLOWS_EXPRESSION}") {{ '
            f"... on Tree {{ entries {{ name }} }} }} }}"
        )
    return "query {\n  " + "\n  ".join(parts) + "\n}"


def parse_batch_response(
    full_names: Sequence[str], data: dict | None
) -> dict[str, WorkflowFiles]:
    """Traduce el ``data`` de la respuesta GraphQL a ``{repo: [archivos] | None}``.

    * ``None``  -> el repositorio no es accesible.
    * ``[]``    -> el repositorio existe pero no tiene ``.github/workflows/``.
    * ``[...]`` -> nombres de archivo dentro de ``.github/workflows/``.
    """
    data = data or {}
    result: dict[str, WorkflowFiles] = {}
    for i, full_name in enumerate(full_names):
        node = data.get(_alias(i))
        if node is None:
            result[full_name] = None
            continue
        tree = node.get("object")
        if not tree:
            result[full_name] = []
            continue
        result[full_name] = [entry["name"] for entry in tree.get("entries", [])]
    return result


class GitHubGraphQLClient:
    """Cliente GraphQL sobre HTTPX, con reintentos y respeto del rate limit."""

    _RETRY_STATUS = {500, 502, 503, 504}

    def __init__(
        self,
        token: str,
        *,
        timeout: float = 60.0,
        max_retries: int = 8,
        min_remaining: int = 50,
        request_delay: float = 0.0,
        max_backoff: float = 300.0,
    ) -> None:
        if not token:
            raise ValueError("GITHUB_TOKEN vacío. Configúralo en el archivo .env")
        self._client = httpx.Client(
            headers={
                "Authorization": f"bearer {token}",
                "User-Agent": "miner-ghaw",
            },
            timeout=timeout,
        )
        self._max_retries = max_retries
        self._min_remaining = min_remaining
        self._request_delay = request_delay
        self._max_backoff = max_backoff

    # -- API pública -----------------------------------------------------------

    def fetch_workflow_files(self, full_names: Sequence[str]) -> dict[str, WorkflowFiles]:
        """Consulta un lote de repos y devuelve ``{repo: [archivos] | None}``."""
        body = self._post_with_retry({"query": build_query(full_names)})
        data = body.get("data")
        self._respect_rate_limit(data)
        if self._request_delay:
            time.sleep(self._request_delay)
        return parse_batch_response(full_names, data)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "GitHubGraphQLClient":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # -- interno -------------------------------------------------------------

    def _post_with_retry(self, payload: dict) -> dict:
        last_error: Exception | None = None
        for attempt in range(self._max_retries):
            try:
                resp = self._client.post(GRAPHQL_URL, json=payload)
            except httpx.TransportError as exc:  # red inestable
                last_error = exc
                time.sleep(min(2**attempt, 30))
                continue

            if resp.status_code in self._RETRY_STATUS:
                time.sleep(min(2**attempt, 30))
                continue
            if resp.status_code in (403, 429):  # rate limit secundario / abuso
                retry_after = resp.headers.get("Retry-After")
                reset = resp.headers.get("x-ratelimit-reset")
                if retry_after is not None:
                    wait = float(retry_after)
                elif reset is not None:
                    wait = max(float(reset) - time.time(), 30.0)
                else:
                    wait = min(60.0 * (attempt + 1), self._max_backoff)
                wait = min(max(wait, 30.0), self._max_backoff)
                _log(f"HTTP {resp.status_code} (rate limit); esperando {wait:.0f}s")
                time.sleep(wait)
                continue

            resp.raise_for_status()
            body = resp.json()

            if body.get("data") is None and body.get("errors"):
                message = str(body["errors"][0].get("message", "")).lower()
                if "rate limit" in message or "timeout" in message:
                    _log(f"GraphQL: {message[:80]}; esperando 60s")
                    time.sleep(60)
                    continue
                raise RuntimeError(f"GraphQL error: {body['errors'][:2]}")
            return body

        raise RuntimeError(f"GraphQL: reintentos agotados ({last_error})")

    def _respect_rate_limit(self, data: dict | None) -> None:
        info = (data or {}).get("rateLimit") or {}
        remaining = info.get("remaining")
        reset_at = info.get("resetAt")
        if remaining is None or remaining > self._min_remaining:
            return
        try:
            from datetime import datetime, timezone

            reset = datetime.fromisoformat(reset_at.replace("Z", "+00:00"))
            wait = (reset - datetime.now(timezone.utc)).total_seconds()
        except Exception:  # noqa: BLE001
            wait = 60.0
        if wait > 0:
            _log(f"presupuesto GraphQL casi agotado (remaining={remaining}); esperando {wait:.0f}s al reset")
            time.sleep(wait + 1)
