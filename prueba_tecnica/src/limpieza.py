"""Funciones de limpieza de datos.

Qué hace : cada función arregla UN problema concreto de calidad que se encontró en el CSV.
Qué recibe: un valor suelto (texto, booleano en texto, lista en texto...) o una serie de pandas.
Qué devuelve: el valor ya limpio (o None si no hay dato).
Dónde se usa: src/ingesta.py (tipado de la tabla raw) y src/transformacion.py (limpieza completa).

Son funciones pequeñas y sin base de datos, por eso es fácil probarlas con pytest.
"""
import ast
import re
from functools import cache

import pandas as pd

# Tramo de caracteres "raros" (no ASCII). Ahí es donde aparece el texto dañado.
TRAMO_NO_ASCII = re.compile(r"[^\x00-\x7f]+")

# En el CSV las columnas booleanas vienen como texto 'True' / 'False'.
BOOLEANOS = {"True": True, "False": False}

# Jornadas escritas en indonesio que se llevan a su equivalente en inglés.
ALIAS_JORNADAS = {"kontraktor": "Contractor", "pekerjaan tetap": "Full-time"}


def _reparar_tramo(tramo):
    """Intenta arreglar un tramo de texto dañado ("Ã©" -> "é").

    El daño ocurre cuando un texto UTF-8 se lee como si fuera cp1252. Para deshacerlo se
    vuelve a convertir el tramo a bytes con cp1252 y se decodifica como UTF-8.
    Si no se puede, el tramo se devuelve igual (era texto legítimo, como "São").
    """
    bytes_originales = bytearray()
    for letra in tramo:
        try:
            bytes_originales += letra.encode("cp1252")
        except UnicodeEncodeError:
            if ord(letra) > 255:
                return tramo  # no puede venir de cp1252: es texto legítimo (p. ej. chino)
            bytes_originales.append(ord(letra))  # byte que cp1252 no define: se conserva su valor
    try:
        return bytes(bytes_originales).decode("utf-8")
    except UnicodeDecodeError:
        return tramo


def reparar_codificacion(texto):
    """Repara el texto dañado, tramo por tramo, para no tocar lo que ya estaba bien.

    Se repite hasta 3 veces porque hay textos dañados DOS veces ("Ã¢â‚¬â€œ" -> "â€“" -> "–").
    """
    for _ in range(3):
        if texto.isascii():
            break
        reparado = TRAMO_NO_ASCII.sub(lambda tramo: _reparar_tramo(tramo.group()), texto)
        if reparado == texto:
            break
        texto = reparado
    return texto


def limpiar_texto(valor):
    """Repara la codificación, quita espacios repetidos y convierte vacíos en None."""
    if pd.isna(valor):
        return None
    texto = reparar_codificacion(str(valor))
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto or None


def quitar_prefijo_via(valor):
    """'via LinkedIn' -> 'LinkedIn'. El prefijo viene del scraping y no aporta.

    También se quita 'melalui' (que es "via" en indonesio y aparece en unas 60 filas).
    """
    texto = limpiar_texto(valor)
    if texto is None:
        return None
    return re.sub(r"^(via|melalui)\s+", "", texto, flags=re.IGNORECASE) or None


def a_booleano(valor):
    """'True'/'False' (texto) -> True/False. Si no se reconoce, devuelve None."""
    if isinstance(valor, bool):
        return valor
    if pd.isna(valor):
        return None
    return BOOLEANOS.get(str(valor).strip().capitalize())


def separar_jornadas(valor):
    """Separa la jornada en valores sueltos.

    'Full-time and Contractor'             -> ('Full-time', 'Contractor')
    'Full-time, Part-time, and Internship' -> ('Full-time', 'Part-time', 'Internship')
    'Pekerjaan tetap'                      -> ('Full-time',)
    """
    texto = limpiar_texto(valor)
    if texto is None:
        return ()
    partes = [p.strip() for p in re.split(r",\s*(?:and\s+)?|\s+and\s+", texto) if p.strip()]
    partes = [ALIAS_JORNADAS.get(p.casefold(), p) for p in partes]
    return tuple(dict.fromkeys(partes))  # sin repetidos y en el mismo orden


@cache
def _evaluar_literal(texto):
    """Convierte el texto "['a', 'b']" o "{'k': ['a']}" en lista o diccionario real.

    Usa ast.literal_eval (seguro: solo entiende literales, no ejecuta código).
    Con @cache, un texto que se repite en miles de filas se interpreta una sola vez.
    """
    try:
        return ast.literal_eval(texto)
    except (ValueError, SyntaxError):
        return None


def leer_lista_cruda(valor):
    """Texto -> lista de Python (sin limpiar). None si está vacío o mal formado."""
    if pd.isna(valor):
        return None
    resultado = _evaluar_literal(valor)
    return resultado if isinstance(resultado, list) else None


def leer_diccionario_crudo(valor):
    """Texto -> diccionario de Python (sin limpiar). None si está vacío o mal formado."""
    if pd.isna(valor):
        return None
    resultado = _evaluar_literal(valor)
    return resultado if isinstance(resultado, dict) else None


def leer_skills(valor):
    """Texto -> tupla de skills en minúscula y sin repetidos (la tupla vacía si no hay)."""
    lista = leer_lista_cruda(valor) or []
    nombres = [str(skill).strip().lower() for skill in lista if str(skill).strip()]
    return tuple(dict.fromkeys(nombres))


def leer_pares_tipo_skill(valor):
    """Texto de job_type_skills -> tupla de pares (tipo, skill), sin repetidos."""
    diccionario = leer_diccionario_crudo(valor) or {}
    pares = []
    for tipo, skills in diccionario.items():
        if isinstance(skills, str):
            skills = [skills]
        for skill in skills:
            tipo_limpio, skill_limpio = str(tipo).strip().lower(), str(skill).strip().lower()
            if tipo_limpio and skill_limpio:
                pares.append((tipo_limpio, skill_limpio))
    return tuple(dict.fromkeys(pares))


def unificar_empresas(empresas):
    """Una misma empresa escrita con otra capitalización queda con un solo nombre.

    Ejemplo: 'BOEING' y 'Boeing' -> el nombre que más se repite. Si empatan, se prefiere
    el que no está todo en mayúsculas. No se comparan nombres parecidos, solo iguales
    sin importar mayúsculas, para no mezclar empresas distintas.
    """
    conteo = empresas.value_counts()
    tabla = pd.DataFrame({"nombre": conteo.index, "veces": conteo.values})
    tabla["clave"] = tabla["nombre"].str.casefold()
    tabla["todo_mayuscula"] = tabla["nombre"].str.isupper()
    tabla = tabla.sort_values(["veces", "todo_mayuscula", "nombre"], ascending=[False, True, True])
    elegido = tabla.drop_duplicates("clave")
    return empresas.str.casefold().map(dict(zip(elegido["clave"], elegido["nombre"])))
