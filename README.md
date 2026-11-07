# Prueba técnica Data Engineer: de un CSV a un modelo relacional en 3FN

Repositorio: https://github.com/gallegoposada/data-engineering-technical-assessment

## 1. Descripción general

**La prueba.** Nos dan `data_jobs.csv`, un archivo plano con **785.741 ofertas de trabajo** (2023) y 17 columnas.
Hay que construir un pipeline en Python que lo cargue a una base de datos y lo convierta en un
modelo relacional **normalizado (3ra forma normal)**, limpio y con llaves foráneas.

**El problema.** El archivo mezcla en cada fila datos de la oferta, la empresa, la plataforma, el país, el salario
y listas de skills. Así no se puede analizar bien: la misma empresa se repite miles de veces, hay texto dañado,
filas repetidas y columnas que guardan listas y diccionarios como texto.

**El objetivo.** Dejar una base PostgreSQL donde cada dato vive en un solo lugar, las relaciones están
explícitas (por ejemplo, oferta ↔ skills) y la calidad está validada antes de cargar.

## 2. Enfoque de la solución

1. **Ingesta.** Leo el CSV, le doy tipo a cada columna (booleanos, fecha, números, listas y diccionarios) y lo
   guardo tal cual en la tabla `raw_jobs`. Sirve de respaldo fiel del archivo.
2. **Transformación.** Limpio los datos, quito ofertas repetidas y los reparto en **14 tablas** conectadas por llaves.
3. **Validación.** Antes de tocar la base reviso llaves únicas, llaves foráneas, nulos y salarios.
4. **Carga.** Creo las tablas con `sql/schema.sql` y cargo todo en **una sola transacción**: o queda todo, o no queda nada.

## 3. Estructura del proyecto

```
prueba_tecnica/
├── README.md
├── requirements.txt
├── .env.example
├── .gitignore
├── pytest.ini
├── docker-compose.yml
├── .github/workflows/ci.yml
├── sql/
│   └── schema.sql
├── docs/
│   ├── erd.svg
│   └── erd.dbml
├── src/
│   ├── __init__.py
│   ├── limpieza.py
│   ├── ingesta.py
│   ├── transformacion.py
│   ├── validacion.py
│   ├── base_datos.py
│   ├── pipeline.py
│   └── xlsx_a_csv.py
├── tests/
│   ├── test_limpieza.py
│   ├── test_ingesta.py
│   ├── test_transformacion.py
│   └── test_base_datos.py
├── airflow/
│   └── dag_pipeline_empleos.py
└── data/
    └── .gitkeep
```

## 4. Descripción de carpetas

| Carpeta | Para qué existe |
|---|---|
| `sql/` | El esquema de la base de datos (DDL): tabla `raw_jobs` y las 14 tablas normalizadas. |
| `docs/` | El diagrama entidad-relación (ERD) del modelo, como imagen y como código para dbdiagram.io. |
| `src/` | El código del pipeline, un archivo por responsabilidad. |
| `tests/` | Pruebas automáticas con pytest. |
| `airflow/` | El DAG mínimo para orquestar el pipeline con Airflow (bonus). |
| `data/` | Aquí se coloca `data_jobs.csv`|
| `.github/workflows/` | Revisión automática (lint + pruebas) en GitHub Actions. |

## 5. Descripción de archivos

