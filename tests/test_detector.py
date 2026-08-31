"""Pruebas de la lógica que identifica GitHub Agentic Workflows."""

from miner.detector import find_ghaw_pairs, uses_ghaw


class TestUsesGhaw:
    def test_par_completo_usa_ghaw(self):
        assert uses_ghaw(["report.md", "report.lock.yml"]) is True

    def test_solo_md_no_usa_ghaw(self):
        assert uses_ghaw(["report.md"]) is False

    def test_solo_lock_no_usa_ghaw(self):
        assert uses_ghaw(["report.lock.yml"]) is False

    def test_bases_distintas_no_usa_ghaw(self):
        assert uses_ghaw(["report.md", "other.lock.yml"]) is False

    def test_directorio_vacio_no_usa_ghaw(self):
        assert uses_ghaw([]) is False

    def test_workflows_normales_no_cuentan(self):
        assert uses_ghaw(["ci.yml", "release.yml", "codeql.yml"]) is False

    def test_un_par_valido_entre_varios_archivos(self):
        files = [
            "ci.yml",
            "release.yml",
            "daily-report.md",
            "daily-report.lock.yml",
            "CONTRIBUTING.md",
        ]
        assert uses_ghaw(files) is True

    def test_lock_yaml_sin_yml_no_cuenta(self):
        assert uses_ghaw(["x.md", "x.lock.yaml"]) is False

    def test_base_con_puntos_y_guiones(self):
        assert uses_ghaw(["daily-report.v2.md", "daily-report.v2.lock.yml"]) is True


class TestFindGhawPairs:
    def test_devuelve_todas_las_bases_emparejadas_ordenadas(self):
        files = ["b.md", "b.lock.yml", "a.md", "a.lock.yml", "c.md"]
        assert find_ghaw_pairs(files) == ["a", "b"]

    def test_sin_pares_lista_vacia(self):
        assert find_ghaw_pairs(["a.md", "b.lock.yml"]) == []
