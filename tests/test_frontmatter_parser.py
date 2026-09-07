"""Pruebas de separación y aplanamiento del frontmatter YAML."""

from miner.frontmatter_parser import flatten_frontmatter, split_frontmatter

SAMPLE = """---
on: push
timeout_minutes: 15
engine: claude
permissions:
  contents: read
  issues: write
tools:
  - github
  - playwright
enabled: true
---
# Daily report

Genera un reporte diario.
"""


class TestSplitFrontmatter:
    def test_separa_metadata_y_body(self):
        parsed = split_frontmatter(SAMPLE)
        assert parsed.metadata["on"] == "push"
        assert parsed.metadata["timeout_minutes"] == 15
        assert "# Daily report" in parsed.body
        assert "---" not in parsed.body

    def test_sin_frontmatter(self):
        parsed = split_frontmatter("solo body, sin frontmatter\n")
        assert parsed.metadata == {}
        assert "solo body" in parsed.body


class TestFlattenFrontmatter:
    def test_claves_planas(self):
        entries = {e.key_path: e for e in flatten_frontmatter({"on": "push", "timeout_minutes": 15})}
        assert entries["on"].value == "push"
        assert entries["on"].value_type == "str"
        assert entries["timeout_minutes"].value == "15"
        assert entries["timeout_minutes"].value_type == "int"

    def test_dict_anidado_se_aplana_con_punto(self):
        entries = {e.key_path: e for e in flatten_frontmatter({"permissions": {"contents": "read"}})}
        assert entries["permissions.contents"].value == "read"

    def test_lista_se_serializa_como_json(self):
        entries = {e.key_path: e for e in flatten_frontmatter({"tools": ["github", "playwright"]})}
        assert entries["tools"].value_type == "json"
        assert entries["tools"].value == '["github", "playwright"]'

    def test_bool_y_null(self):
        entries = {e.key_path: e for e in flatten_frontmatter({"enabled": True, "note": None})}
        assert entries["enabled"].value == "true"
        assert entries["enabled"].value_type == "bool"
        assert entries["note"].value == "None"
        assert entries["note"].value_type == "null"

    def test_frontmatter_vacio(self):
        assert flatten_frontmatter({}) == []
