"""Consumo de la API de tipo de cambio https://open.er-api.com (gratuita, no requiere key)."""
import math
import time
from decimal import Decimal, ROUND_HALF_UP

import requests

from http_cliente import ErrorServicio, mensaje_http_generico, solicitar_json
from seguridad import requiere_autenticacion, validar_moneda, validar_monto

API_URL = "https://open.er-api.com/v6/latest/USD"
MONEDA_BASE = "USD"
CACHE_SEGUNDOS = 3600    # las tasas se actualizan 1 vez al día: se evita consultar de más

_cache: dict = {"momento": 0.0, "datos": None}


def _mensaje_http(resp: requests.Response) -> str | None:
    if resp.status_code == 404:
        return "El servicio de tipo de cambio no encontró la moneda solicitada."
    return mensaje_http_generico(resp.status_code)


def _obtener_tasas() -> dict:
    """Devuelve {'fecha': ..., 'rates': {...}} usando caché de 1 hora."""
    if _cache["datos"] is not None and time.monotonic() - _cache["momento"] < CACHE_SEGUNDOS:
        return _cache["datos"]

    data = solicitar_json(API_URL, None, _mensaje_http)
    try:
        if data["result"] != "success":
            raise ErrorServicio("El servicio de tipo de cambio no pudo procesar la consulta.")
        rates = data["rates"]
        if not isinstance(rates, dict):
            raise TypeError
        datos = {"fecha": str(data.get("time_last_update_utc", "")), "rates": rates}
    except (KeyError, TypeError):
        raise ErrorServicio("La respuesta del servicio no tiene el formato esperado.") from None

    _cache["momento"], _cache["datos"] = time.monotonic(), datos
    return datos


def _tasa_valida(rates: dict, moneda: str) -> Decimal:
    try:
        valor = float(rates[moneda])
    except KeyError:
        raise ErrorServicio(f"La moneda {moneda} no está disponible en el servicio.") from None
    except (TypeError, ValueError):
        raise ErrorServicio("La respuesta del servicio no tiene el formato esperado.") from None
    if not math.isfinite(valor) or valor <= 0:
        raise ErrorServicio("El servicio devolvió un tipo de cambio inválido.")
    return Decimal(str(valor))


@requiere_autenticacion
def calcular_pago(monto_usd_texto: str, moneda_texto: str) -> dict:
    """Convierte un pago en USD a la moneda del país donde se ejecuta el proyecto."""
    monto = validar_monto(monto_usd_texto)      # Decimal > 0
    moneda = validar_moneda(moneda_texto)       # 3 letras mayúsculas (ISO 4217)
    tasas = _obtener_tasas()
    tasa = _tasa_valida(tasas["rates"], moneda)
    # Decimal en vez de float: en dinero se evitan errores de redondeo binario
    convertido = (monto * tasa).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return {
        "moneda_base": MONEDA_BASE,
        "moneda_destino": moneda,
        "monto_base": str(monto),
        "tasa": str(tasa),
        "monto_convertido": str(convertido),
        "fecha_tasa": tasas["fecha"],
    }
