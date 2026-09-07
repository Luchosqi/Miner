# Uso de la CLI

Miner ahora expone dos comandos: `mine` (Tarea 2, sin cambios de fondo) y
`dataset` (nuevo, Tarea 3).

## `miner mine` — detectar repositorios que usan GH-AW

Sin cambios respecto a la Tarea 2, salvo que ahora es un subcomando:

```bash
miner mine repositorios.csv --output repositorios_ghaw.csv
```

Ver `miner mine --help` para todas las opciones (`--enriched`, `--batch-size`,
`--workers`, `--checkpoint`, etc.).

## `miner dataset` — construir el dataset relacional Parquet

Toma el CSV de repositorios que usan GH-AW (la salida de `miner mine`,
por ejemplo `repositorios_ghaw.csv`), vuelve a listar
`.github/workflows/` de cada uno, descarga el contenido de cada archivo `.md`
válido (el que tiene su `.lock.yml` correspondiente), separa frontmatter YAML
y body Markdown, y escribe las tres tablas del esquema
(ver [er-diagram.md](er-diagram.md) y [data-dictionary.md](data-dictionary.md))
como archivos `.parquet`.

### Entrada requerida

- Un CSV con una columna que identifique el repositorio (`name`, `full_name`,
  `nameWithOwner`, `repository`, `repo`, o una columna de URL) — el mismo
  formato que usa `miner mine`. Normalmente es el `repositorios_ghaw.csv`
  generado en el paso anterior.
- Un token de GitHub en `GITHUB_TOKEN` (archivo `.env`), igual que para
  `miner mine`.

### Indicar la salida

```bash
miner dataset repositorios_ghaw.csv --output-dir dataset
```

Esto crea el directorio `dataset/` (si no existe) con:

```
dataset/
  repositories.parquet
  workflow_files.parquet
  frontmatter_entries.parquet
```

### Opciones

| Opción | Descripción | Por defecto |
|---|---|---|
| `--output-dir`, `-o` | Directorio donde se escriben las tablas `.parquet` | `dataset` |
| `--batch-size`, `-b` | Elementos por consulta GraphQL (repos al listar, archivos al descargar) | `50` |
| `--request-delay` | Pausa (s) tras cada consulta, para no gatillar el rate limit secundario | `0.3` |

### Ejemplo completo de ejecución

```bash
# 1. Detectar repos que usan GH-AW (Tarea 2)
miner mine repositorios.csv --output repositorios_ghaw.csv

# 2. Construir el dataset relacional a partir de esos repos (Tarea 3)
miner dataset repositorios_ghaw.csv --output-dir dataset -b 20 --request-delay 0.2
```

Salida esperada en consola:

```
Dataset generado. 374 repos · 421 archivos .md encontrados · 421 descargados.
  repositories: dataset/repositories.parquet
  workflow_files: dataset/workflow_files.parquet
  frontmatter_entries: dataset/frontmatter_entries.parquet
```

### Explorar el resultado

```python
import pandas as pd

repos = pd.read_parquet("dataset/repositories.parquet")
files = pd.read_parquet("dataset/workflow_files.parquet")
entries = pd.read_parquet("dataset/frontmatter_entries.parquet")

# Archivos + su repo de origen
files.merge(repos, on="repo_id")[["full_name", "filename", "body_markdown"]]

# Frontmatter de un archivo puntual
entries[entries["file_id"] == 0]
```
