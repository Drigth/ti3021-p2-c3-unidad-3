"""Persistencia del historial de consultas.

Si hay una base Oracle configurada en el .env se usa Oracle (bd_oracle.py); si no está configurada
o falla, se usa un archivo JSON local como respaldo, de modo que el programa nunca se detiene.
"""
import json
import os
from datetime import datetime
from pathlib import Path

import bd_oracle

RUTA_HISTORIAL = Path(__file__).with_name("historial_clima.json")


def _leer_todo() -> list:
    try:
        with open(RUTA_HISTORIAL, "r", encoding="utf-8") as f:
            datos = json.load(f)
        return datos if isinstance(datos, list) else []
    except FileNotFoundError:
        return []
    except json.JSONDecodeError:
        # Archivo corrupto: se aparta para no perderlo y se parte de cero
        os.replace(RUTA_HISTORIAL, RUTA_HISTORIAL.with_suffix(".corrupto"))
        return []


def _guardar_json(usuario: str, tipo: str, datos: dict) -> bool:
    try:
        registros = _leer_todo()
        registros.append({
            "fecha": datetime.now().isoformat(timespec="seconds"),
            "usuario": usuario,
            "tipo": tipo,
            **datos,
        })
        tmp = RUTA_HISTORIAL.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(registros, f, ensure_ascii=False, indent=2)
        os.replace(tmp, RUTA_HISTORIAL)
        return True
    except OSError:
        return False


def guardar_consulta(usuario: str, tipo: str, datos: dict) -> bool:
    """Guarda una consulta ('clima' o 'pago'). Oracle primero; si no está o falla, JSON local.
    Devuelve False solo si ninguna de las dos opciones funcionó (no detiene el programa)."""
    if bd_oracle.disponible() and bd_oracle.guardar(usuario, tipo, datos):
        return True
    return _guardar_json(usuario, tipo, datos)


def leer_historial(usuario: str, limite: int = 10) -> list:
    """Últimas consultas del usuario (cada usuario solo ve las suyas)."""
    if bd_oracle.disponible():
        registros = bd_oracle.leer(usuario, limite)
        if registros is not None:
            return registros
    try:
        propios = [r for r in _leer_todo() if r.get("usuario") == usuario]
    except OSError:
        return []
    return propios[-limite:]