| Archivo | Propósito | Qué hace | Relación con el resto |
|---|---|---|---|
| `sql/schema.sql` | Definir la base de datos | Borra y crea `raw_jobs` + 14 tablas con llaves primarias, foráneas, restricciones e índices | Lo ejecuta `base_datos.crear_esquema` |
| `docs/erd.svg` | Diagrama ER | Imagen del modelo con tablas, columnas, tipos y relaciones | Refleja `sql/schema.sql` |
| `docs/erd.dbml` | Diagrama ER editable | El mismo modelo en DBML: se pega en https://dbdiagram.io/d para verlo y editarlo | Refleja `sql/schema.sql` |
| `src/limpieza.py` | Arreglar problemas de calidad | Funciones pequeñas: reparar texto dañado, quitar el prefijo "via", separar jornadas, leer listas y diccionarios, unificar empresas | La usan `ingesta` y `transformacion` |
| `src/ingesta.py` | Fase 1 | Lee el CSV (`leer_csv`) y lo deja tipado para `raw_jobs` (`preparar_raw`) | Primer paso de `pipeline` |
| `src/transformacion.py` | Fase 2 | `limpiar` limpia y deduplica; `construir_tablas` genera las 14 tablas | Recibe lo de `ingesta`, entrega a `validacion` y `base_datos` |
| `src/validacion.py` | Calidad de datos | Revisa llaves primarias, foráneas, nulos y salarios; falla con un mensaje claro | Se ejecuta antes de cargar |
| `src/base_datos.py` | Hablar con PostgreSQL | Conecta (credenciales del `.env`), crea el esquema y carga DataFrames por bloques | Lo usa `pipeline` |
| `src/pipeline.py` | Orquestar | Ejecuta todos los pasos en orden, con logs y transacción única | Punto de entrada: `python -m src.pipeline` |
| `src/xlsx_a_csv.py` | Utilidad opcional | Convierte el `.xlsx` en `data_jobs.csv` si solo se tiene el Excel | Independiente del pipeline |
| `tests/test_limpieza.py` | Probar la limpieza | 14 pruebas de las funciones de `limpieza.py` | |
| `tests/test_ingesta.py` | Probar la lectura del CSV | 7 pruebas de `leer_csv` y `preparar_raw` | |
| `tests/test_transformacion.py` | Probar el modelo y las validaciones | 16 pruebas con 8 ofertas de ejemplo que reproducen los problemas reales | |
| `tests/test_base_datos.py` | Probar la carga | 10 pruebas de `cargar_tabla` (sin base real) y de que `schema.sql` coincida con el código | |
| `airflow/dag_pipeline_empleos.py` | Orquestación (bonus) | DAG de 3 tareas: verificar CSV → ejecutar pipeline → verificar carga | Llama a `src/pipeline.py` y `src/base_datos.py` |
| `docker-compose.yml` | Base de datos | Levanta PostgreSQL 16 | |
| `.env.example` | Configuración | Plantilla de credenciales y rutas (se copia a `.env`) | |
| `requirements.txt` | Dependencias | Librerías necesarias | |
| `pytest.ini` | Config de pytest | Permite que las pruebas importen `src` | |
| `.github/workflows/ci.yml` | CI (bonus) | Corre `ruff` y `pytest` en cada push | |

## 6. Tecnologías utilizadas

| Tecnología | Para qué | Por qué |
|---|---|---|
| Python 3.11 | Todo el pipeline | Lenguaje pedido |
| pandas | Leer, limpiar y reorganizar los datos | El archivo cabe en memoria y la lógica queda fácil de leer y probar |
| PostgreSQL 16 + Docker Compose | Base de datos | Lo que pide el enunciado; maneja arreglos y JSONB para listas y diccionarios |
| psycopg2 | Conexión y carga | `execute_values` inserta por bloques, mucho más rápido que fila por fila |
| python-dotenv | Leer el `.env` | Evita credenciales en el código |
| openpyxl | Convertir el `.xlsx` | Solo se usa en la utilidad opcional |
| pytest / ruff | Pruebas y estilo | revisión básica en el CI |
| Apache Airflow 2.10 | Orquestar el pipeline |
| GitHub Actions | Corre lint y pruebas en cada push |

## 7. Dependencias

Necesitas **Python 3.11** y, para PostgreSQL, **Docker**.

