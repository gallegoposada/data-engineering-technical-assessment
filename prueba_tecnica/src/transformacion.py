"""Fase 2 – Transformación: de la tabla plana a 14 tablas normalizadas (3FN).

Qué hace : limpia los datos (limpiar) y los reparte en tablas conectadas por llaves (construir_tablas).
Qué recibe: el DataFrame del CSV, todo como texto (salida de ingesta.leer_csv).
Qué devuelve: un diccionario {nombre_de_tabla: DataFrame} en el orden en que se deben cargar.
Dónde se usa: src/pipeline.py.
"""
import logging

import pandas as pd

from src.ingesta import COLUMNAS_BOOLEANAS, COLUMNAS_SALARIO
from src.limpieza import (
    a_booleano,
    leer_pares_tipo_skill,
    leer_skills,
    limpiar_texto,
    quitar_prefijo_via,
    separar_jornadas,
    unificar_empresas,
)

log = logging.getLogger(__name__)

# Orden de carga: primero las tablas "padre" y al final las que dependen de ellas.
ORDEN_CARGA = [
    "companies", "platforms", "title_categories", "countries", "search_locations", "locations",
    "schedule_types", "skills", "skill_types", "jobs", "job_salaries", "job_schedules",
    "job_skills", "skill_type_links",
]

COLUMNAS_TEXTO = ["job_title_short", "job_title", "job_location", "search_location", "job_country", "company_name"]
# Una oferta se identifica por estos campos; si se repiten, es la misma oferta.
COLUMNAS_IDENTIDAD = ["job_title", "company_name", "job_location", "job_via", "job_posted_date"]
# Sin estos datos no se puede guardar la oferta.
COLUMNAS_OBLIGATORIAS = ["job_title", "company_name", "job_via", "job_posted_date", "job_title_short", "search_location"]


def limpiar(df):
    """Limpia y estandariza el DataFrame del CSV y elimina ofertas repetidas."""
    df = df.copy()

    # Texto: arregla codificación dañada, espacios repetidos y vacíos.
    for columna in COLUMNAS_TEXTO:
        df[columna] = df[columna].apply(limpiar_texto)
    df["job_via"] = df["job_via"].apply(quitar_prefijo_via)
    df["salary_rate"] = df["salary_rate"].apply(limpiar_texto).str.lower()
    df["company_name"] = unificar_empresas(df["company_name"])

    # Tipos: booleanos, fecha y salarios (redondeados a 2 decimales).
    for columna in COLUMNAS_BOOLEANAS:
        df[columna] = df[columna].apply(a_booleano)
    df["job_posted_date"] = pd.to_datetime(df["job_posted_date"], errors="coerce")
    for columna in COLUMNAS_SALARIO:
        df[columna] = pd.to_numeric(df[columna], errors="coerce").round(2)

    # Columnas con varios valores: jornadas, skills y pares (tipo, skill).
    df["jornadas"] = df["job_schedule_type"].apply(separar_jornadas)
    df["skills"] = df["job_skills"].apply(leer_skills)
    df["pares_tipo_skill"] = df["job_type_skills"].apply(leer_pares_tipo_skill)

    # Se descartan las ofertas a las que les falta un dato indispensable.
    incompletas = df[COLUMNAS_OBLIGATORIAS].isna().any(axis=1)
    if incompletas.any():
        log.warning("Se descartan %s filas sin título, empresa, plataforma o fecha", int(incompletas.sum()))
        df = df[~incompletas].copy()

    # Ofertas repetidas: se conserva la que tiene más skills (la más completa).
    antes = len(df)
    df["cantidad_skills"] = df["skills"].apply(len)
    df = df.sort_values("cantidad_skills", ascending=False, kind="stable")
    df = df.drop_duplicates(subset=COLUMNAS_IDENTIDAD).sort_index().reset_index(drop=True)
    log.info("Ofertas repetidas eliminadas: %s", f"{antes - len(df):,}")

    df.insert(0, "job_id", range(1, len(df) + 1))
    return df


def _catalogo(valores, columna_id, columna_nombre):
    """Tabla catálogo: los valores distintos, ordenados, con un id numérico (1, 2, 3...)."""
    nombres = sorted(valores.dropna().unique())
    return pd.DataFrame({columna_id: range(1, len(nombres) + 1), columna_nombre: nombres})


def _ids(catalogo, columna_nombre, columna_id):
    """Diccionario nombre -> id, para convertir texto en llave foránea."""
    return dict(zip(catalogo[columna_nombre], catalogo[columna_id]))


