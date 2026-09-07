"""Pruebas de construcción de las tablas relacionales del dataset GH-AW."""

from miner.workflows_dataset import WorkflowFileRecord, build_tables

FILE_A = """---
on: push
engine: claude
---
# Reporte A
"""

FILE_B = """---
on: schedule
permissions:
  contents: read
---
# Reporte B
"""


class TestBuildTables:
    def test_una_fila_por_repo_archivo_y_entrada(self):
        records = [
            WorkflowFileRecord("owner/repo1", ".github/workflows/a.md", FILE_A),
            WorkflowFileRecord("owner/repo1", ".github/workflows/b.md", FILE_B),
            WorkflowFileRecord("owner/repo2", ".github/workflows/a.md", FILE_A),
        ]
        tables = build_tables(records)

        repos = tables["repositories"]
        files = tables["workflow_files"]
        entries = tables["frontmatter_entries"]

        assert len(repos) == 2
        assert set(repos["full_name"]) == {"owner/repo1", "owner/repo2"}
        assert len(files) == 3
        assert (files["filename"] == "a.md").sum() == 2
        assert "# Reporte A" in files.iloc[0]["body_markdown"]

        # repo1 tiene 2 archivos -> ambos file_id deben apuntar al mismo repo_id
        repo1_id = repos.loc[repos["full_name"] == "owner/repo1", "repo_id"].item()
        repo1_files = files[files["repo_id"] == repo1_id]
        assert len(repo1_files) == 2

        # entradas del frontmatter aplanado, ligadas al file_id correcto
        b_file_id = files.loc[
            (files["repo_id"] == repo1_id) & (files["filename"] == "b.md"), "file_id"
        ].item()
        b_entries = entries[entries["file_id"] == b_file_id]
        assert set(b_entries["key_path"]) == {"on", "permissions.contents"}

    def test_sin_registros(self):
        tables = build_tables([])
        assert list(tables["repositories"].columns) == ["repo_id", "full_name", "owner", "name"]
        assert len(tables["repositories"]) == 0
        assert len(tables["workflow_files"]) == 0
        assert len(tables["frontmatter_entries"]) == 0

    def test_claves_primarias_unicas(self):
        records = [
            WorkflowFileRecord("a/b", ".github/workflows/x.md", FILE_A),
            WorkflowFileRecord("c/d", ".github/workflows/x.md", FILE_B),
        ]
        tables = build_tables(records)
        assert tables["repositories"]["repo_id"].is_unique
        assert tables["workflow_files"]["file_id"].is_unique
        assert tables["frontmatter_entries"]["entry_id"].is_unique
