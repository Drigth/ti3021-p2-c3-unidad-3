"""Cliente HTTP seguro y reutilizable para todas las APIs externas (clima y divisas)."""
import logging
import time

import requests

TIMEOUT = (5, 10)        # (segundos para conectar, segundos para leer la respuesta)
MAX_REINTENTOS = 2       # solo para fallos transitorios (timeout, conexión, 5xx)

logger = logging.getLogger(__name__)


class ErrorServicio(Exception):
    """Error controlado. Su mensaje es SEGURO de mostrar al usuario (sin key, URL ni trazas)."""


def mensaje_http_generico(estado: int) -> str:
    """Mensaje para códigos HTTP de error comunes, sin información sensible."""
    if estado == 400:
        return "La consulta fue rechazada por el servicio (parámetros inválidos)."
    if estado in (401, 403):
        return "Acceso denegado por el servicio externo."
    if estado == 404:
        return "El recurso solicitado no existe en el servicio."
    if estado == 429:
        return "Demasiadas solicitudes al servicio. Intenta nuevamente en unos minutos."
    return f"El servicio respondió con un error inesperado (HTTP {estado})."


def solicitar_json(url: str, params: dict | None = None, interpretar_error=None) -> dict:
    """GET con timeout, reintentos ante fallos transitorios y validación del código HTTP.

    interpretar_error: función opcional (respuesta) -> mensaje, para errores 4xx propios de cada API.
    Devuelve el JSON (dict). Cualquier fallo se traduce a ErrorServicio.
    """
    ultimo_error = "No se pudo contactar al servicio."

    for intento in range(MAX_REINTENTOS + 1):
        try:
            resp = requests.get(url, params=params, timeout=TIMEOUT)
        except requests.exceptions.Timeout:
            ultimo_error = "El servicio tardó demasiado en responder."
            logger.warning("Timeout al consultar un servicio externo (intento %d)", intento + 1)
        except requests.exceptions.ConnectionError:
            ultimo_error = "No hay conexión con el servicio. Revisa tu internet."
            logger.warning("Error de conexión con un servicio externo (intento %d)", intento + 1)
        except requests.exceptions.RequestException as e:
            # Solo se registra el TIPO de error: el texto de la excepción puede incluir la URL con la key.
            logger.error("Error de requests: %s", type(e).__name__)
            raise ErrorServicio("No se pudo completar la solicitud al servicio.") from None
        else:
            if resp.status_code == 200:
                try:
                    datos = resp.json()
                except ValueError:
                    logger.error("Respuesta 200 que no es JSON válido")
                    raise ErrorServicio("El servicio devolvió una respuesta ilegible.") from None
                if not isinstance(datos, dict):
                    raise ErrorServicio("El servicio devolvió una respuesta inesperada.")
                return datos
            if resp.status_code >= 500:
                ultimo_error = "El servicio externo presenta problemas en este momento."
                logger.warning("HTTP %d de un servicio externo (intento %d)", resp.status_code, intento + 1)
            else:
                logger.error("HTTP %d de un servicio externo", resp.status_code)
                mensaje = interpretar_error(resp) if interpretar_error else None
                raise ErrorServicio(mensaje or mensaje_http_generico(resp.status_code))  # 4xx: no se reintenta

        if intento < MAX_REINTENTOS:
            time.sleep(0.5 * 2 ** intento)  # espera 0.5 s, 1 s...

    raise ErrorServicio(ultimo_error)