```bash
python -m venv .venv
source .venv/bin/activate          # Windows (PowerShell): .venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Airflow **no** está en `requirements.txt` .

## 8. Instrucciones de ejecución (desde cero)

1. **Configurar credenciales.** Copia la plantilla y cambia la contraseña:
   `cp .env.example .env` (Windows: `copy .env.example .env`).
2. **Poner los datos.** Copia `data_jobs.csv` en `data/`. Si solo tienes el Excel:
   `python -m src.xlsx_a_csv data/archivo.xlsx data/data_jobs.csv` (tarda un par de minutos).
3. **Levantar PostgreSQL.** `docker compose up -d` (espera a que el estado sea *healthy*: `docker compose ps`).
4. **Ejecutar el pipeline.** `python -m src.pipeline`
5. **Revisar el resultado.**
   `docker compose exec postgres psql -U jobs_user -d jobs_db -c "SELECT COUNT(*) FROM jobs;"`
   (usa el usuario y la base que pusiste en el `.env`). Más revisiones en la sección 16.
6. **Correr las pruebas.** `pytest -v` y, para el estilo, `ruff check .` (guía completa en la sección 16).

Es seguro ejecutar el pipeline varias veces: cada corrida borra y recrea las tablas, así no se duplican datos.
Como referencia, la lectura y transformación de las 785 mil filas tomó alrededor de 1 minuto con unos 2,5 GB de
memoria; la carga depende de tu equipo.

## 9. Flujo de datos

```
data_jobs.csv (785.741 filas, todo texto)
      ↓  ingesta.leer_csv
DataFrame de texto ──→ ingesta.preparar_raw ──→ tabla raw_jobs (tipada, sin limpiar)
      ↓  transformacion.limpiar
DataFrame limpio y sin repetidos (784.955 ofertas)
      ↓  transformacion.construir_tablas
14 DataFrames (uno por tabla)
      ↓  validacion.validar_tablas        ← si falla, se detiene y no se toca la base
      ↓  base_datos (una transacción)
