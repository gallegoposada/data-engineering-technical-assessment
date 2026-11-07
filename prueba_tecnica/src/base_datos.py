"""Conexión a PostgreSQL y carga de DataFrames a tablas.

Qué hace : abre la conexión (con credenciales del archivo .env), crea las tablas ejecutando
           sql/schema.sql y carga cada DataFrame en su tabla por bloques.
Qué recibe: variables de entorno DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD; DataFrames a cargar.
Qué devuelve: una conexión abierta (conectar) o inserta filas en la base (cargar_tabla).
Dónde se usa: src/pipeline.py.
"""
import logging
import os
from pathlib import Path

import pandas as pd
import psycopg2
from psycopg2.extras import Json, execute_values

log = logging.getLogger(__name__)

RUTA_ESQUEMA = Path(__file__).resolve().parents[1] / "sql" / "schema.sql"


def conectar():
    """Abre la conexión a PostgreSQL usando variables de entorno (nada de claves en el código)."""
    try:
        return psycopg2.connect(
            host=os.environ["DB_HOST"],
            port=os.environ["DB_PORT"],
            dbname=os.environ["DB_NAME"],
            user=os.environ["DB_USER"],
            password=os.environ["DB_PASSWORD"],
        )
    except KeyError as error:
        raise RuntimeError(f"Falta la variable de entorno {error}. Copia .env.example a .env y complétalo.") from error


def crear_esquema(conexion):
    """Ejecuta sql/schema.sql: borra las tablas anteriores y crea todas de nuevo."""
    with conexion.cursor() as cursor:
        cursor.execute(RUTA_ESQUEMA.read_text(encoding="utf-8"))
    log.info("Esquema creado (raw_jobs + 14 tablas normalizadas)")


def cargar_tabla(conexion, tabla, df, columnas_json=(), tam_bloque=50_000):
    """Inserta un DataFrame en una tabla, por bloques para no gastar demasiada memoria.

    - Los nulos de pandas (NaN, NaT, NA) se convierten en NULL.
    - Las fechas se envían como texto 'AAAA-MM-DD HH:MM:SS'.
    - Las columnas indicadas en `columnas_json` (diccionarios) se envían como JSON.
    - Las listas de Python se envían como arreglos de PostgreSQL.
    """
    if df.empty:
        return
    sql = f"INSERT INTO {tabla} ({', '.join(df.columns)}) VALUES %s"
    with conexion.cursor() as cursor:
        for inicio in range(0, len(df), tam_bloque):
            bloque = df.iloc[inicio:inicio + tam_bloque].copy()
            for columna in bloque.columns:
                if pd.api.types.is_datetime64_any_dtype(bloque[columna]):
                    bloque[columna] = bloque[columna].dt.strftime("%Y-%m-%d %H:%M:%S")
            bloque = bloque.astype(object).where(bloque.notna(), None)
            for columna in columnas_json:
                bloque[columna] = bloque[columna].map(lambda d: Json(d) if d is not None else None)
            filas = list(bloque.itertuples(index=False, name=None))
            execute_values(cursor, sql, filas, page_size=5000)
    log.info("Cargada %-17s %9s filas", tabla, f"{len(df):,}")
