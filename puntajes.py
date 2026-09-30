"""
puntajes.py
===========
Persistencia de los mejores puntajes en un archivo JSON.

El archivo se guarda junto al codigo (equivalente al directorio
donde se ejecuta el script), asi no depende de la ruta actual.
"""

import json
import os

MAX_RECORDS = 5


def _ruta_archivo():
    directorio_script = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(directorio_script, "puntajes.json")


def cargar_puntajes():
    """Devuelve la lista de mejores puntajes (dicts {puntaje, nivel, fecha})."""
    try:
        with open(_ruta_archivo(), "r", encoding="utf-8") as archivo:
            datos = json.load(archivo)
        if isinstance(datos, list):
            return [d for d in datos if isinstance(d, dict) and "puntaje" in d]
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        pass
    return []


def guardar_puntaje(puntaje, nivel, fecha):
    """Registra un puntaje si entra en el top N. Se ignoran los puntajes de 0."""
    if int(puntaje) <= 0:
        return cargar_puntajes()

    registros = cargar_puntajes()
    registros.append({"puntaje": int(puntaje), "nivel": int(nivel), "fecha": str(fecha)})
    registros.sort(key=lambda r: r["puntaje"], reverse=True)
    registros = registros[:MAX_RECORDS]

    try:
        with open(_ruta_archivo(), "w", encoding="utf-8") as archivo:
            json.dump(registros, archivo, ensure_ascii=False, indent=2)
    except OSError:
        pass

    return registros


def mejor_puntaje():
    """Devuelve el puntaje mas alto registrado (0 si no hay ninguno)."""
    registros = cargar_puntajes()
    return registros[0]["puntaje"] if registros else 0