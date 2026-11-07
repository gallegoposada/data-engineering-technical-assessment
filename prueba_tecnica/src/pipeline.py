"""Punto de entrada: corre todo el proceso, de principio a fin.

Pasos: leer CSV -> tipar raw -> limpiar y normalizar -> validar -> crear esquema -> cargar.
Se ejecuta con:  python -m src.pipeline
Toda la carga a la base de datos ocurre en UNA transacción: si algo falla, no queda nada a medias.
"""
import logging
import os
import time

from dotenv import load_dotenv

from src.base_datos import cargar_tabla, conectar, crear_esquema
from src.ingesta import leer_csv, preparar_raw
from src.transformacion import ORDEN_CARGA, construir_tablas, limpiar
from src.validacion import validar_tablas

log = logging.getLogger(__name__)


def main():
    load_dotenv()  # lee el archivo .env (credenciales y ruta del CSV)
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO"),
        format="%(asctime)s | %(levelname)s | %(message)s",
    )
    inicio = time.time()

    # Fase 1: ingesta
    df = leer_csv(os.getenv("CSV_PATH", "data/data_jobs.csv"))
    raw = preparar_raw(df)

    # Fase 2: transformación y validación (todo en memoria, la base de datos aún no se toca)
    df_limpio = limpiar(df)
    del df
    tablas = construir_tablas(df_limpio)
    validar_tablas(tablas)
    log.info("Filas del CSV: %s -> ofertas únicas: %s", f"{len(raw):,}", f"{len(tablas['jobs']):,}")

    # Carga: una sola transacción
    conexion = conectar()
    try:
        crear_esquema(conexion)
        cargar_tabla(conexion, "raw_jobs", raw, columnas_json=["job_type_skills"])
        for nombre in ORDEN_CARGA:
            cargar_tabla(conexion, nombre, tablas[nombre])
        conexion.commit()
    except Exception:
        conexion.rollback()
        log.exception("Falló la carga: se deshizo todo (rollback)")
        raise
    finally:
        conexion.close()
    log.info("Proceso terminado en %.0f segundos", time.time() - inicio)


if __name__ == "__main__":
    main()
