# EcoTech Solutions – Clima y pagos internacionales (Unidad 3)

Script en Python que consume dos APIs externas con `requests`:

- **WeatherAPI** (clima de cualquier ciudad del mundo) para planificar proyectos en terreno.
- **open.er-api.com** (tipo de cambio, sin key) para calcular pagos a trabajadores en la moneda del país del proyecto.

Incluye autenticación, validación de entradas, manejo de errores y persistencia local.

## Puesta en marcha

```bash
pip install -r requirements.txt
cp .env.example .env        # y pega tu API key en weather_api_token
python main.py
```

Requiere Python 3.10 o superior. La primera vez, usa la opción **Registrarse** para crear un usuario
(contraseña: mínimo 8 caracteres con mayúscula, minúscula y número).

**Ejemplo de uso:** clima → `Lima, Peru`; pago → monto `1500.50` en USD, moneda `CLP`.

## Base de datos Oracle (opcional)

Completa en el `.env` los datos de tu base (no van en el código):

```
DB_USER=tu_usuario
DB_PASSWORD=tu_contraseña
DB_DSN=tcps://db.freesql.com:2484/26ai_un3c1
```

Al guardar la primera consulta se crean solas las tablas `CONSULTAS_CLIMA` y `PAGOS_INTERNACIONALES`.
Si las variables no están, o Oracle no responde, el programa sigue funcionando y guarda en el JSON local.

## Estructura

| Archivo | Responsabilidad | Criterio |
|---|---|---|
| `main.py` | Menús, flujo de sesión y mensajes al usuario | 3.1.2 / 3.1.3 |
| `http_cliente.py` | Cliente HTTP compartido: timeout, reintentos, códigos HTTP, errores seguros | 3.1.1 / 3.1.3 |
| `clima.py` | API de clima: JSON, extracción de datos, recomendación operativa | 3.1.1 |
| `divisas.py` | API de tipo de cambio: conversión de pagos USD → moneda local con `Decimal` | 3.1.1 |
| `seguridad.py` | Hash de contraseñas (PBKDF2 + salt), validaciones, sesión y decorador de acceso | 3.1.2 |
| `almacenamiento.py` | Historial de consultas: Oracle si está configurado; si no, `historial_clima.json` | 3.1.1 |
| `bd_oracle.py` | Conexión a Oracle con `oracledb`, tablas automáticas y consultas con variables bind | 3.1.1 / 3.1.2 |
| `DOCUMENTACION_IA.md` | Uso de IA, vulnerabilidades detectadas y justificación de cambios | 3.1.4 |

## Seguridad en resumen

- Contraseñas guardadas solo como hash PBKDF2-HMAC-SHA256 con salt aleatorio (nunca en texto plano).
- Solo usuarios autenticados pueden consultar la API (decorador `@requiere_autenticacion`).
- API key en `.env` (ignorado por git), enviada con `params=` y nunca impresa ni registrada.
- Entradas validadas con listas blancas (usuario, contraseña, ciudad, moneda y monto).
- Mensajes de error genéricos al usuario; el detalle técnico mínimo va a `errores.log`.
