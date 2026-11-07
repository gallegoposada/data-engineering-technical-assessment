"""Pruebas de la ingesta (src/ingesta.py): lectura del CSV y tipado de la tabla raw_jobs."""
import pandas as pd
import pytest

from src.ingesta import COLUMNAS_ESPERADAS, leer_csv, preparar_raw


def fila(**cambios):
    """Una fila de ejemplo con las 17 columnas; `cambios` permite modificar columnas concretas."""
    base = {
        "job_title_short": "Data Engineer", "job_title": "Data Engineer", "job_location": "Berlin, Germany",
        "job_via": "via BeBee MÃ©xico", "job_schedule_type": "Full-time", "job_work_from_home": "False",
        "search_location": "Germany", "job_posted_date": "2023-01-05 10:00:00", "job_no_degree_mention": "True",
        "job_health_insurance": "False", "job_country": "Germany", "salary_rate": "year",
        "salary_year_avg": "100000", "salary_hour_avg": None, "company_name": "Acme",
        "job_skills": "['python', 'sql']", "job_type_skills": "{'programming': ['python', 'sql']}",
    }
    base.update(cambios)
    return base


def escribir_csv(ruta, filas, columnas=COLUMNAS_ESPERADAS):
    pd.DataFrame(filas).reindex(columns=columnas).to_csv(ruta, index=False)
    return ruta


def test_leer_csv_devuelve_las_17_columnas_como_texto(tmp_path):
    df = leer_csv(escribir_csv(tmp_path / "datos.csv", [fila()]))
    assert list(df.columns) == COLUMNAS_ESPERADAS
    assert df["salary_year_avg"].iloc[0] == "100000"       # sigue siendo texto: el tipo se aplica después
    assert df["job_work_from_home"].iloc[0] == "False"


def test_leer_csv_no_confunde_textos_reales_con_nulos(tmp_path):
    filas = [fila(company_name="NA"), fila(company_name="None"), fila(company_name=None)]
    df = leer_csv(escribir_csv(tmp_path / "datos.csv", filas))
    assert list(df["company_name"].iloc[:2]) == ["NA", "None"]  # empresas con esos nombres no se pierden
    assert pd.isna(df["company_name"].iloc[2])                  # la celda vacía sí es nulo


def test_leer_csv_con_archivo_inexistente_explica_que_hacer(tmp_path):
    with pytest.raises(FileNotFoundError, match="data_jobs.csv"):
        leer_csv(tmp_path / "no_existe.csv")


def test_leer_csv_con_columnas_faltantes_lanza_error(tmp_path):
    columnas = [c for c in COLUMNAS_ESPERADAS if c != "company_name"]
    with pytest.raises(ValueError, match="company_name"):
        leer_csv(escribir_csv(tmp_path / "datos.csv", [fila()], columnas))


def test_preparar_raw_convierte_cada_columna_a_su_tipo(tmp_path):
    raw = preparar_raw(leer_csv(escribir_csv(tmp_path / "datos.csv", [fila()])))
    primera = raw.iloc[0]
    assert bool(primera["job_work_from_home"]) is False and bool(primera["job_no_degree_mention"]) is True
    assert primera["job_posted_date"] == pd.Timestamp("2023-01-05 10:00:00")
    assert primera["salary_year_avg"] == 100000.0 and pd.isna(primera["salary_hour_avg"])
    assert primera["job_skills"] == ["python", "sql"]
    assert primera["job_type_skills"] == {"programming": ["python", "sql"]}


def test_preparar_raw_no_limpia_el_texto_y_agrega_raw_id(tmp_path):
    raw = preparar_raw(leer_csv(escribir_csv(tmp_path / "datos.csv", [fila(), fila(job_title="Otro")])))
    assert list(raw["raw_id"]) == [1, 2]
    assert raw["job_via"].iloc[0] == "via BeBee MÃ©xico"  # la capa raw conserva el texto original


def test_preparar_raw_con_listas_mal_formadas_las_deja_nulas(tmp_path):
    filas = [fila(job_skills="['python', ", job_type_skills="no es un diccionario"), fila(job_skills=None, job_type_skills=None)]
    raw = preparar_raw(leer_csv(escribir_csv(tmp_path / "datos.csv", filas)))
    assert raw["job_skills"].isna().all() and raw["job_type_skills"].isna().all()
