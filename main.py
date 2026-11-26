"""EcoTech Solutions - Clima y pagos internacionales para proyectos (Unidad 3)."""
import getpass
import logging
import time
from pathlib import Path

import almacenamiento
import clima
import divisas
import seguridad
from http_cliente import ErrorServicio
from seguridad import sesion

# Los errores técnicos van a un archivo (sin datos sensibles); al usuario solo se le muestran mensajes controlados.
logging.basicConfig(
    filename=Path(__file__).with_name("errores.log"),
    level=logging.WARNING,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("main")


# ------------------------------------------------------------------ autenticación
def registrar():
    print("\n--- Registro de usuario ---")
    try:
        usuario = input("Usuario: ")
        password = getpass.getpass("Contraseña: ")
        if password != getpass.getpass("Repite la contraseña: "):
            print("Las contraseñas no coinciden.")
            return
        seguridad.registrar_usuario(usuario, password)
        print("Usuario registrado correctamente. Ya puedes iniciar sesión.")
    except ValueError as e:
        print(f"Error: {e}")


def iniciar_sesion():
    print("\n--- Inicio de sesión ---")
    for intento in range(1, seguridad.MAX_INTENTOS_LOGIN + 1):
        usuario = input("Usuario: ").strip()
        password = getpass.getpass("Contraseña: ")
        if not usuario or not password:
            print("Usuario y contraseña son obligatorios.")
        elif seguridad.autenticar(usuario, password):
            sesion.iniciar(usuario)
            print(f"Bienvenido, {usuario}.")
            return
        else:
            print("Credenciales incorrectas.")  # no se indica cuál de las dos falló
        if intento < seguridad.MAX_INTENTOS_LOGIN:
            time.sleep(intento)  # retardo creciente contra fuerza bruta
    print("Demasiados intentos fallidos. Volviendo al menú.")
    logger.warning("Login bloqueado tras %d intentos", seguridad.MAX_INTENTOS_LOGIN)


# ------------------------------------------------------------------ funciones protegidas
def consultar_clima():
    ciudad = input("Ciudad (ej: Santiago o Santiago, Chile): ")
    try:
        datos = clima.obtener_clima(ciudad)
    except ValueError as e:        # entrada inválida
        print(f"Entrada inválida: {e}")
        return
    except ErrorServicio as e:     # fallo del servicio externo (mensaje ya es seguro)
        print(f"No se pudo obtener el clima: {e}")
        return

    print(f"\n{datos['ciudad']}, {datos['region']}, {datos['pais']} ({datos['hora_local']})")
    print(f"  Estado:        {datos['condicion']}")
    print(f"  Temperatura:   {datos['temperatura_c']} °C (sensación {datos['sensacion_c']} °C)")
    print(f"  Humedad:       {datos['humedad']} %")
    print(f"  Viento:        {datos['viento_kph']} km/h")
    print(f"  Precipitación: {datos['precipitacion_mm']} mm")
    print(f"  >> Operación en terreno: {datos['nivel']} - {datos['recomendacion']}")

    if not almacenamiento.guardar_consulta(sesion.usuario, "clima", datos):
        print("(Aviso: no se pudo guardar la consulta en el historial local.)")


def calcular_pago_internacional():
    print("\n(El pago base se expresa en USD; la moneda destino es la del país del proyecto.)")
    monto = input("Monto del pago en USD (ej: 1500.50): ")
    moneda = input("Moneda destino (ej: CLP, PEN, EUR, BRL): ")
    try:
        datos = divisas.calcular_pago(monto, moneda)
    except ValueError as e:        # entrada inválida
        print(f"Entrada inválida: {e}")
        return
    except ErrorServicio as e:     # fallo del servicio externo (mensaje ya es seguro)
        print(f"No se pudo calcular el pago: {e}")
        return

    print(f"\n  Tipo de cambio: 1 {datos['moneda_base']} = {datos['tasa']} {datos['moneda_destino']}")
    print(f"  Pago: {datos['monto_base']} {datos['moneda_base']} = "
          f"{datos['monto_convertido']} {datos['moneda_destino']}")
    print(f"  Tasa actualizada: {datos['fecha_tasa']}")

    if not almacenamiento.guardar_consulta(sesion.usuario, "pago", datos):
        print("(Aviso: no se pudo guardar la consulta en el historial local.)")


def ver_historial():
    registros = almacenamiento.leer_historial(sesion.usuario)
    if not registros:
        print("Aún no tienes consultas guardadas.")
        return
    print("\n--- Tus últimas consultas ---")
    for r in registros:
        try:
            if r.get("tipo") == "pago":
                print(f"{r['fecha']} | PAGO | {r['monto_base']} {r['moneda_base']} -> "
                      f"{r['monto_convertido']} {r['moneda_destino']}")
            else:
                print(f"{r['fecha']} | CLIMA | {r['ciudad']}, {r['pais']} | {r['temperatura_c']} °C | "
                      f"{r['condicion']} | {r['nivel']}")
        except KeyError:
            continue  # registro incompleto: se omite en vez de detener el programa


# ------------------------------------------------------------------ menús
def menu_principal():
    while sesion.activa:
        print("\n=== EcoTech Solutions - Clima y pagos ===")
        print("1. Consultar clima de una ciudad")
        print("2. Calcular pago internacional (tipo de cambio)")
        print("3. Ver mi historial")
        print("4. Cerrar sesión")
        opcion = input("Opción: ").strip()
        try:
            if opcion == "1":
                consultar_clima()
            elif opcion == "2":
                calcular_pago_internacional()
            elif opcion == "3":
                ver_historial()
            elif opcion == "4":
                sesion.cerrar()
                print("Sesión cerrada.")
            else:
                print("Opción no válida.")
        except PermissionError as e:
            print(e)
            sesion.cerrar()


def menu_acceso():
    while True:
        print("\n=== Acceso ===")
        print("1. Iniciar sesión")
        print("2. Registrarse")
        print("0. Salir")
        opcion = input("Opción: ").strip()
        if opcion == "1":
            iniciar_sesion()
            if sesion.activa:
                menu_principal()
        elif opcion == "2":
            registrar()
        elif opcion == "0":
            print("Hasta luego.")
            return
        else:
            print("Opción no válida.")


def main():
    try:
        menu_acceso()
    except (KeyboardInterrupt, EOFError):
        print("\nPrograma finalizado por el usuario.")
    except Exception as e:
        # Última barrera: se registra solo el tipo de error y se muestra un mensaje genérico.
        logger.error("Error no controlado: %s", type(e).__name__)
        print("Ocurrió un error inesperado. El programa se cerrará de forma segura.")


if __name__ == "__main__":
    main()
