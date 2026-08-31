"""Acceso a la API de GitHub mediante PyGithub."""

from __future__ import annotations

from github import Auth, Github
from github.ContentFile import ContentFile
from github.GithubException import GithubException, UnknownObjectException

WORKFLOWS_PATH = ".github/workflows"


class GitHubClient:
    """Envoltorio delgado sobre PyGithub para lo único que Miner necesita:
    listar los archivos dentro de ``.github/workflows/`` de un repositorio.
    """

    def __init__(self, token: str, *, per_page: int = 100) -> None:
        if not token:
            raise ValueError("GITHUB_TOKEN vacío. Configúralo en el archivo .env")
        self._gh = Github(auth=Auth.Token(token), per_page=per_page)

    def list_workflow_files(self, full_name: str) -> list[str]:
        """Nombres de archivo dentro de ``.github/workflows/`` del repo.

        Devuelve una lista vacía si el repo no existe, es privado/inaccesible,
        o no contiene ese directorio.
        """
        try:
            repo = self._gh.get_repo(full_name)
            contents = repo.get_contents(WORKFLOWS_PATH)
        except UnknownObjectException:
            return []
        except GithubException as exc:
            if exc.status in (403, 404, 451):
                return []
            raise

        if isinstance(contents, ContentFile):  # el path resultó ser un archivo
            return [contents.name]
        return [c.name for c in contents if c.type == "file"]

    def rate_limit_remaining(self) -> int | None:
        try:
            return self._gh.get_rate_limit().core.remaining
        except GithubException:
            return None