def _tabla_salarios(df):
    """Una fila por oferta que tenga salario, con el monto que corresponde a su tasa.

    Solo se guardan las tasas 'year' y 'hour' que traen monto. Las tasas month/week/day
    del CSV vienen sin monto y no aportan información.
    """
    es_anual = (df["salary_rate"] == "year") & df["salary_year_avg"].notna() & df["salary_hour_avg"].isna()
    es_por_hora = (df["salary_rate"] == "hour") & df["salary_hour_avg"].notna() & df["salary_year_avg"].isna()
    con_algo = df["salary_rate"].notna() | df["salary_year_avg"].notna() | df["salary_hour_avg"].notna()
    omitidas = int((con_algo & ~(es_anual | es_por_hora)).sum())
    if omitidas:
        log.warning("%s ofertas con tasa de salario pero sin monto utilizable: no entran a job_salaries", omitidas)
    columnas = ["job_id", "salary_rate", "salary_year_avg", "salary_hour_avg"]
    return df.loc[es_anual | es_por_hora, columnas].reset_index(drop=True)


def construir_tablas(df):
    """Reparte el DataFrame limpio en las 14 tablas del modelo 3FN."""
    # --- Catálogos ---
    companies = _catalogo(df["company_name"], "company_id", "company_name")
    platforms = _catalogo(df["job_via"], "platform_id", "platform_name")
    title_categories = _catalogo(df["job_title_short"], "title_category_id", "title_category_name")
    countries = _catalogo(df["job_country"], "country_id", "country_name")
    locations = _catalogo(df["job_location"], "location_id", "location_name")
    schedule_types = _catalogo(df["jornadas"].explode(), "schedule_type_id", "schedule_type_name")

    # Cada búsqueda tiene un único país. Si algún día no fuera así, mejor fallar que guardar datos mezclados.
    busquedas = df[["search_location", "job_country"]].drop_duplicates().sort_values("search_location")
    if busquedas["search_location"].duplicated().any():
        raise ValueError("Una misma search_location aparece con más de un país")
    busquedas = busquedas.reset_index(drop=True)
    search_locations = pd.DataFrame({
        "search_location_id": range(1, len(busquedas) + 1),
        "search_location_name": busquedas["search_location"],
        "country_id": busquedas["job_country"].map(_ids(countries, "country_name", "country_id")).astype("Int64"),
    })

    # --- Skills: lista de skills por oferta y pares (tipo, skill) ---
    skills_por_oferta = df[["job_id", "skills"]].explode("skills").dropna(subset=["skills"])
    pares = pd.DataFrame(df["pares_tipo_skill"].explode().dropna().tolist(), columns=["tipo", "skill"]).drop_duplicates()
    todas_las_skills = pd.concat([skills_por_oferta["skills"].drop_duplicates(), pares["skill"].drop_duplicates()])
    skills = _catalogo(todas_las_skills, "skill_id", "skill_name")
    skill_types = _catalogo(pares["tipo"], "skill_type_id", "skill_type_name")
    id_skill = _ids(skills, "skill_name", "skill_id")

    # --- Tabla central: jobs ---
    jobs = pd.DataFrame({
        "job_id": df["job_id"],
        "job_title": df["job_title"],
        "title_category_id": df["job_title_short"].map(_ids(title_categories, "title_category_name", "title_category_id")),
        "company_id": df["company_name"].map(_ids(companies, "company_name", "company_id")),
        "platform_id": df["job_via"].map(_ids(platforms, "platform_name", "platform_id")),
        "location_id": df["job_location"].map(_ids(locations, "location_name", "location_id")).astype("Int64"),
        "search_location_id": df["search_location"].map(_ids(search_locations, "search_location_name", "search_location_id")),
        "posted_at": df["job_posted_date"],
        "job_work_from_home": df["job_work_from_home"],
        "job_no_degree_mention": df["job_no_degree_mention"],
        "job_health_insurance": df["job_health_insurance"],
    })

    # --- Tablas puente ---
    jornadas = df[["job_id", "jornadas"]].explode("jornadas").dropna(subset=["jornadas"])
    job_schedules = pd.DataFrame({
        "job_id": jornadas["job_id"],
        "schedule_type_id": jornadas["jornadas"].map(_ids(schedule_types, "schedule_type_name", "schedule_type_id")),
    }).reset_index(drop=True)
    job_skills = pd.DataFrame({
        "job_id": skills_por_oferta["job_id"],
        "skill_id": skills_por_oferta["skills"].map(id_skill),
    }).reset_index(drop=True)
    skill_type_links = pd.DataFrame({
        "skill_id": pares["skill"].map(id_skill),
        "skill_type_id": pares["tipo"].map(_ids(skill_types, "skill_type_name", "skill_type_id")),
    }).reset_index(drop=True)

    tablas = {
        "companies": companies, "platforms": platforms, "title_categories": title_categories,
        "countries": countries, "search_locations": search_locations, "locations": locations,
        "schedule_types": schedule_types, "skills": skills, "skill_types": skill_types,
        "jobs": jobs, "job_salaries": _tabla_salarios(df), "job_schedules": job_schedules,
        "job_skills": job_skills, "skill_type_links": skill_type_links,
    }
    for nombre in ORDEN_CARGA:
        log.info("Tabla %-17s %9s filas", nombre, f"{len(tablas[nombre]):,}")
    return tablas
