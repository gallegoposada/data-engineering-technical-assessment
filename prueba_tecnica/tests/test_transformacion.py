"""Pruebas de la limpieza y del modelo 3FN (src/transformacion.py) y de las validaciones."""
import pandas as pd
import pytest

from src.ingesta import COLUMNAS_ESPERADAS
from src.transformacion import ORDEN_CARGA, construir_tablas, limpiar
from src.validacion import validar_tablas


def datos_de_prueba():
    """8 ofertas pequeñas; cada una reproduce un problema real que tiene el CSV."""
    filas = [
        # 0: versión POBRE de una oferta repetida (1 skill). Texto dañado en título y plataforma.
        ["Data Engineer", "Data  Engineer Ã¢â‚¬â€œ DBT", "Berlin, Germany", "via BeBee MÃ©xico", "Full-time and Contractor",
         "False", "Germany", "2023-01-05 10:00:00", "False", "True", "Germany", "year", "100000", None, "BOEING",
         "['python']", "{'programming': ['python']}"],
        # 1: remota, salario por hora, la misma empresa escrita distinto
        ["Data Analyst", "Data Analyst", "Anywhere", "via LinkedIn", "Part-time",
         "True", "Georgia", "2023-02-01 09:30:00", "True", "False", "United States", "hour", None, "45.5", "Boeing",
         "['excel']", "{'analyst_tools': ['excel']}"],
        # 2: sin skills, sin ubicación y sin jornada
        ["Data Scientist", "Data Scientist", None, "via Indeed", None,
         "False", "Georgia", "2023-03-01 08:00:00", "False", "False", "United States", None, None, None, "Acme",
         None, None],
        # 3: la MISMA oferta que la 0 pero más completa (skills repetidas y una skill en dos tipos)
        ["Data Engineer", "Data  Engineer Ã¢â‚¬â€œ DBT", "Berlin, Germany", "via BeBee MÃ©xico", "Full-time and Contractor",
         "False", "Germany", "2023-01-05 10:00:00", "False", "True", "Germany", "year", "100000", None, "BOEING",
         "['Python', 'sql', 'python', 'sas']", "{'programming': ['python', 'sas'], 'analyst_tools': ['sas', 'sql']}"],
        # 4: otra oferta distinta
        ["Data Analyst", "Analyst", "Tbilisi, Georgia", "via LinkedIn", "Full-time",
         "False", "Tbilisi", "2023-04-01 08:00:00", "False", "False", "Georgia", None, None, None, "Acme",
         "['sql']", "{'programming': ['sql']}"],
        # 5: booleanos en minúscula
        ["Senior Data Engineer", "Sr DE", "Austin, TX", "via LinkedIn", "Full-time",
         "false", "Texas", "2023-05-01 08:00:00", "true", "False", "United States", None, None, None, "Zeta Corp",
         "['aws']", "{'cloud': ['aws']}"],
        # 6: jornada con comas, tasa 'month' sin monto, búsqueda sin país
        ["Data Engineer", "DE Mensual", "Libreville", "via LinkedIn", "Full-time, Part-time, and Internship",
         "False", "Gabon", "2023-06-01 08:00:00", "False", "False", None, "month", None, None, "Acme",
         "['sql']", "{'programming': ['sql']}"],
        # 7: jornada en indonesio
        ["Data Analyst", "Analista", "Jakarta", "via LinkedIn", "Pekerjaan tetap",
         "False", "Indonesia", "2023-07-01 08:00:00", "False", "False", "Indonesia", None, None, None, "Zeta Corp",
         None, None],
    ]
    return pd.DataFrame(filas, columns=COLUMNAS_ESPERADAS)


def tablas_de_prueba():
    return construir_tablas(limpiar(datos_de_prueba()))


def oferta(tablas, titulo):
    """Fila de jobs cuyo título es `titulo`."""
    return tablas["jobs"][tablas["jobs"]["job_title"] == titulo].iloc[0]


def nombres_de(tablas, puente, columna_id, catalogo, col_id_catalogo, col_nombre, job_id):
    """Nombres del catálogo asociados a una oferta a través de una tabla puente."""
    ids = tablas[puente][tablas[puente]["job_id"] == job_id][columna_id]
    cat = tablas[catalogo].set_index(col_id_catalogo)
    return set(cat.loc[ids, col_nombre])


def test_se_generan_las_14_tablas_en_orden_de_carga():
    assert list(tablas_de_prueba()) == ORDEN_CARGA
    assert len(ORDEN_CARGA) == 14


