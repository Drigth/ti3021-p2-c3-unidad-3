"""Persistencia en Oracle Database con la librería oficial `oracledb`.

La conexión se configura en el archivo .env (nunca en el código):
    DB_USER=...
    DB_PASSWORD=...
    DB_DSN=host:puerto/servicio        (ej: tcps://db.freesql.com:2484/servicio)

Si las variables no existen, o Oracle no responde, el sistema sigue funcionando con el
archivo JSON local (ver almacenamiento.py).
"""
import logging
import os
from decimal import Decimal, InvalidOperation

import oracledb
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

_tablas_listas = False

_DDL = (
    """CREATE TABLE consultas_clima (
           id             NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
           fecha          TIMESTAMP DEFAULT SYSTIMESTAMP NOT NULL,
           usuario        VARCHAR2(20)  NOT NULL,
           ciudad         VARCHAR2(100) NOT NULL,
           pais           VARCHAR2(100),
           temperatura_c  NUMBER(5,2),
           humedad        NUMBER(3),
           condicion      VARCHAR2(100),
           nivel          VARCHAR2(20)
       )""",
    """CREATE TABLE pagos_internacionales (
           id                NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
           fecha             TIMESTAMP DEFAULT SYSTIMESTAMP NOT NULL,
           usuario           VARCHAR2(20) NOT NULL,
           moneda_destino    CHAR(3)      NOT NULL,
           monto_usd         NUMBER(14,2) NOT NULL,
           tasa              NUMBER(18,6) NOT NULL,
           monto_convertido  NUMBER(18,2) NOT NULL
       )""",
)


def disponible() -> bool:
    """True si hay credenciales de Oracle configuradas en el entorno."""
    return all(os.getenv(v, "").strip() for v in ("DB_USER", "DB_PASSWORD", "DB_DSN"))


def _conectar():
    return oracledb.connect(
        user=os.getenv("DB_USER").strip(),
        password=os.getenv("DB_PASSWORD"),
        dsn=os.getenv("DB_DSN").strip(),
        tcp_connect_timeout=5,
    )


def _codigo_error(e: Exception):
    try:
        return e.args[0].code
    except (AttributeError, IndexError):
        return None


def _crear_tablas(conn) -> None:
    """Crea las tablas si no existen (ORA-00955 = ya existe: se ignora)."""
    global _tablas_listas
    if _tablas_listas:
        return
    with conn.cursor() as cur:
        for ddl in _DDL:
            try:
                cur.execute(ddl)
            except oracledb.DatabaseError as e:
                if _codigo_error(e) != 955:
                    raise
    _tablas_listas = True


def _dec(valor) -> Decimal:
    try:
        return Decimal(str(valor))
    except InvalidOperation:
        raise ValueError("valor numérico inválido") from None


def guardar(usuario: str, tipo: str, datos: dict) -> bool:
    """Inserta la consulta. Devuelve False si no se pudo (el llamador usa el respaldo JSON)."""
    try:
        with _conectar() as conn:
            _crear_tablas(conn)
            with conn.cursor() as cur:
                # Siempre con variables bind (:nombre): nunca se concatenan valores al SQL (evita inyección SQL)
                if tipo == "clima":
                    cur.execute(
                        """INSERT INTO consultas_clima
                           (usuario, ciudad, pais, temperatura_c, humedad, condicion, nivel)
                           VALUES (:usuario, :ciudad, :pais, :temp, :humedad, :condicion, :nivel)""",
                        usuario=usuario, ciudad=datos["ciudad"], pais=datos["pais"],
                        temp=_dec(datos["temperatura_c"]), humedad=datos["humedad"],
                        condicion=datos["condicion"], nivel=datos["nivel"])
                else:
                    cur.execute(
                        """INSERT INTO pagos_internacionales
                           (usuario, moneda_destino, monto_usd, tasa, monto_convertido)
                           VALUES (:usuario, :moneda, :monto, :tasa, :convertido)""",
                        usuario=usuario, moneda=datos["moneda_destino"],
                        monto=_dec(datos["monto_base"]), tasa=_dec(datos["tasa"]),
                        convertido=_dec(datos["monto_convertido"]))
            conn.commit()
        return True
    except (oracledb.Error, KeyError, ValueError) as e:
        # Solo se registra el tipo/código: el mensaje de Oracle puede incluir host o usuario
        logger.error("Error al guardar en Oracle: %s (código %s)", type(e).__name__, _codigo_error(e))
        return False


def leer(usuario: str, limite: int = 10):
    """Últimas consultas del usuario, en el mismo formato que el JSON. None si Oracle falla."""
    try:
        with _conectar() as conn:
            _crear_tablas(conn)
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT fecha, 'clima' tipo, ciudad, pais, temperatura_c, condicion, nivel,
                              NULL monto, NULL moneda, NULL convertido
                         FROM consultas_clima WHERE usuario = :usuario
                       UNION ALL
                       SELECT fecha, 'pago', NULL, NULL, NULL, NULL, NULL,
                              monto_usd, moneda_destino, monto_convertido
                         FROM pagos_internacionales WHERE usuario = :usuario
                       ORDER BY 1 DESC FETCH FIRST :limite ROWS ONLY""",
                    usuario=usuario, limite=limite)
                filas = cur.fetchall()
        registros = []
        for f in reversed(filas):  # más antiguo primero, igual que el JSON
            fecha = f[0].isoformat(timespec="seconds")
            if f[1] == "clima":
                registros.append({"fecha": fecha, "tipo": "clima", "ciudad": f[2], "pais": f[3],
                                  "temperatura_c": float(f[4]), "condicion": f[5], "nivel": f[6]})
            else:
                registros.append({"fecha": fecha, "tipo": "pago", "monto_base": f"{f[7]:.2f}",
                                  "moneda_base": "USD", "moneda_destino": str(f[8]).strip(),
                                  "monto_convertido": f"{f[9]:.2f}"})
        return registros
    except (oracledb.Error, TypeError, ValueError) as e:
        logger.error("Error al leer de Oracle: %s (código %s)", type(e).__name__, _codigo_error(e))
        return None
