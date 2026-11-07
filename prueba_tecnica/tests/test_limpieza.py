"""Pruebas de las funciones de limpieza (src/limpieza.py)."""
import pandas as pd

from src.limpieza import (
    a_booleano,
    leer_pares_tipo_skill,
    leer_skills,
    limpiar_texto,
    quitar_prefijo_via,
    reparar_codificacion,
    separar_jornadas,
    unificar_empresas,
)


def test_reparar_codificacion_arregla_acentos():
    assert reparar_codificacion("BeBee MÃ©xico") == "BeBee México"
    assert reparar_codificacion("BeBee PerÃº") == "BeBee Perú"


def test_reparar_codificacion_arregla_dano_doble_y_emojis():
    assert reparar_codificacion("Data Engineer Ã¢â‚¬â€œ DBT") == "Data Engineer – DBT"
    assert reparar_codificacion("ðŸ‘¨") == "👨"


def test_reparar_codificacion_no_toca_texto_correcto():
    for texto in ["São Paulo", "Zürich", "高級工程師", "texto normal"]:
        assert reparar_codificacion(texto) == texto


def test_limpiar_texto_quita_espacios_y_convierte_vacios_en_none():
    assert limpiar_texto("  Data   Engineer \n") == "Data Engineer"
    assert limpiar_texto("   ") is None
    assert limpiar_texto(None) is None
    assert limpiar_texto(float("nan")) is None


def test_quitar_prefijo_via():
    assert quitar_prefijo_via("via LinkedIn") == "LinkedIn"
    assert quitar_prefijo_via("via BeBee MÃ©xico") == "BeBee México"
    assert quitar_prefijo_via("melalui Trigyn") == "Trigyn"  # "via" en indonesio
    assert quitar_prefijo_via(None) is None


def test_a_booleano():
    assert a_booleano("True") is True
    assert a_booleano("False") is False
    assert a_booleano("true") is True
    assert a_booleano(None) is None
    assert a_booleano("quizas") is None


def test_separar_jornadas_con_and_y_con_comas():
    assert separar_jornadas("Full-time and Contractor") == ("Full-time", "Contractor")
    assert separar_jornadas("Full-time, Part-time, and Internship") == ("Full-time", "Part-time", "Internship")
    assert separar_jornadas("Part-time") == ("Part-time",)
    assert separar_jornadas(None) == ()


def test_separar_jornadas_traduce_indonesio():
    assert separar_jornadas("Pekerjaan tetap") == ("Full-time",)
    assert separar_jornadas("Kontraktor") == ("Contractor",)


def test_leer_skills_quita_repetidos_y_pasa_a_minuscula():
    assert leer_skills("['Python', 'sql', 'python', ' SQL ']") == ("python", "sql")
    assert leer_skills(None) == ()


def test_leer_skills_con_texto_mal_formado_devuelve_vacio():
    assert leer_skills("['python', ") == ()
    assert leer_skills("{'a': 1}") == ()  # es un diccionario, no una lista


def test_leer_skills_no_ejecuta_codigo():
    assert leer_skills("__import__('os').system('echo hack')") == ()


def test_leer_pares_tipo_skill():
    texto = "{'Programming': ['Python', 'python', 'sas'], 'analyst_tools': ['sas'], 'cloud': []}"
    assert leer_pares_tipo_skill(texto) == (
        ("programming", "python"), ("programming", "sas"), ("analyst_tools", "sas"),
    )
    assert leer_pares_tipo_skill(None) == ()


def test_unificar_empresas_usa_el_nombre_mas_frecuente():
    empresas = pd.Series(["BOEING", "Boeing", "Boeing", "Acme", None])
    resultado = unificar_empresas(empresas)
    assert list(resultado.iloc[:4]) == ["Boeing", "Boeing", "Boeing", "Acme"]
    assert pd.isna(resultado.iloc[4])


def test_unificar_empresas_si_empatan_prefiere_la_que_no_es_mayuscula():
    resultado = unificar_empresas(pd.Series(["LEIDOS", "Leidos"]))
    assert list(resultado) == ["Leidos", "Leidos"]