PostgreSQL: raw_jobs + 14 tablas normalizadas
```

## 10. Transformaciones

Antes de diseñar perfilé los datos. Esto fue lo que encontré y lo que hice:

| Problema | Cuánto | Qué hice |
|---|---|---|
| Texto con codificación dañada (`MÃ©xico`, `â€“`, emojis rotos), a veces dañado dos veces | ≈68 mil celdas | `reparar_codificacion`: arregla solo los tramos dañados y deja el resto intacto |
| Prefijo `via` (y `melalui`, que es "via" en indonesio) en la plataforma | 100 % de las filas | Se quita; `LinkedIn` y `via LinkedIn` pasan a ser la misma plataforma |
| Empresas escritas con otra capitalización (`BOEING` / `Boeing`) | ≈8.900 casos | Quedan con el nombre más frecuente |
| Jornada con varios valores (`Full-time, Part-time, and Internship`) | ≈17.600 | Se separa en valores sueltos → tabla `job_schedules` |
| Jornada en indonesio (`Kontraktor`, `Pekerjaan tetap`) | 62 | Se traduce a `Contractor` / `Full-time` |
| Skills repetidas dentro de una lista | ≈63.800 | Se quitan repetidos y se pasa a minúscula |
| Ofertas repetidas (mismo título, empresa, ubicación, plataforma y fecha) | 777 | Se conserva la que tiene más skills |
| Filas sin título, empresa o plataforma | 9 | Se descartan (queda en el log) |
| `salary_rate` = month/week/day, siempre sin monto | 402 | No entran a `job_salaries` (una tasa sin monto no aporta) |
| Búsquedas sin país | 49 filas (8 búsquedas) | `country_id` queda en NULL; no se inventa |
| Ofertas sin skills | ≈117 mil (15 %) | Sin filas en `job_skills` |
| Títulos cortados con `...` | ≈15.800 | No se pueden recuperar; se dejan como vienen |

**Cuadre:** 785.741 filas del CSV = 784.955 ofertas + 777 repetidas + 9 descartadas.

## 11. Decisiones técnicas

### Modelo de datos (ERD)

DDL completo en [`sql/schema.sql`](sql/schema.sql). El diagrama refleja ese archivo exactamente (se comparó tabla por tabla,
columna por columna y relación por relación). La tabla `raw_jobs` no aparece porque es solo la copia fiel del CSV y no tiene relaciones.

![Diagrama entidad-relación](docs/erd.svg)

Para verlo de forma interactiva o editarlo, pega el contenido de [`docs/erd.dbml`](docs/erd.dbml) en https://dbdiagram.io/d.

### Decisiones

| Decisión | Por qué | Qué problema resuelve |
|---|---|---|
| Una tabla por entidad (empresas, plataformas, países, skills...) | Cada dato se guarda una sola vez | Evita repetir la misma empresa miles de veces y errores de captura |
| **El país va en `search_locations`, no en la oferta** | Comprobé que una misma `job_location` aparece con varios países (hay ofertas en Washington, DC con país *Sudan*), pero cada búsqueda tiene un único país | Evita guardar un país que no depende de la oferta (dependencia transitiva) |
| Skills como relación muchos a muchos (`job_skills`) | Una oferta pide varias skills y una skill está en muchas ofertas | Resuelve el requisito de la relación Jobs ↔ Skills |
| Tipos de skill en `skill_type_links` | Hay skills en dos tipos (`mongodb`, `ruby`, `sas`, `firebase`) | Evita forzar un solo tipo por skill. Se pierde qué tipo le asignó el NLP en cada oferta; eso sigue en `raw_jobs` |
| Jornadas separadas en `job_schedules` | Una oferta puede ser `Full-time` y `Contractor` a la vez | Cada columna guarda un único valor (1FN) |
| Salario en tabla aparte (`job_salaries`) | Solo el 4 % de las ofertas tiene monto | Evita una columna casi toda en NULL; un `CHECK` asegura que el monto corresponda a la tasa |
| `raw_jobs` con `TEXT[]` y `JSONB` | Pide cargar listas y diccionarios "con tipos apropiados" | Se pueden consultar con SQL sin volver a interpretar texto |
| Ids numéricos consecutivos creados en pandas | Es lo más simple y repetible | Dos ejecuciones dan exactamente los mismos ids |
| Entre repetidas, quedarse con la de más skills | Es una regla simple y explicable | Evita contar dos veces la misma oferta sin perder la información más completa |
| Borrar y recrear tablas en cada ejecución, en una sola transacción | Simplicidad | Se puede repetir sin duplicar y no queda nada a medias si falla |
| Validaciones propias con pandas (`validacion.py`) | Son pocas y fáciles de leer | Detiene el proceso antes de cargar datos inconsistentes (Pandera o Great Expectations serían alternativas) |
| Python + pandas en vez de dbt | El enunciado permite Python, una sola fuente y un solo lote | Menos piezas que montar y explicar |
| Carga con `execute_values` por bloques de 50.000 filas | Es el método estándar de psycopg2 para cargas grandes | Rápido y sin llenar la memoria |
| DAG de Airflow de 3 tareas, con una sola tarea de carga | La transformación trabaja en memoria; partirla obligaría a guardar archivos intermedios | Orquesta el pipeline sin complicarlo (sección 17) |
| Una prueba compara `schema.sql` con las columnas que genera el código | El `INSERT` falla si una columna se desalinea | Detecta el error en las pruebas y no en plena carga |

## 12. Supuestos

- Una oferta repetida es la que coincide en título, empresa, ubicación, plataforma y fecha (después de limpiar).
- Las empresas se unifican solo por mayúsculas/minúsculas; no hay coincidencia por parecido, para no mezclar empresas distintas.
- Los salarios por hora y por año no se convierten entre sí.
- `job_location` se guarda como viene (`Anywhere`, `Washington, DC`...); no se separa en ciudad, estado y país.
- Cada búsqueda (`search_location`) tiene un solo país. Si algún día no fuera así, el pipeline falla con un error explícito.
- La lista `job_skills` coincide con las skills del diccionario `job_type_skills` (lo verifiqué en los 785 mil registros).
- Si una búsqueda no trae país, se deja el país en NULL aunque la búsqueda sea el nombre de un país (completarlo sería inferir).

## 13. Resultados

Al terminar, PostgreSQL contiene (cifras con el archivo completo):

| Tabla | Filas | Tabla | Filas |
|---|---:|---|---:|
| `raw_jobs` | 785.741 | `jobs` | 784.955 |
| `companies` | 130.346 | `job_salaries` | 32.651 |
| `platforms` | 7.884 | `job_schedules` | 790.874 |
| `locations` | 16.998 | `job_skills` | 3.592.350 |
| `search_locations` | 173 | `skills` | 252 |
| `countries` | 160 | `skill_types` | 10 |
| `title_categories` | 10 | `skill_type_links` | 256 |
| `schedule_types` | 7 | | |

Consultas de ejemplo:

```sql
-- Skills más pedidas para Data Engineer
SELECT s.skill_name, COUNT(*) AS ofertas
FROM jobs j
JOIN title_categories t ON t.title_category_id = j.title_category_id
JOIN job_skills js ON js.job_id = j.job_id
JOIN skills s ON s.skill_id = js.skill_id
WHERE t.title_category_name = 'Data Engineer'
GROUP BY s.skill_name ORDER BY ofertas DESC LIMIT 5;

