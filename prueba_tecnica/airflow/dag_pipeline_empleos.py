import os
import sys
from datetime import datetime
from pathlib import Path

from airflow import DAG
from airflow.operators.python import PythonOperator
from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))  # permite importar el paquete src desde el DAG


def preparar_entorno():
    """Se ubica en la carpeta del proyecto y carga el .env, igual que al correr el pipeline a mano."""
    os.chdir(RAIZ)
    load_dotenv(RAIZ / ".env")


def verificar_csv():
    """Falla pronto (y con un mensaje claro) si el CSV de entrada no está."""
    preparar_entorno()
    ruta = Path(os.getenv("CSV_PATH", "data/data_jobs.csv"))
    if not ruta.exists():
        raise FileNotFoundError(f"No se encontró {ruta}. Copia data_jobs.csv a esa ruta.")
    print(f"CSV encontrado: {ruta} ({ruta.stat().st_size / 1_000_000:.0f} MB)")


def ejecutar_pipeline():
    """Corre el pipeline completo. Se importa aquí adentro para que Airflow lea el DAG rápido (sin cargar pandas)."""
    preparar_entorno()
    from src.pipeline import main

    main()


def verificar_carga():
    """Comprueba que la carga dejó ofertas y que no hay más ofertas que filas del CSV."""
    preparar_entorno()
    from src.base_datos import conectar

    conexion = conectar()
    try:
        with conexion.cursor() as cursor:
            cursor.execute("SELECT (SELECT COUNT(*) FROM raw_jobs), (SELECT COUNT(*) FROM jobs)")
            filas_raw, filas_jobs = cursor.fetchone()
    finally:
        conexion.close()
    if filas_jobs == 0 or filas_jobs > filas_raw:
        raise ValueError(f"Carga incoherente: raw_jobs={filas_raw}, jobs={filas_jobs}")
    print(f"Carga correcta: {filas_raw:,} filas en raw_jobs y {filas_jobs:,} ofertas únicas en jobs")


with DAG(
    dag_id="pipeline_ofertas_laborales",
    description="CSV de ofertas laborales -> PostgreSQL (raw_jobs + modelo 3FN)",
    start_date=datetime(2024, 1, 1),
    schedule=None,  # sin horario: se lanza a mano desde la interfaz de Airflow
    catchup=False,
    tags=["prueba_tecnica"],
) as dag:
    tarea_csv = PythonOperator(task_id="verificar_csv", python_callable=verificar_csv)
    tarea_pipeline = PythonOperator(task_id="ejecutar_pipeline", python_callable=ejecutar_pipeline)
    tarea_carga = PythonOperator(task_id="verificar_carga", python_callable=verificar_carga)

    tarea_csv >> tarea_pipeline >> tarea_carga
