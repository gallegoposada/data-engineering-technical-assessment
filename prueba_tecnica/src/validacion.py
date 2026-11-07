"""Validaciones de calidad de datos, antes de cargar nada a la base de datos.

Qué hace : revisa que las 14 tablas sean consistentes (llaves únicas, sin nulos donde no se permite,
           llaves foráneas que apuntan a algo que existe y salarios positivos).
Qué recibe: el diccionario de DataFrames que devuelve transformacion.construir_tablas().
Qué devuelve: nada si todo está bien; lanza ValueError con la lista de problemas si algo falla.
Dónde se usa: src/pipeline.py. Si falla, el pipeline se detiene y la base de datos no se toca.
"""
import logging

log = logging.getLogger(__name__)

# Columnas que forman la llave primaria de cada tabla.
LLAVES_PRIMARIAS = {
    "companies": ["company_id"], "platforms": ["platform_id"], "title_categories": ["title_category_id"],
    "countries": ["country_id"], "search_locations": ["search_location_id"], "locations": ["location_id"],
    "schedule_types": ["schedule_type_id"], "skills": ["skill_id"], "skill_types": ["skill_type_id"],
    "jobs": ["job_id"], "job_salaries": ["job_id"], "job_schedules": ["job_id", "schedule_type_id"],
    "job_skills": ["job_id", "skill_id"], "skill_type_links": ["skill_id", "skill_type_id"],
}

# (tabla hija, columna, tabla padre, columna del padre)
LLAVES_FORANEAS = [
    ("search_locations", "country_id", "countries", "country_id"),
    ("jobs", "title_category_id", "title_categories", "title_category_id"),
    ("jobs", "company_id", "companies", "company_id"),
    ("jobs", "platform_id", "platforms", "platform_id"),
    ("jobs", "location_id", "locations", "location_id"),
    ("jobs", "search_location_id", "search_locations", "search_location_id"),
    ("job_salaries", "job_id", "jobs", "job_id"),
    ("job_schedules", "job_id", "jobs", "job_id"),
    ("job_schedules", "schedule_type_id", "schedule_types", "schedule_type_id"),
    ("job_skills", "job_id", "jobs", "job_id"),
    ("job_skills", "skill_id", "skills", "skill_id"),
    ("skill_type_links", "skill_id", "skills", "skill_id"),
    ("skill_type_links", "skill_type_id", "skill_types", "skill_type_id"),
]

# Columnas de jobs que no pueden tener nulos (las demás son opcionales).
JOBS_SIN_NULOS = [
    "job_title", "title_category_id", "company_id", "platform_id", "search_location_id",
    "posted_at", "job_work_from_home", "job_no_degree_mention", "job_health_insurance",
]


def validar_tablas(tablas):
    """Ejecuta todas las revisiones y lanza ValueError si encuentra algún problema."""
    problemas = []

    for tabla, columnas in LLAVES_PRIMARIAS.items():
        repetidas = int(tablas[tabla].duplicated(subset=columnas).sum())
        if repetidas:
            problemas.append(f"{tabla}: {repetidas} llaves primarias repetidas {columnas}")

    for hija, columna, padre, columna_padre in LLAVES_FORANEAS:
        valores = tablas[hija][columna].dropna()  # los NULL son válidos (campos opcionales)
        huerfanos = int((~valores.isin(tablas[padre][columna_padre])).sum())
        if huerfanos:
            problemas.append(f"{hija}.{columna}: {huerfanos} valores que no existen en {padre}.{columna_padre}")

    for columna in JOBS_SIN_NULOS:
        nulos = int(tablas["jobs"][columna].isna().sum())
        if nulos:
            problemas.append(f"jobs.{columna}: {nulos} nulos")

    salarios = tablas["job_salaries"]
    montos = salarios[["salary_year_avg", "salary_hour_avg"]].stack()  # solo los montos que existen
    if (montos <= 0).any():
        problemas.append("job_salaries: hay salarios menores o iguales a cero")

    if problemas:
        raise ValueError("Falló la validación de datos:\n- " + "\n- ".join(problemas))
    log.info("Validación superada: llaves primarias, llaves foráneas, nulos y salarios")
