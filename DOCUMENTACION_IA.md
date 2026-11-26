# Documentación del uso de herramientas de IA (Criterio 3.1.4)

> Herramienta utilizada: Claude (Anthropic), como apoyo de codificación.
> Prompt principal: *"Termina el código siguiendo la pauta de la guía de la Unidad 3 (consumo de API de
> clima, autenticación con credenciales cifradas, validación de entradas, manejo de errores y uso de IA)"*,
> adjuntando la guía y mi `main.py` inicial.

## 1. Código de partida (`main.py` original) y análisis

```python
api_url = "https://api.weatherapi.com/current.json"
api_key = f"?key={ os.getenv("weather_api_token")}"
ciudad = "&q=santiago"
try:
    res = requests.get(api_url+api_key+ciudad, timeout=10)
    data = res.json
    print(data)
except requests.exceptions.Timeout:
    print("timeout")
```

### Errores y vulnerabilidades identificados

| # | Problema | Riesgo / efecto | Categoría |
|---|---|---|---|
| 1 | La URL no incluye `/v1/` | La API responde 404; el programa nunca obtiene datos | Funcional |
| 2 | `res.json` sin paréntesis | Se imprime el método, no el contenido JSON | Funcional |
| 3 | La API key se concatena a mano en la URL (`?key=...`) | Si ocurre un error, el texto de la excepción puede incluir la URL con la key y filtrarla | Datos sensibles |
| 4 | Si falta la variable de entorno, se envía `key=None` | Error confuso y petición inútil | Validación |
| 5 | No se revisa `status_code` | Respuestas 400/401/403/500 se tratan como éxito | Manejo de errores |
| 6 | Solo se captura `Timeout` | `ConnectionError`, JSON inválido u otros errores cierran el programa | Manejo de errores |
| 7 | La ciudad está fija y sin validar | Al hacerla variable, permite inyectar parámetros (`Santiago&key=...`) | Validación |
| 8 | No hay autenticación | Cualquiera ejecuta consultas que gastan cuota de la API | Autenticación |
| 9 | f-string con comillas dobles anidadas | `SyntaxError` en Python < 3.12 | Compatibilidad |
| 10 | No hay persistencia ni uso de los datos | No se integra al sistema | Funcional |

## 2. Código generado por la IA: qué se usó, qué se modificó y qué se descartó

