"""Seguridad: autenticación con contraseñas hasheadas y validación de entradas.

Solo usa la librería estándar de Python (hashlib, hmac, secrets, re, json).
"""
import hashlib
import hmac
import json
import os
import re
import secrets
import unicodedata
from decimal import Decimal
from functools import wraps
from pathlib import Path

RUTA_USUARIOS = Path(__file__).with_name("usuarios.json")

# PBKDF2-HMAC-SHA256: derivación de clave lenta, pensada para contraseñas.
# 600.000 iteraciones es el mínimo que recomienda OWASP para SHA-256.
ITERACIONES = 600_000
LARGO_SALT = 16
MAX_INTENTOS_LOGIN = 3

# --- Patrones de validación (lista blanca: solo se acepta lo explícitamente permitido) ---
_PATRON_USUARIO = re.compile(r"^[A-Za-z0-9_]{4,20}$")
# [^\W\d_] = cualquier letra Unicode (acepta tildes y ñ, rechaza números y símbolos)
_PALABRA = r"[^\W\d_]+(?:[.'\-][^\W\d_]+)*"
_NOMBRE_LUGAR = rf"{_PALABRA}(?: {_PALABRA})*"
_PATRON_CIUDAD = re.compile(rf"^{_NOMBRE_LUGAR}(?:, ?{_NOMBRE_LUGAR})?$")


# ---------------------------------------------------------------- hashing
def hashear_password(password: str, salt: bytes | None = None) -> tuple[str, str]:
    """Devuelve (salt_hex, hash_hex). Cada usuario tiene su propio salt aleatorio."""
    if salt is None:
        salt = secrets.token_bytes(LARGO_SALT)
    derivado = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, ITERACIONES)
    return salt.hex(), derivado.hex()


def _verificar_password(password: str, salt_hex: str, hash_hex: str) -> bool:
    _, calculado = hashear_password(password, bytes.fromhex(salt_hex))
    # compare_digest compara en tiempo constante (evita ataques de temporización)
    return hmac.compare_digest(calculado, hash_hex)


# ---------------------------------------------------------------- validaciones
def validar_usuario(username: str) -> str:
    username = (username or "").strip()
    if not username:
        raise ValueError("El usuario no puede estar vacío.")
    if not _PATRON_USUARIO.fullmatch(username):
        raise ValueError("Usuario inválido: 4 a 20 caracteres (letras, números o guion bajo).")
    return username


def validar_password_nueva(password: str) -> str:
    """Política de contraseña para REGISTRO (no se aplica al login)."""
    if not password:
        raise ValueError("La contraseña no puede estar vacía.")
    if len(password) < 8 or len(password) > 128:
        raise ValueError("La contraseña debe tener entre 8 y 128 caracteres.")
    if any(c.isspace() for c in password):
        raise ValueError("La contraseña no puede contener espacios.")
    if not (re.search(r"[a-z]", password) and re.search(r"[A-Z]", password)
            and re.search(r"\d", password)):
        raise ValueError("La contraseña debe incluir mayúscula, minúscula y número.")
    return password


def validar_ciudad(texto: str) -> str:
    """Valida y normaliza la ciudad (opcionalmente 'Ciudad, País') antes de enviarla a la API."""
    texto = unicodedata.normalize("NFC", (texto or "").strip())
    texto = re.sub(r"\s+", " ", texto)
    if not texto:
        raise ValueError("La ciudad no puede estar vacía.")
    if len(texto) < 2 or len(texto) > 60:
        raise ValueError("La ciudad debe tener entre 2 y 60 caracteres.")
    if not _PATRON_CIUDAD.fullmatch(texto):
        raise ValueError("Ciudad inválida: solo letras, espacios, guiones y apóstrofes "
                         "(formato opcional: Ciudad, País).")
    return texto


def validar_moneda(texto: str) -> str:
    """Código de moneda ISO 4217: exactamente 3 letras (USD, CLP, EUR...). Se normaliza a mayúsculas."""
    texto = (texto or "").strip().upper()
    if not texto:
        raise ValueError("La moneda no puede estar vacía.")
    if not re.fullmatch(r"[A-Z]{3}", texto):
        raise ValueError("Moneda inválida: usa el código de 3 letras (ej: CLP, EUR, PEN).")
    return texto


def validar_monto(texto: str) -> Decimal:
    """Monto positivo con hasta 2 decimales (acepta coma o punto). Devuelve Decimal, no float."""
    texto = (texto or "").strip().replace(",", ".")
    if not texto:
        raise ValueError("El monto no puede estar vacío.")
    # La regex descarta de entrada 'NaN', 'Infinity', notación científica y negativos
    if not re.fullmatch(r"\d{1,9}(\.\d{1,2})?", texto):
        raise ValueError("Monto inválido: número positivo con hasta 2 decimales (ej: 1500.50).")
    monto = Decimal(texto)
    if monto <= 0:
        raise ValueError("El monto debe ser mayor que cero.")
    return monto


# ---------------------------------------------------------------- persistencia de usuarios
def _cargar_usuarios() -> dict:
    try:
        with open(RUTA_USUARIOS, "r", encoding="utf-8") as f:
            datos = json.load(f)
        return datos if isinstance(datos, dict) else {}
    except FileNotFoundError:
        return {}
    except (json.JSONDecodeError, OSError):
        raise RuntimeError("No se pudo leer el archivo de usuarios.") from None


def _guardar_usuarios(usuarios: dict) -> None:
    tmp = RUTA_USUARIOS.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(usuarios, f, indent=2)
    try:
        os.chmod(tmp, 0o600)  # solo el dueño (no aplica en Windows, se ignora)
    except OSError:
        pass
    os.replace(tmp, RUTA_USUARIOS)  # escritura atómica: no deja el archivo a medias


def registrar_usuario(username: str, password: str) -> None:
    username = validar_usuario(username)
    validar_password_nueva(password)
    usuarios = _cargar_usuarios()
    if username.lower() in {u.lower() for u in usuarios}:
        raise ValueError("Ese nombre de usuario ya existe.")
    salt, hash_ = hashear_password(password)
    usuarios[username] = {"salt": salt, "hash": hash_, "iteraciones": ITERACIONES}
    _guardar_usuarios(usuarios)


def autenticar(username: str, password: str) -> bool:
    """True solo si usuario y contraseña son correctos. Nunca revela cuál de los dos falló."""
    username = (username or "").strip()
    if not username or not password:
        return False
    usuario = _cargar_usuarios().get(username)
    if usuario is None:
        # Hash "falso" para que tardar lo mismo exista o no el usuario
        _verificar_password(password, "00" * LARGO_SALT, "00" * 32)
        return False
    return _verificar_password(password, usuario["salt"], usuario["hash"])


def hay_usuarios() -> bool:
    return bool(_cargar_usuarios())


# ---------------------------------------------------------------- sesión y control de acceso
class Sesion:
    def __init__(self):
        self.usuario: str | None = None

    @property
    def activa(self) -> bool:
        return self.usuario is not None

    def iniciar(self, username: str) -> None:
        self.usuario = username

    def cerrar(self) -> None:
        self.usuario = None


sesion = Sesion()


def requiere_autenticacion(func):
    """Decorador: la función solo se ejecuta si hay un usuario autenticado."""
    @wraps(func)
    def envoltura(*args, **kwargs):
        if not sesion.activa:
            raise PermissionError("Debes iniciar sesión para usar esta función.")
        return func(*args, **kwargs)
    return envoltura