-- Salario anual promedio por categoría de cargo
SELECT t.title_category_name, COUNT(*) AS ofertas, ROUND(AVG(sa.salary_year_avg)) AS promedio
FROM job_salaries sa
JOIN jobs j ON j.job_id = sa.job_id
JOIN title_categories t ON t.title_category_id = j.title_category_id
WHERE sa.salary_rate = 'year'
GROUP BY t.title_category_name ORDER BY promedio DESC;
```

## 14 Guía de pruebas

### 14.1 Qué se prueba

| Archivo | Qué comprueba | Pruebas |
|---|---|---:|
| `tests/test_limpieza.py` | Cada función de limpieza por separado: texto dañado, espacios, prefijo "via", booleanos, jornadas, skills, empresas | 14 |
| `tests/test_ingesta.py` | Lectura del CSV (todo como texto, textos "NA"/"None" que no se pierden, archivo inexistente, columnas faltantes) y tipado de `raw_jobs` | 7 |
| `tests/test_transformacion.py` | El modelo 3FN completo con 8 ofertas de ejemplo, y las reglas de `validacion.py` | 16 |
| `tests/test_base_datos.py` | La carga: nulos, tipos que acepta psycopg2, fechas, JSON, bloques, y que `schema.sql` coincida con el código | 10 |
| **Total** | | **47** |

Las pruebas **no necesitan base de datos ni internet**: la carga se prueba con una conexión falsa que guarda lo que recibiría PostgreSQL.

### 14.2 Cómo correrlas

```bash
pytest -v                                  # todas, con el detalle de cada una (esperado: 47 passed)
pytest -q                                  # todas, en resumen
pytest tests/test_limpieza.py -v           # solo un archivo
pytest -k "jornadas" -v                    # solo las pruebas cuyo nombre contenga "jornadas"
pytest -x                                  # se detiene en la primera que falle
ruff check .                               # revisión de estilo del código
```

Si todo está bien, `pytest` termina con una línea como `47 passed`. Si algo falla, muestra el nombre de la prueba, la línea y la diferencia entre lo esperado y lo obtenido.

### 14.3 Los datos de ejemplo

`tests/test_transformacion.py` crea 8 ofertas pequeñas; cada una reproduce un problema real del CSV:

| Fila | Qué reproduce |
|---|---|
| 0 | Versión **pobre** (1 skill) de una oferta repetida, con texto dañado dos veces y plataforma `via BeBee MÃ©xico` |
| 1 | Oferta remota, salario por hora y la empresa escrita con otra capitalización |
| 2 | Sin skills, sin ubicación y sin jornada |
| 3 | La **misma oferta que la fila 0, pero más completa** (debe ser la que se conserve) |
| 4 | Otra búsqueda cuyo país es *Georgia* |
| 5 | Booleanos escritos en minúscula |
| 6 | Jornada con comas, tasa de salario `month` sin monto y búsqueda sin país |
| 7 | Jornada en indonesio |

### 14.4 Pruebas de calidad de datos

`src/validacion.py` es a la vez una **barrera en el pipeline** (si falla, no se carga nada) y código **probado**:

| Regla | Prueba que la comprueba |
|---|---|
| Llaves primarias sin repetir | `test_validacion_detecta_llave_primaria_repetida` |
| Llaves foráneas que apuntan a algo que existe | `test_validacion_detecta_llave_foranea_huerfana` |
| Sin nulos en los campos obligatorios de `jobs` | `test_validacion_detecta_nulos_en_campos_obligatorios` |
| El modelo correcto sí pasa | `test_validacion_acepta_el_modelo_correcto` |

### 14.5 Verificación manual después de cargar

Con el pipeline ya ejecutado sobre el archivo completo, estas consultas (en `psql`) deben dar estos resultados:

| Qué se comprueba | Consulta | Resultado esperado |
|---|---|---|
| Cuadre de filas | `SELECT (SELECT COUNT(*) FROM raw_jobs), (SELECT COUNT(*) FROM jobs);` | 785741 y 784955 (la diferencia son 777 repetidas y 9 descartadas) |
| Ninguna oferta repetida | `SELECT job_title, company_id, location_id, platform_id, posted_at, COUNT(*) FROM jobs GROUP BY 1,2,3,4,5 HAVING COUNT(*) > 1;` | 0 filas |
| Ofertas sin skills | `SELECT COUNT(*) FROM jobs j WHERE NOT EXISTS (SELECT 1 FROM job_skills s WHERE s.job_id = j.job_id);` | 116854 |
| Texto reparado | `SELECT platform_name FROM platforms WHERE platform_name IN ('BeBee México', 'BeBee Perú');` | 2 filas |
| Empresas unificadas | `SELECT company_name FROM companies WHERE LOWER(company_name) = 'boeing';` | 1 fila |
| Salarios por tasa | `SELECT salary_rate, COUNT(*) FROM job_salaries GROUP BY salary_rate;` | `hour` 10653 y `year` 21998 |
| Búsquedas sin país | `SELECT COUNT(*) FROM search_locations WHERE country_id IS NULL;` | 8 |
| Listas y diccionarios con su tipo | `SELECT pg_typeof(job_skills), pg_typeof(job_type_skills) FROM raw_jobs LIMIT 1;` | `text[]` y `jsonb` |

### 14.6 Integración continua

En cada `push` a GitHub, `.github/workflows/ci.yml` instala las dependencias y corre `ruff check .` y `pytest -v`.
El resultado se ve en la pestaña **Actions** del repositorio.

### 14.7 Cómo agregar una prueba nueva

1. Abre el archivo que corresponda (por ejemplo `tests/test_limpieza.py`).
2. Escribe una función cuyo nombre empiece por `test_`, con un `assert` por cada cosa que debe cumplirse:

```python
def test_quitar_prefijo_via_con_mayusculas():
    assert quitar_prefijo_via("VIA LinkedIn") == "LinkedIn"