def test_ofertas_repetidas_se_eliminan_y_queda_la_mas_completa():
    tablas = tablas_de_prueba()
    assert len(tablas["jobs"]) == 7  # 8 filas de entrada, 1 repetida
    job = oferta(tablas, "Data Engineer – DBT")
    skills = nombres_de(tablas, "job_skills", "skill_id", "skills", "skill_id", "skill_name", job["job_id"])
    assert skills == {"python", "sql", "sas"}  # no quedó la versión pobre (solo 'python')


def test_texto_danado_se_repara_en_titulo_y_plataforma():
    tablas = tablas_de_prueba()
    assert "Data Engineer – DBT" in set(tablas["jobs"]["job_title"])
    assert "BeBee México" in set(tablas["platforms"]["platform_name"])


def test_empresas_con_distinta_capitalizacion_quedan_unificadas():
    nombres = set(tablas_de_prueba()["companies"]["company_name"])
    assert len(nombres) == 3  # BOEING/Boeing cuenta como una sola, más Acme y Zeta Corp


def test_jornadas_son_muchos_a_muchos():
    tablas = tablas_de_prueba()

    def jornadas(titulo):
        job_id = oferta(tablas, titulo)["job_id"]
        return nombres_de(tablas, "job_schedules", "schedule_type_id", "schedule_types",
                          "schedule_type_id", "schedule_type_name", job_id)

    assert jornadas("Data Engineer – DBT") == {"Full-time", "Contractor"}
    assert jornadas("DE Mensual") == {"Full-time", "Part-time", "Internship"}
    assert jornadas("Analista") == {"Full-time"}  # 'Pekerjaan tetap' traducido


def test_una_skill_puede_tener_varios_tipos():
    tablas = tablas_de_prueba()
    id_sas = int(tablas["skills"][tablas["skills"]["skill_name"] == "sas"]["skill_id"].iloc[0])
    assert (tablas["skill_type_links"]["skill_id"] == id_sas).sum() == 2


def test_oferta_sin_skills_no_tiene_filas_en_job_skills():
    tablas = tablas_de_prueba()
    job_id = oferta(tablas, "Data Scientist")["job_id"]
    assert (tablas["job_skills"]["job_id"] == job_id).sum() == 0


def test_ubicacion_vacia_queda_como_null():
    assert pd.isna(oferta(tablas_de_prueba(), "Data Scientist")["location_id"])


def test_salarios_solo_con_tasa_year_o_hour_y_monto():
    salarios = tablas_de_prueba()["job_salaries"]
    assert len(salarios) == 2  # la tasa 'month' sin monto no entra
    assert set(salarios["salary_rate"]) == {"year", "hour"}
    por_hora = salarios[salarios["salary_rate"] == "hour"].iloc[0]
    assert por_hora["salary_hour_avg"] == 45.5 and pd.isna(por_hora["salary_year_avg"])


def test_busqueda_sin_pais_queda_con_country_id_nulo():
    busquedas = tablas_de_prueba()["search_locations"]
    gabon = busquedas[busquedas["search_location_name"] == "Gabon"].iloc[0]
    assert pd.isna(gabon["country_id"])


def test_booleanos_en_texto_se_convierten():
    job = oferta(tablas_de_prueba(), "Sr DE")
    assert bool(job["job_work_from_home"]) is False
    assert bool(job["job_no_degree_mention"]) is True


def test_busqueda_con_dos_paises_distintos_lanza_error():
    df = datos_de_prueba()
    df.loc[1, "job_country"] = "Canada"  # 'Georgia' ya aparece con United States en la fila 2
    with pytest.raises(ValueError):
        construir_tablas(limpiar(df))


def test_validacion_acepta_el_modelo_correcto():
    validar_tablas(tablas_de_prueba())


def test_validacion_detecta_llave_foranea_huerfana():
    tablas = tablas_de_prueba()
    tablas["job_skills"].loc[0, "skill_id"] = 9999
    with pytest.raises(ValueError, match="job_skills.skill_id"):
        validar_tablas(tablas)


def test_validacion_detecta_llave_primaria_repetida():
    tablas = tablas_de_prueba()
    tablas["companies"] = pd.concat([tablas["companies"], tablas["companies"].iloc[[0]]])
    with pytest.raises(ValueError, match="llaves primarias repetidas"):
        validar_tablas(tablas)


def test_validacion_detecta_nulos_en_campos_obligatorios():
    tablas = tablas_de_prueba()
    tablas["jobs"].loc[0, "company_id"] = None
    with pytest.raises(ValueError, match="jobs.company_id"):
        validar_tablas(tablas)