| Decisión | Detalle | Justificación técnica |
|---|---|---|
| **Usado** | `requests.get(API_URL, params=..., timeout=(5, 10))` | `params` codifica los valores y evita concatenar la key a mano; timeout de conexión y lectura separados evita bloqueos |
| **Usado** | `hashlib.pbkdf2_hmac` (SHA-256, salt por usuario, 600 000 iteraciones) + `hmac.compare_digest` | Es de la librería estándar, lento a propósito frente a fuerza bruta, y la comparación en tiempo constante evita ataques de temporización |
| **Usado** | Validación por lista blanca con expresiones regulares | Es más seguro permitir solo lo conocido que intentar bloquear caracteres peligrosos |
| **Usado** | Decorador `@requiere_autenticacion` | Centraliza el control de acceso: no depende de que cada menú "se acuerde" de verificar |
| **Modificado** | La IA propuso reintentar ante cualquier error | Se limitó a fallos transitorios (timeout, conexión, 5xx). Un 400/401/403 no se arregla reintentando y gastaría cuota |
| **Modificado** | Mensajes de error con `str(e)` | Se reemplazó por mensajes controlados (`ErrorClima`) y en el log solo se guarda `type(e).__name__`, porque el texto de la excepción de `requests` puede contener la URL con la API key |
| **Modificado** | El mensaje de login indicaba "usuario no existe" / "contraseña incorrecta" | Se unificó en "Credenciales incorrectas" y se hace un hash falso si el usuario no existe, para evitar enumeración de usuarios |
| **Modificado** | Escritura directa de `usuarios.json` | Se cambió a escritura atómica (archivo temporal + `os.replace`) para no dejar el archivo corrupto si el programa se corta |
| **Usado** | Un único cliente HTTP (`http_cliente.py`) para ambas APIs | La IA había duplicado la lógica de reintentos y errores en clima y divisas; unificarla evita inconsistencias y deja un solo lugar que revisar |
| **Modificado** | La IA usó `float` para calcular el pago | Se cambió a `Decimal` con redondeo a 2 decimales: `float` acumula errores binarios y en dinero eso es inaceptable |
| **Modificado** | La IA aceptaba cualquier texto como monto (`float(input())`) | `float("nan")` y `float("inf")` son válidos en Python y romperían el cálculo; se validó con regex (solo dígitos y hasta 2 decimales, positivo) antes de convertir a `Decimal` |
| **Modificado** | La IA propuso la API Frankfurter para divisas | Se descartó porque usa tasas del BCE y no incluye CLP ni PEN; se usó open.er-api.com, que sí las trae y no requiere key |
| **Modificado** | La IA consultaba la API de tasas en cada cálculo | Se agregó caché de 1 hora: las tasas cambian una vez al día y así se evita exceder el límite de solicitudes (HTTP 429) |
| **Usado** | `oracledb` (librería oficial de Oracle) con credenciales en `.env` | Las credenciales de la base no se escriben en el código ni se suben a git |
| **Modificado** | La IA armó el `INSERT` con f-strings | Se cambió a variables bind (`:ciudad`, `:usuario`...): concatenar valores al SQL permite inyección SQL |
| **Modificado** | La IA dejaba que el programa fallara si Oracle no respondía | Se agregó respaldo automático a JSON y registro del error solo con su código, porque el mensaje de Oracle puede incluir host o usuario |
| **Descartado** | Guardar las contraseñas de los usuarios del sistema en Oracle sin hash | Se mantiene el hash PBKDF2 con salt; la base nunca almacena contraseñas en texto plano |
| **Descartado** | Guardar contraseñas con SHA-256 simple / Base64 | SHA-256 sin sal ni iteraciones es rápido de atacar; Base64 es codificación, no cifrado |
| **Descartado** | Instalar `bcrypt`/`passlib` | PBKDF2 está en la librería estándar y cumple el objetivo sin dependencias extra |
| **Descartado** | Guardar la API key en el código o en `usuarios.json` | Debe vivir en `.env` (ignorado por git), fuera del código fuente |

## 3. Vulnerabilidades revisadas en el código final

- **Inyección de parámetros en la consulta**: mitigada con validación de ciudad + `params=`.
- **Fuga de la API key**: no se imprime, no se registra y no va concatenada a la URL.
- **Contraseñas en texto plano**: no existen; solo se guarda `salt` y `hash`.
- **Fuerza bruta en el login**: máximo 3 intentos con retardo creciente.
- **Caída por fallos externos**: todas las rutas de error de la API terminan en un mensaje y el menú continúa.
- **Datos de la API inesperados**: se verifican tipos y rangos antes de usarlos.
- **Datos de divisas manipulados o inválidos**: se rechazan tasas no numéricas, negativas, cero o infinitas, y monedas inexistentes.
- **Aislamiento del historial**: cada usuario solo ve sus propias consultas.

### Limitaciones conocidas (mejoras futuras)
- El registro es abierto; en producción lo haría un administrador.
- El bloqueo por intentos fallidos vive en memoria (se reinicia al cerrar el programa).
- `usuarios.json` e historial no están cifrados en disco (las contraseñas sí están hasheadas).

## 4. Validación realizada

Se probaron con respuestas simuladas: ciudades válidas e inválidas (vacías, números, `;`, saltos de línea,
intentos de inyección de parámetros), contraseñas débiles, usuario duplicado, login correcto e incorrecto,
acceso sin sesión, códigos HTTP 200/400/401/403/404/429/418/500, reintentos ante 5xx y timeouts,
fallo de conexión, respuesta no JSON, campos faltantes, valores fuera de rango, API key ausente e
historial corrupto. Para divisas: monedas y montos inválidos (`NaN`, `Infinity`, negativos, `1e5`, 3 decimales),
tasas corruptas, caché y cálculo exacto con `Decimal`. También se simuló el flujo completo del menú
(registro, login, clima, pago, historial y cierre de sesión). En todos los casos el programa respondió con un mensaje controlado y sin exponer la API key.
