"""Fase 1 – Ingesta: leer el CSV y dejarlo listo para la tabla raw_jobs.

Qué hace : lee data_jobs.csv y le pone el tipo correcto a cada columna, SIN limpiar el contenido
           (la tabla raw_jobs es la copia fiel del archivo).
Qué recibe: la ruta del CSV.
Qué devuelve: leer_csv() -> DataFrame con todo como texto; preparar_raw() -> DataFrame tipado.
Dónde se usa: src/pipeline.py.
"""
import logging
import os

import pandas as pd

from src.limpieza import a_booleano, leer_diccionario_crudo, leer_lista_cruda

log = logging.getLogger(__name__)

COLUMNAS_ESPERADAS = [
    "job_title_short", "job_title", "job_location", "job_via", "job_schedule_type",
    "job_work_from_home", "search_location", "job_posted_date", "job_no_degree_mention",
    "job_health_insurance", "job_country", "salary_rate", "salary_year_avg",
    "salary_hour_avg", "company_name", "job_skills", "job_type_skills",
]
COLUMNAS_BOOLEANAS = ["job_work_from_home", "job_no_degree_mention", "job_health_insurance"]
COLUMNAS_SALARIO = ["salary_year_avg", "salary_hour_avg"]


def leer_csv(ruta):
    """Lee el CSV completo como texto y revisa que traiga las 17 columnas esperadas."""
    if not os.path.exists(ruta):
        raise FileNotFoundError(
            f"No existe {ruta}. Copia data_jobs.csv a esa ruta (o cambia CSV_PATH en el .env)."
        )
    # dtype=str: todo entra como texto y los tipos se aplican después, de forma explícita.
    # keep_default_na=False + na_values=[""]: solo la celda vacía cuenta como nulo. Así un
    # texto real como "NA" o "None" (por ejemplo, el nombre de una empresa) no se pierde.
    df = pd.read_csv(ruta, dtype=str, keep_default_na=False, na_values=[""])
    faltantes = [c for c in COLUMNAS_ESPERADAS if c not in df.columns]
    if faltantes:
        raise ValueError(f"Al CSV le faltan columnas: {faltantes}")
    log.info("CSV leído: %s filas", f"{len(df):,}")
    return df[COLUMNAS_ESPERADAS]


def preparar_raw(df):
    """Da el tipo correcto a cada columna para cargar la tabla raw_jobs.

    - booleanos: 'True'/'False' -> bool
    - job_posted_date -> fecha y hora
    - salarios -> número
    - job_skills -> lista de Python (se guarda como TEXT[] en PostgreSQL)
    - job_type_skills -> diccionario de Python (se guarda como JSONB en PostgreSQL)
    El texto no se modifica: la limpieza se hace después, en la fase 2.
    """
    raw = df.copy()
    for columna in COLUMNAS_BOOLEANAS:
        raw[columna] = raw[columna].apply(a_booleano)
    raw["job_posted_date"] = pd.to_datetime(raw["job_posted_date"], errors="coerce")
    for columna in COLUMNAS_SALARIO:
        raw[columna] = pd.to_numeric(raw[columna], errors="coerce")
    raw["job_skills"] = raw["job_skills"].apply(leer_lista_cruda)
    raw["job_type_skills"] = raw["job_type_skills"].apply(leer_diccionario_crudo)

    # Si el CSV traía texto en estas columnas pero no se pudo convertir, se avisa.
    for columna in ["job_skills", "job_type_skills"]:
        mal_formados = int(raw[columna].isna().sum() - df[columna].isna().sum())
        if mal_formados:
            log.warning("%s: %s valores mal formados se guardan como NULL", columna, mal_formados)

    raw.insert(0, "raw_id", range(1, len(raw) + 1))
    return raw
