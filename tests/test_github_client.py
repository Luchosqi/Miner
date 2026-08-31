"""Pruebas de las funciones puras del cliente GraphQL."""

from miner.github_client import build_query, parse_batch_response
from miner.pipeline import result_from_files


class TestBuildQuery:
    def test_incluye_un_alias_por_repo(self):
        q = build_query(["octocat/Hello-World", "a/b"])
        assert "r0: repository(owner: \"octocat\", name: \"Hello-World\")" in q
        assert "r1: repository(owner: \"a\", name: \"b\")" in q
        assert "rateLimit" in q

    def test_escapa_comillas(self):
        q = build_query(['ev"il/repo'])
        assert '\\"' in q


class TestParseBatchResponse:
    def test_repo_con_archivos(self):
        data = {"r0": {"object": {"entries": [{"name": "ci.yml"}, {"name": "x.md"}]}}}
        assert parse_batch_response(["a/b"], data) == {"a/b": ["ci.yml", "x.md"]}

    def test_repo_sin_directorio_workflows(self):
        data = {"r0": {"object": None}}
        assert parse_batch_response(["a/b"], data) == {"a/b": []}

    def test_repo_inaccesible_es_none(self):
        data = {"r0": None}
        assert parse_batch_response(["a/b"], data) == {"a/b": None}

    def test_data_vacia(self):
        assert parse_batch_response(["a/b"], None) == {"a/b": None}

    def test_varios_repos_mezclados(self):
        data = {
            "r0": {"object": {"entries": [{"name": "r.md"}, {"name": "r.lock.yml"}]}},
            "r1": {"object": None},
            "r2": None,
        }
        out = parse_batch_response(["x/0", "x/1", "x/2"], data)
        assert out == {"x/0": ["r.md", "r.lock.yml"], "x/1": [], "x/2": None}


class TestResultFromFiles:
    def test_par_valido(self):
        res = result_from_files("a/b", ["r.md", "r.lock.yml"])
        assert res.uses_ghaw is True
        assert res.ghaw_files == ["r.md"]
        assert res.error is None

    def test_sin_par(self):
        assert result_from_files("a/b", ["r.md"]).uses_ghaw is False

    def test_repo_inaccesible(self):
        res = result_from_files("a/b", None)
        assert res.uses_ghaw is False
        assert res.error == "repo no accesible"
