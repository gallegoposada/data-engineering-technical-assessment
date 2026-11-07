"""Pruebas de la carga a PostgreSQL (src/base_datos.py), sin necesidad de una base de datos real.

Se reemplaza `execute_values` por una función que guarda lo que recibiría PostgreSQL, y así se revisa
que los datos viajen con los tipos que psycopg2 sabe enviar (nada de tipos de numpy, nulos como None...).
También se comprueba que sql/schema.sql y el código estén de acuerdo en tablas y columnas.
"""
import re

import numpy as np
import pandas as pd
from psycopg2.extras import Json

from src import base_datos
from src.ingesta import preparar_raw
from src.transformacion import ORDEN_CARGA, construir_tablas, limpiar
from tests.test_ingesta import escribir_csv, fila
from tests.test_transformacion import datos_de_prueba


class CursorFalso:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class ConexionFalsa:
    def cursor(self):
        return CursorFalso()


def cargar_y_capturar(df, **opciones):
    """Ejecuta cargar_tabla con una conexión falsa y devuelve las llamadas a execute_values."""
    llamadas = []

    def execute_values_falso(cursor, sql, filas, page_size=0):
        llamadas.append((sql, filas))

    original = base_datos.execute_values
    base_datos.execute_values = execute_values_falso
    try:
        base_datos.cargar_tabla(ConexionFalsa(), "tabla", df, **opciones)
    finally:
        base_datos.execute_values = original
    return llamadas


def test_cargar_tabla_arma_el_insert_con_las_columnas_del_dataframe():
    llamadas = cargar_y_capturar(pd.DataFrame({"a": [1], "b": ["x"]}))
    assert llamadas[0][0] == "INSERT INTO tabla (a, b) VALUES %s"


def test_cargar_tabla_convierte_todos_los_nulos_de_pandas_en_none():
    df = pd.DataFrame({
        "decimal": [1.5, np.nan],
        "entero": pd.array([1, None], dtype="Int64"),
        "fecha": pd.to_datetime(["2023-01-05 10:00:00", None]),
        "texto": ["a", None],
    })
    segunda_fila = cargar_y_capturar(df)[0][1][1]
    assert segunda_fila == (None, None, None, None)


def test_cargar_tabla_envia_solo_tipos_que_psycopg2_sabe_adaptar():
    df = pd.DataFrame({
        "entero": np.array([1, 2], dtype="int64"),
        "decimal": [1.5, 2.5],
        "booleano": [True, False],
        "id_opcional": pd.array([7, None], dtype="Int64"),
        "texto": ["a", "b"],
    })
    for fila_enviada in cargar_y_capturar(df)[0][1]:
        for valor in fila_enviada:
            assert type(valor) in (int, float, bool, str, type(None)), f"tipo no permitido: {type(valor)}"


def test_cargar_tabla_envia_las_fechas_como_texto():
    df = pd.DataFrame({"fecha": pd.to_datetime(["2023-01-05 10:00:00"])})
    assert cargar_y_capturar(df)[0][1][0] == ("2023-01-05 10:00:00",)


def test_cargar_tabla_envuelve_diccionarios_en_json_y_deja_las_listas():
    df = pd.DataFrame({"lista": [["a", "b"]], "diccionario": [{"k": ["a"]}]})
    lista, diccionario = cargar_y_capturar(df, columnas_json=["diccionario"])[0][1][0]
    assert lista == ["a", "b"]                      # psycopg2 convierte las listas en arreglos de PostgreSQL
    assert isinstance(diccionario, Json)            # y los diccionarios en JSON


def test_cargar_tabla_divide_los_datos_en_bloques():
    llamadas = cargar_y_capturar(pd.DataFrame({"a": range(5)}), tam_bloque=2)
    assert [len(filas) for _, filas in llamadas] == [2, 2, 1]


def test_cargar_tabla_con_dataframe_vacio_no_hace_nada():
    assert cargar_y_capturar(pd.DataFrame({"a": []})) == []


def columnas_del_esquema():
    """Lee sql/schema.sql y devuelve {tabla: [columnas]} (ignora comentarios y restricciones)."""
    sql = "\n".join(linea.split("--")[0] for linea in base_datos.RUTA_ESQUEMA.read_text(encoding="utf-8").splitlines())
    tipos = r"(?:INTEGER|TEXT\[\]|TEXT|TIMESTAMP|BOOLEAN|JSONB|NUMERIC\(\d+, \d+\))"
    esquema = {}
    for tabla, cuerpo in re.findall(r"CREATE TABLE (\w+) \((.*?)\n\);", sql, re.S):
        esquema[tabla] = re.findall(rf"^\s*(\w+)\s+{tipos}(?=[\s,])", cuerpo, re.M)
    return esquema


def test_el_esquema_tiene_las_tablas_que_el_pipeline_carga():
    assert set(columnas_del_esquema()) == set(ORDEN_CARGA) | {"raw_jobs"}


def test_las_columnas_de_cada_dataframe_coinciden_con_el_esquema():
    esquema = columnas_del_esquema()
    tablas = construir_tablas(limpiar(datos_de_prueba()))
    for nombre in ORDEN_CARGA:
        assert list(tablas[nombre].columns) == esquema[nombre], f"columnas distintas en {nombre}"


def test_las_columnas_de_raw_jobs_coinciden_con_el_esquema(tmp_path):
    from src.ingesta import leer_csv

    raw = preparar_raw(leer_csv(escribir_csv(tmp_path / "datos.csv", [fila()])))
    assert list(raw.columns) == columnas_del_esquema()["raw_jobs"]