```

3. Córrela sola con `pytest -k "mayusculas" -v` y luego corre todas con `pytest`.

## 15. Orquestación con Airflow (bonus)

El DAG está en [`airflow/dag_pipeline_empleos.py`](airflow/dag_pipeline_empleos.py) y tiene 3 tareas en fila:

```
verificar_csv  →  ejecutar_pipeline  →  verificar_carga
```

| Tarea | Qué hace | Cuándo falla |
|---|---|---|
| `verificar_csv` | Comprueba que exista el archivo de `CSV_PATH` | Si el CSV no está |
| `ejecutar_pipeline` | Corre el pipeline completo (`src/pipeline.py`) | Si falla la lectura, la validación o la carga |
| `verificar_carga` | Consulta PostgreSQL: debe haber ofertas y no más que filas en `raw_jobs` | Si la carga quedó vacía o incoherente |

Decisiones: el DAG se lanza **a mano** (`schedule=None`, es una carga única) y usa **una sola tarea de carga** porque la transformación
trabaja en memoria; partirla en varias tareas obligaría a guardar archivos intermedios que aquí no hacen falta.

Cómo probarlo (Airflow corre en Linux o macOS; en Windows se usa WSL2). Instálalo en el mismo entorno donde instalaste `requirements.txt`:

```bash
pip install "apache-airflow==2.10.5" --constraint "https://raw.githubusercontent.com/apache/airflow/constraints-2.10.5/constraints-3.11.txt"
export AIRFLOW__CORE__DAGS_FOLDER="$(pwd)/airflow"     # le dice a Airflow dónde está el DAG
export AIRFLOW__CORE__LOAD_EXAMPLES=False              # oculta los DAGs de ejemplo
airflow standalone                                     # arranca todo; muestra el usuario y la clave en consola
```

Abre http://localhost:8080, entra con esa clave y lanza el DAG `pipeline_ofertas_laborales` con el botón *Trigger*.
PostgreSQL debe estar arriba (`docker compose up -d`) y el `.env` configurado, igual que al correr el pipeline a mano.

## 16. Repositorio y control de versiones

Repositorio: https://github.com/gallegoposada/data-engineering-technical-assessment

El historial sigue la convención **Conventional Commits** (`tipo(ámbito): descripción`) y tiene un commit por componente,
en el orden en que se construye la solución:

| Commit | Qué incluye |
|---|---|
| `chore: estructura inicial, dependencias y configuración` | `.gitignore`, `requirements.txt`, `.env.example`, `pytest.ini` |
| `feat(sql): esquema PostgreSQL con raw_jobs y modelo 3FN` | `sql/schema.sql` |
| `feat(docker): PostgreSQL 16 con Docker Compose` | `docker-compose.yml` |
| `feat(limpieza): funciones de limpieza de datos` | `src/limpieza.py` y sus pruebas |
| `feat(ingesta): lectura del CSV y tipado de raw_jobs` | `src/ingesta.py` y sus pruebas |
| `feat(transformacion): modelo 3FN y validaciones de calidad` | `src/transformacion.py`, `src/validacion.py` y sus pruebas |
| `feat(carga): conexión a PostgreSQL y carga por bloques` | `src/base_datos.py` y sus pruebas |
| `feat(pipeline): orquestar lectura, transformación, validación y carga` | `src/pipeline.py` |
| `feat(utilidad): convertir el xlsx a csv` | `src/xlsx_a_csv.py` |
| `feat(airflow): DAG mínimo para orquestar el pipeline` | `airflow/dag_pipeline_empleos.py` |
| `ci: lint y pruebas con GitHub Actions` | `.github/workflows/ci.yml` |
| `docs: diagrama entidad-relación (SVG y DBML)` | `docs/erd.svg`, `docs/erd.dbml` |
| `docs: README con decisiones, guía de pruebas y diseño OLAP` | `README.md` |

Prefijos usados: `feat` (algo nuevo), `docs` (documentación), `ci` (integración continua), `chore` (mantenimiento).

## 17. Bonus: diseño conceptual OLAP (esquema en estrella)

*Solo diseño, no se implementó.*

- **Tabla de hechos `fact_job_postings`.** Una fila por **oferta de trabajo** (esa es su granularidad).
- **Medidas:** `cantidad_ofertas` (siempre 1, se puede sumar), `salary_year_avg` y `salary_hour_avg` (no se suman: se
  promedian o se usan mínimos, máximos y percentiles; pueden ser nulos) y `cantidad_skills` (se puede sumar).
- **Dimensiones:** `dim_fecha` (día, mes, trimestre), `dim_empresa`, `dim_plataforma`, `dim_cargo` (categoría del título),
  `dim_ubicacion` y `dim_busqueda` (con su país).
- **Skills → tabla puente (bridge).** Una oferta tiene varias skills; si se une el hecho directo con la skill, cada oferta se
  repite y las medidas se inflan. Se crea `bridge_oferta_skill(oferta, skill, peso)` con `peso = 1 / cantidad de skills de
  la oferta`: sumando con ese peso los totales siguen cuadrando; para "ofertas que mencionan Python" se cuenta sin peso.
- **Banderas booleanas → dimensión basura (junk).** `remoto`, `sin_título_requerido` y `seguro_médico` son 3 booleanos,
  o sea solo **8 combinaciones**. En vez de tres dimensiones minúsculas, una `dim_banderas` de 8 filas, y el hecho guarda una
  sola llave hacia ella.
- La jornada (varios valores por oferta) se trataría igual que las skills, con otra tabla puente.
