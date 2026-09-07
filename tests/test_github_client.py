"""Pruebas de las funciones puras del cliente GraphQL."""

from miner.github_client import (
    build_content_query,
    build_query,
    parse_batch_response,
    parse_content_response,
)
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


class TestBuildContentQuery:
    def test_incluye_expresion_del_blob(self):
        q = build_content_query([("octocat/Hello-World", ".github/workflows/report.md")])
        assert 'r0: repository(owner: "octocat", name: "Hello-World")' in q
        assert 'expression: "HEAD:.github/workflows/report.md"' in q
        assert "... on Blob { text }" in q


class TestParseContentResponse:
    def test_archivo_con_texto(self):
        data = {"r0": {"object": {"text": "---\non: push\n---\nhola"}}}
        refs = [("a/b", ".github/workflows/x.md")]
        assert parse_content_response(refs, data) == {refs[0]: "---\non: push\n---\nhola"}

    def test_repo_inaccesible_es_none(self):
        refs = [("a/b", ".github/workflows/x.md")]
        assert parse_content_response(refs, {"r0": None}) == {refs[0]: None}

    def test_archivo_no_encontrado_es_none(self):
        refs = [("a/b", ".github/workflows/x.md")]
        assert parse_content_response(refs, {"r0": {"object": None}}) == {refs[0]: None}


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
