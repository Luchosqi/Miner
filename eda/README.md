# EDA — GitHub Agentic Workflows (GH-AW)

Análisis exploratorio de datos (EDA) sobre el dataset relacional generado con
[Miner](../README.md) (`miner dataset`) a partir de archivos `.md` de
[GitHub Agentic Workflows](https://github.com/githubnext/gh-aw).

**Dataset propio (Hugging Face):**
<https://huggingface.co/datasets/luchosqi/gh-aw-workflows>

## Contenido

| Archivo | Descripción |
|---|---|
| `01_descripcion_y_calidad.ipynb` | Carga el dataset desde Hugging Face, describe las tres tablas y sus relaciones, revisa su calidad y guarda las tablas preparadas en `data/processed/`. |
| `02_exploracion_y_hallazgos.ipynb` | Carga `data/processed/`, explora la distribución de archivos por repo, el frontmatter, el body, cruces entre variables, y presenta los hallazgos. |
| `data/processed/` | Tablas Parquet generadas por el notebook 1 (`repositories.parquet`, `workflow_files.parquet`, `frontmatter_entries.parquet`). Se regeneran al ejecutar el notebook 1; no es necesario descargarlas a mano. |

## 1. Obtener los datos

No hace falta descargar nada manualmente: el notebook 1 lee las tres tablas Parquet directamente
desde Hugging Face con `pandas.read_parquet("hf://datasets/luchosqi/gh-aw-workflows/...")` y
guarda copias preparadas en `eda/data/processed/`. Basta con tener conexión a internet la primera
vez que se ejecuta.

## 2. Instalar las dependencias

Desde la raíz del repositorio (`Miner/`), con el mismo entorno virtual que usa el resto del
proyecto:

```bash
source .venv/bin/activate      # Windows: .venv\Scripts\activate
python -m pip install -e ".[eda]"
```

Esto instala JupyterLab, ipykernel, pandas, PyArrow, Matplotlib, Seaborn y `huggingface_hub`
(para leer `hf://...`), además de las dependencias ya existentes de Miner. Las versiones quedan
registradas en `pyproject.toml`, bajo `[project.optional-dependencies] eda`.

## 3. Registrar y seleccionar el kernel

Registra el entorno virtual como kernel de Jupyter (una sola vez):

```bash
python -m ipykernel install --user --name=miner-eda --display-name "Miner (.venv)"
```

Al abrir cualquiera de los dos notebooks en JupyterLab, selecciona el kernel **"Miner (.venv)"**
desde el menú *Kernel → Change Kernel*.

## 4. Iniciar JupyterLab

```bash
cd eda
jupyter lab
```

## 5. Orden de ejecución

1. **`01_descripcion_y_calidad.ipynb`** primero — genera las tablas en `data/processed/` que
   consume el segundo notebook.
2. **`02_exploracion_y_hallazgos.ipynb`** después — lee únicamente `data/processed/`, no depende
   de variables en memoria del primer notebook.

Ambos notebooks están pensados para ejecutarse de principio a fin con *Run → Run All Cells* (o
`jupyter nbconvert --to notebook --execute --inplace <archivo>.ipynb`), sin errores.
