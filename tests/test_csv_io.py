"""Pruebas de lectura/escritura de CSV (por trozos) y del modelo de datos."""

import pandas as pd
import pytest

from miner.csv_io import detect_name_column, iter_candidate_names, write_filtered
from miner.models import CandidateRepo


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


class TestDetectNameColumn:
    def test_encuentra_name(self, tmp_path):
        csv = tmp_path / "in.csv"
        pd.DataFrame({"name": ["a/b"], "stars": [1]}).to_csv(csv, index=False)
        assert detect_name_column(csv) == "name"

    def test_sin_columna_reconocible(self, tmp_path):
        csv = tmp_path / "in.csv"
        pd.DataFrame({"foo": ["x"]}).to_csv(csv, index=False)
        with pytest.raises(ValueError):
            detect_name_column(csv)


class TestIterCandidateNames:
    def test_itera_y_normaliza(self, tmp_path):
        csv = tmp_path / "in.csv"
        pd.DataFrame(
            {"name": ["a/b", "https://github.com/c/d"], "stars": [1, 2]}
        ).to_csv(csv, index=False)
        assert list(iter_candidate_names(csv, chunksize=1)) == ["a/b", "c/d"]


class TestWriteFiltered:
    def _input(self, tmp_path):
        csv = tmp_path / "in.csv"
        pd.DataFrame(
            {"name": ["a/b", "c/d", "e/f"], "stars": [10, 20, 30]}
        ).to_csv(csv, index=False)
        return csv

    def test_filtra_y_agrega_columna_binaria(self, tmp_path):
        csv = self._input(tmp_path)
        out = tmp_path / "out.csv"
        enriched = tmp_path / "enriched.csv"

        written = write_filtered(csv, {"a/b", "e/f"}, out, enriched_path=enriched, chunksize=2)

        assert written == 2
        result = pd.read_csv(out)
        assert list(result["name"]) == ["a/b", "e/f"]
        assert list(result["uses_ghaw"]) == [1, 1]
        assert list(result.columns) == ["name", "stars", "uses_ghaw"]

        full = pd.read_csv(enriched)
        assert list(full["name"]) == ["a/b", "c/d", "e/f"]
        assert list(full["uses_ghaw"]) == [1, 0, 1]

    def test_sin_hits_deja_solo_encabezados(self, tmp_path):
        csv = self._input(tmp_path)
        out = tmp_path / "out.csv"
        written = write_filtered(csv, set(), out)
        assert written == 0
        result = pd.read_csv(out)
        assert result.empty
        assert list(result.columns) == ["name", "stars", "uses_ghaw"]
