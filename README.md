# Miner

Miner identifica, a partir de un archivo CSV de repositorios de GitHub, cuáles
utilizan **GitHub Agentic Workflows (GH-AW)** y genera un nuevo CSV que contiene
únicamente esos repositorios. Además, extrae el contenido de sus archivos
`.md` de GH-AW (frontmatter YAML + body Markdown) y lo transforma en un
dataset relacional en formato **Apache Parquet**.

Documentación de la Tarea 3 (dataset relacional): [docs/](docs/)
- [Diagrama entidad-relación](docs/er-diagram.md)
- [Diccionario de datos](docs/data-dictionary.md)
- [Uso de la CLI](docs/cli-usage.md)

## ¿Qué problema resuelve?

GH-AW es una tecnología reciente de GitHub. Dado un listado amplio de
repositorios (por ejemplo, el exportado desde [SEART GitHub Search](https://seart-ghs.si.usi.ch/)),
revisar uno por uno si adoptaron GH-AW es inviable a mano. Miner automatiza esa
revisión.

### Criterio de identificación

Un repositorio usa GH-AW cuando, dentro de `.github/workflows/`, existe al menos
un **par de archivos con el mismo nombre base**:

| Archivo | Descripción |
|---|---|
| `<base>.md` | definición del workflow agéntico |
| `<base>.lock.yml` | workflow compilado por GH-AW |

Ejemplo: `daily-report.md` + `daily-report.lock.yml`.

### ¿Por qué GraphQL y no la API REST?

El listado de candidatos puede tener cientos de miles de repositorios.
Consultarlos uno por uno con la API REST (una petición por repo) choca con el
límite de 5.000 peticiones/hora. Miner usa la **API GraphQL de GitHub** a través
de **HTTPX**: una sola consulta pide el contenido de `.github/workflows/` de
hasta 100 repositorios (mediante *alias*) y ese lote completo cuesta **1 punto**
del presupuesto horario. Así el dataset completo se procesa en un par de horas.

## Requisitos

- Python 3.10 o superior
- Un token personal de GitHub (para consultar la API sin toparse con el límite
  de peticiones anónimas)

## Preparar el entorno

```bash
git clone https://github.com/<tu-usuario>/Miner.git
cd Miner

python3 -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
```

## Instalar dependencias

```bash
pip install -e ".[dev]"
```

Esto instala Miner y sus dependencias: Typer, Pydantic, pandas, HTTPX,
python-dotenv, Rich y pytest.

## Configurar el token de GitHub

1. Crea un token en <https://github.com/settings/personal-access-tokens>.
   Para repositorios públicos basta con permisos de **solo lectura**.
2. Copia el archivo de ejemplo y pega tu token:

   ```bash
   cp .env.example .env
   ```

3. Edita `.env`:

   ```
   GITHUB_TOKEN=tu_token_de_github
   ```

El archivo `.env` está en `.gitignore`: **nunca se sube al repositorio**.

## Ejecutar Miner

### 1. Detectar repositorios que usan GH-AW

```bash
miner mine repositorios.csv --output repositorios_ghaw.csv
```

Opciones:

| Opción | Descripción | Por defecto |
|---|---|---|
| `--output`, `-o` | CSV de salida (solo repos que usan GH-AW) | `repositorios_ghaw.csv` |
| `--enriched` | CSV adicional con **todas** las filas y la columna binaria `uses_ghaw` | — |
| `--batch-size`, `-b` | Repositorios por consulta GraphQL (1-100) | `50` |
| `--workers`, `-w` | Consultas GraphQL concurrentes | `4` |
| `--checkpoint` | Archivo de avance; volver a ejecutar retoma donde quedó | `.miner_checkpoint.jsonl` |
| `--no-checkpoint` | Ignora el checkpoint y empieza de cero | — |

El proceso guarda cada resultado en el archivo de checkpoint. Si se interrumpe
(corte de red, Ctrl-C), basta con volver a ejecutar el mismo comando: retoma
donde quedó.

Ejemplo con CSV enriquecido:

```bash
miner mine repositorios.csv -o repositorios_ghaw.csv --enriched repositorios_enriquecido.csv
```

### 2. Construir el dataset relacional (Parquet)

A partir del CSV de repositorios que usan GH-AW, `miner dataset` descarga cada
archivo `.md` de `.github/workflows/`, separa su frontmatter YAML del body
Markdown y genera tres tablas `.parquet` (`repositories`, `workflow_files`,
`frontmatter_entries`):

```bash
miner dataset repositorios_ghaw.csv --output-dir dataset
```

Ver [docs/cli-usage.md](docs/cli-usage.md) para todas las opciones y un
ejemplo completo, y [docs/er-diagram.md](docs/er-diagram.md) /
[docs/data-dictionary.md](docs/data-dictionary.md) para el esquema del
dataset.

### Entrada

Un CSV con una fila por repositorio. Miner busca automáticamente el identificador
`owner/repo` en alguna de estas columnas: `name`, `full_name`, `nameWithOwner`,
`repository`, `repo`, o lo deriva de una columna de URL (`url`, `html_url`, ...).
El CSV exportado por SEART GitHub Search funciona directamente.

### Salida

Un CSV con las **mismas columnas del archivo de entrada** más una columna
binaria `uses_ghaw` (siempre `1` en el archivo de salida, ya que solo contiene
los repositorios que usan GH-AW). El CSV opcional `--enriched` conserva todas
las filas con `uses_ghaw` en `0`/`1`.

## Pruebas

```bash
pytest
```

Las pruebas cubren, como mínimo, la lógica que decide si un conjunto de archivos
corresponde a un GitHub Agentic Workflow:

- `report.md` + `report.lock.yml` → usa GH-AW
- `report.md` solo → no usa GH-AW
- `report.lock.yml` solo → no usa GH-AW
- `report.md` + `other.lock.yml` → no usa GH-AW

## Estructura del proyecto

```
src/miner/
  detector.py           # lógica pura: detección de pares .md / .lock.yml
  models.py             # modelos Pydantic (validación de datos)
  csv_io.py             # lectura/escritura de CSV con pandas
  github_client.py      # acceso a la API de GitHub vía HTTPX + GraphQL (batching)
  pipeline.py           # orquestación de 'miner mine' (concurrente + checkpoint)
  frontmatter_parser.py # separa y aplana el frontmatter YAML de los .md de GH-AW
  workflows_dataset.py  # construye las tablas del esquema entidad-relación (pandas)
  dataset_pipeline.py   # orquestación de 'miner dataset' (descarga + tablas + Parquet)
  cli.py                # interfaz de línea de comandos (Typer): 'mine' y 'dataset'
tests/
  test_detector.py
  test_csv_io.py
  test_github_client.py
  test_frontmatter_parser.py
  test_workflows_dataset.py
docs/
  er-diagram.md       # diagrama entidad-relación del dataset
  data-dictionary.md  # diccionario de datos (tablas, columnas, PK/FK)
  cli-usage.md        # instrucciones de uso de 'miner dataset'
```
