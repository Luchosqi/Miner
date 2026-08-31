"""Pruebas de lectura/escritura de CSV y del modelo de datos."""

import pandas as pd
import pytest

from miner.csv_io import read_candidates, write_results
from miner.models import CandidateRepo, RepoResult


class TestCandidateRepo:
    def test_owner_repo_directo(self):
        assert CandidateRepo(full_name="octocat/Hello-World").full_name == "octocat/Hello-World"

    def test_desde_url_https(self):
        assert (
            CandidateRepo(full_name="https://github.com/octocat/Hello-World").full_name
            == "octocat/Hello-World"
        )

    def test_espacios_y_barras_sobrantes(self):
        assert CandidateRepo(full_name="  octocat/Hello-World/ ").full_name == "octocat/Hello-World"

    def test_valor_invalido(self):
        with pytest.raises(ValueError):
            CandidateRepo(full_name="no-es-un-repo")


class TestReadCandidates:
    def test_lee_columna_name(self, tmp_path):
        csv = tmp_path / "in.csv"
        pd.DataFrame({"name": ["a/b", "c/d"], "stars": [1, 2]}).to_csv(csv, index=False)
        df = read_candidates(csv)
        assert list(df["_full_name"]) == ["a/b", "c/d"]
        assert "stars" in df.columns

    def test_sin_columna_reconocible(self, tmp_path):
        csv = tmp_path / "in.csv"
        pd.DataFrame({"foo": ["x"]}).to_csv(csv, index=False)
        with pytest.raises(ValueError):
            read_candidates(csv)


class TestWriteResults:
    def test_filtra_y_agrega_columna_binaria(self, tmp_path):
        csv = tmp_path / "in.csv"
        pd.DataFrame({"name": ["a/b", "c/d"], "stars": [10, 20]}).to_csv(csv, index=False)
        df = read_candidates(csv)
        results = {
            "a/b": RepoResult(full_name="a/b", uses_ghaw=True),
            "c/d": RepoResult(full_name="c/d", uses_ghaw=False),
        }
        out = tmp_path / "out.csv"
        enriched = tmp_path / "enriched.csv"
        filtered = write_results(df, results, out, enriched_path=enriched)

        assert list(filtered["name"]) == ["a/b"]
        assert list(filtered["uses_ghaw"]) == [1]
        assert "_full_name" not in filtered.columns

        full = pd.read_csv(enriched)
        assert list(full["uses_ghaw"]) == [1, 0]
        assert list(full.columns) == ["name", "stars", "uses_ghaw"]
