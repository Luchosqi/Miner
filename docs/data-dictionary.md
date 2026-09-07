# Diccionario de datos

Tres tablas Parquet, una por entidad del esquema (ver [er-diagram.md](er-diagram.md)).

## `repositories.parquet`

Un repositorio de GitHub que usa GH-AW.

| Columna | Tipo | Clave | Descripción |
|---|---|---|---|
| `repo_id` | int64 | PK | Identificador interno, autoincremental por orden de aparición. |
| `full_name` | string | — | Identificador `owner/repo` en GitHub. |
| `owner` | string | — | Cuenta u organización dueña del repositorio. |
| `name` | string | — | Nombre del repositorio (sin el owner). |

## `workflow_files.parquet`

Un archivo `.md` de GitHub Agentic Workflows dentro de `.github/workflows/` de
un repositorio (solo los que tienen su `.lock.yml` correspondiente, es decir,
los detectados como GH-AW válidos en la Tarea 2).

| Columna | Tipo | Clave | Descripción |
|---|---|---|---|
| `file_id` | int64 | PK | Identificador interno del archivo. |
| `repo_id` | int64 | FK → `repositories.repo_id` | Repositorio al que pertenece el archivo. |
| `path` | string | — | Ruta completa dentro del repo, p. ej. `.github/workflows/daily-report.md`. |
| `filename` | string | — | Nombre del archivo, p. ej. `daily-report.md`. |
| `body_markdown` | string | — | Contenido en Markdown del archivo, **sin** el frontmatter YAML. |

## `frontmatter_entries.parquet`

El frontmatter YAML de cada archivo, aplanado a pares clave/valor (modelo
entidad-atributo-valor). Se usa este modelo porque el frontmatter de GH-AW
tiene esquema libre: cada workflow define sus propias claves y niveles de
anidamiento (`on`, `permissions`, `engine`, `tools`, `timeout_minutes`, etc.),
por lo que no existe un conjunto fijo de columnas que sirva para todos los
archivos.

| Columna | Tipo | Clave | Descripción |
|---|---|---|---|
| `entry_id` | int64 | PK | Identificador interno de la entrada. |
| `file_id` | int64 | FK → `workflow_files.file_id` | Archivo del que proviene la entrada. |
| `key_path` | string | — | Ruta de la clave YAML, con notación de punto para anidamiento (p. ej. `permissions.contents`). |
| `value` | string | — | Valor serializado a texto. Objetos y listas se serializan como JSON. |
| `value_type` | string | — | Tipo original del valor: `str`, `int`, `float`, `bool`, `null` o `json` (dict/list). |

### Reconstruir el frontmatter de un archivo

Para volver a armar el frontmatter completo de un `file_id`, se filtran las
filas de `frontmatter_entries` con ese `file_id` y se reconstruye el árbol a
partir de `key_path` (separando por `.`) y `value` (parseando según
`value_type`: `int`/`float`/`bool` con cast directo, `json` con
`json.loads`, `null` como `None`, `str` tal cual).

## Cardinalidades

| Relación | Cardinalidad |
|---|---|
| `repositories` → `workflow_files` | 1 : N (un repo puede tener 0 o más archivos GH-AW) |
| `workflow_files` → `frontmatter_entries` | 1 : N (un archivo puede tener 0 o más entradas de frontmatter) |
