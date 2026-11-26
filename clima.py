"""Consumo de WeatherAPI (https://www.weatherapi.com) con requests."""
import os

import requests
from dotenv import load_dotenv

from http_cliente import ErrorServicio, mensaje_http_generico, solicitar_json
from seguridad import requiere_autenticacion, validar_ciudad

load_dotenv()

API_URL = "https://api.weatherapi.com/v1/current.json"

ErrorClima = ErrorServicio  # alias: los mensajes de este error son seguros para el usuario


def _obtener_api_key() -> str:
    key = os.getenv("weather_api_token")
    if not key or not key.strip():
        raise ErrorClima("Falta configurar la API key. Revisa tu archivo .env (ver README).")
    return key.strip()


def _mensaje_http(resp: requests.Response) -> str | None:
    """Mensajes específicos de WeatherAPI para errores 4xx."""
    codigo_api = None
    try:
        codigo_api = resp.json().get("error", {}).get("code")  # WeatherAPI: {"error": {"code": ...}}
    except (ValueError, AttributeError):
        pass

    if resp.status_code == 400 and codigo_api == 1006:
        return "No se encontró esa ubicación. Revisa el nombre de la ciudad."
    if resp.status_code == 401:
        return "La API key es inválida o no fue enviada. Revisa tu archivo .env."
    if resp.status_code == 403:
        return "Acceso denegado por el servicio (cuota excedida o API key deshabilitada)."
    return mensaje_http_generico(resp.status_code)


def _solicitar(ciudad: str) -> dict:
    # La key viaja en `params` (requests la codifica); nunca se concatena a mano en la URL.
    params = {"key": _obtener_api_key(), "q": ciudad, "lang": "es"}
    return solicitar_json(API_URL, params, _mensaje_http)


def _extraer_datos(data: dict) -> dict:
    """Selecciona solo los campos útiles y verifica que sean utilizables."""
    try:
        loc, cur = data["location"], data["current"]
        datos = {
            "ciudad": str(loc["name"]),
            "region": str(loc.get("region", "")),
            "pais": str(loc["country"]),
            "hora_local": str(loc["localtime"]),
            "temperatura_c": float(cur["temp_c"]),
            "sensacion_c": float(cur["feelslike_c"]),
            "humedad": int(cur["humidity"]),
            "condicion": str(cur["condition"]["text"]),
            "viento_kph": float(cur["wind_kph"]),
            "precipitacion_mm": float(cur["precip_mm"]),
        }
    except (KeyError, TypeError, ValueError, AttributeError):
        raise ErrorClima("La respuesta del servicio no tiene el formato esperado.") from None

    if not (-90 <= datos["temperatura_c"] <= 60) or not (0 <= datos["humedad"] <= 100) \
            or datos["viento_kph"] < 0 or datos["precipitacion_mm"] < 0:
        raise ErrorClima("El servicio devolvió valores fuera de rango.")
    return datos


def evaluar_condiciones(d: dict) -> tuple[str, str]:
    """Recomendación operativa para proyectos en terreno según el clima actual."""
    if d["precipitacion_mm"] >= 5 or d["viento_kph"] >= 50:
        return "NO RECOMENDADO", "Lluvia fuerte o viento intenso: posponer trabajos en terreno."
    if d["temperatura_c"] >= 35 or d["temperatura_c"] <= 0:
        return "PRECAUCIÓN", "Temperatura extrema: limitar la exposición y planificar pausas."
    if d["precipitacion_mm"] > 0 or d["viento_kph"] >= 30 or d["humedad"] >= 90:
        return "PRECAUCIÓN", "Condiciones húmedas o ventosas: revisar equipos y vías de acceso."
    return "APTO", "Condiciones favorables para trabajos en terreno."


@requiere_autenticacion
def obtener_clima(ciudad_ingresada: str) -> dict:
    """Valida la entrada, consulta la API y devuelve datos + recomendación operativa."""
    ciudad = validar_ciudad(ciudad_ingresada)
    datos = _extraer_datos(_solicitar(ciudad))
    datos["nivel"], datos["recomendacion"] = evaluar_condiciones(datos)
    return datos
