import sys
from pathlib import Path
import pytest
from airflow.models import DagBag

# Localizamos la raíz del proyecto (un nivel arriba de la carpeta del DAG)
RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

@pytest.fixture(scope="session")
def dag_bag():
    """Busca y carga los DAGs apuntando directamente a tu carpeta 'airflow'."""
    ruta_dags = RAIZ / "airflow"
    return DagBag(dag_folder=str(ruta_dags), include_examples=False)

def test_dag_carga_sin_errores(dag_bag):
    """Comprueba que Airflow no encuentre errores de sintaxis al leer tu código."""
    assert len(dag_bag.import_errors) == 0, f"Errores encontrados por Airflow: {dag_bag.import_errors}"

def test_dag_estructura_y_tareas(dag_bag):
    """Verifica que tu DAG se registre con el ID correcto y sus 3 tareas."""
    dag_id = "pipeline_ofertas_laborales"
    assert dag_id in dag_bag.dags, f"No se encontró el DAG con ID: {dag_id}"
    
    dag = dag_bag.dags[dag_id]
    tareas_esperadas = {"verificar_csv", "ejecutar_pipeline", "verificar_carga"}
    assert set(dag.task_ids) == tareas_esperadas, "Los IDs de tus tareas PythonOperator no coinciden."
    
    # Valida el orden de tus flechas (tarea_csv >> tarea_pipeline >> tarea_carga)
    task_csv = dag.get_task("verificar_csv")
    task_pipeline = dag.get_task("ejecutar_pipeline")
    
    assert "ejecutar_pipeline" in task_csv.downstream_task_ids, "La tarea 'ejecutar_pipeline' no va después de verificar el CSV."
    assert "verificar_carga" in task_pipeline.downstream_task_ids, "La tarea 'verificar_carga' no va al final del pipeline."

def test_dag_no_tiene_ciclos(dag_bag):
    """Verifica que no existan bucles infinitos en el flujo de tareas."""
    dag = dag_bag.dags["pipeline_ofertas_laborales"]
    from airflow.utils.dag_cycle_tester import check_cycle
    try:
        check_cycle(dag)
    except Exception as e:
        pytest.fail(f"Se detectó un ciclo infinito en el DAG: {e}")
