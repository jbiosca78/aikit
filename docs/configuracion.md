# Configuración

Cada integración tiene su propio `aikit.yaml`. AiKit sabe cuál debe usar mediante la variable de
entorno `AIKIT_CONFIG`. El fichero de la raíz del repositorio funciona como referencia comentada:
no hace falta usarlo tal cual, pero viene bien para ver todas las opciones disponibles.

```bash
export AIKIT_CONFIG=/ruta/a/mi-proyecto/aikit.yaml
uvicorn aikit.core.main:app --port 8000
```

## Secciones

### log

```yaml
log:
  level: INFO          # DEBUG, INFO, WARNING, ERROR, CRITICAL
  output: stdout       # "stdout" o una ruta de fichero
```

El nivel `DEBUG` registra las invocaciones de herramientas con sus argumentos, lo que resulta
útil para comprobar qué está decidiendo el modelo.

### engine

Aquí se elige qué motor de IA se va a usar y con qué parámetros.

```yaml
engine:
  module: bedrock      # fichero de aikit/engine/ sin extensión
  params:
    aws_profile: aikit
    model: eu.amazon.nova-lite-v1:0
  prompt:
    - "Responde de forma breve y directa."
    - "No menciones herramientas ni pasos internos."
```

`params` se pasa tal cual a la función `init()` del conector, así que sus claves dependen del
proveedor. El bloque `prompt` puede ser una cadena o una lista de líneas, que AiKit une al
arrancar. Al estar en configuración, puedes ajustar el comportamiento del asistente sin tocar
código.

Cambiar de proveedor consiste en modificar `module` y `params`.

### services

Lista de servicios de dominio que se cargan al arrancar.

```yaml
services:
  - name: horarios
  - name: catalogo
    module: mi_paquete.catalogo
    class: CatalogoService
```

Por convención, `name` determina el módulo `services.<name>` y la clase `Service`. Véase
[Crear un servicio de dominio](crear-un-servicio.md).

### auth

Define cómo se identifica al usuario para poder separar historiales. El parámetro `method`
elige un único mecanismo.

```yaml
auth:
  method: cookie       # proxy | jwt | cookie
  allow_anonymous: true
  anonymous_principal: "anon"
```

Con `allow_anonymous: false`, las peticiones sin identidad reciben un error 401.

**`method: proxy`**. Un proxy o servidor externo autentica al usuario y añade su identidad en
una cabecera. AiKit solo la lee.

```yaml
  proxy:
    userid_header: "x-user-id"
```

El proxy debe eliminar esa cabecera si llega del cliente, y el servicio no debe ser accesible sin
pasar por él.

**`method: jwt`**. Se valida la firma HS256 del testigo recibido en `Authorization: Bearer`,
junto con su vigencia y, opcionalmente, emisor y audiencia.

```yaml
  jwt:
    secret_env: "AIKIT_JWT_SECRET"
    claim_name: "sub"
    issuer: ""
    audience: ""
```

**`method: cookie`**. No hay identidad externa: el propio núcleo emite en `POST /session` una
sesión anónima firmada. El cliente conserva el identificador, pero no puede inventarse uno válido.

```yaml
  cookie:
    cookie_name: "aikit_session"
    token_header: "x-session-token"
    secret_env: "AIKIT_SESSION_SECRET"
    max_age_seconds: 86400
    samesite: "strict"   # "none" si la web y el core están en dominios distintos
    secure: false        # true en producción, con HTTPS
```

Este modo identifica, pero no autentica: distingue visitantes y mantiene la continuidad de su
conversación, sin acreditar una identidad real. No debe emplearse para dar acceso a datos
personales.

Las claves se resuelven desde la variable de entorno indicada en `secret_env`. Existe una clave
`secret` alternativa para demostraciones, que solo se usa si la variable no está definida.

### history

```yaml
history:
  enabled: true
  backend: json                       # memory | json
  path: "history.json"                # solo con backend json
  max_messages_per_conversation: 200
  context_messages: 12
```

`context_messages` indica cuántos mensajes recientes se reenvían como contexto en cada petición.
Subirlo puede mejorar la continuidad de la conversación, pero también aumenta el coste de cada
llamada al modelo.

### rewrites

Permite reescribir mensajes de entrada con expresiones regulares antes de mandarlos al modelo.
Es útil para atajos, comandos frecuentes o formas de hablar que quieras normalizar.

```yaml
rewrites:
  - name: saludo_simple
    pattern: '^\s*(hola|buenas)\s*$'
    replacement: 'Hola, ¿en qué puedo ayudarte?'
    flags: IGNORECASE
    count: 1
```

## Variables de entorno

| Variable | Uso |
|---|---|
| `AIKIT_CONFIG` | Ruta del fichero de configuración a utilizar |
| `AIKIT_SESSION_SECRET` | Clave de firma de las sesiones, en el modo `cookie` |
| `AIKIT_JWT_SECRET` | Clave de verificación de testigos, en el modo `jwt` |
| `AIKIT_CORS_ORIGINS` | Orígenes permitidos por CORS, separados por comas. Por defecto `*` |
| `AIKIT_CORS_ALLOW_CREDENTIALS` | Permite credenciales CORS cuando los orígenes son explícitos. Por defecto `true` |
| `AIKIT_TRACEBACK_SHOW_LOCALS` | Muestra variables locales en trazas de error si vale `1`, `true` o `yes` |

Si `AIKIT_CORS_ORIGINS` queda como `*`, AiKit desactiva `allow_credentials` aunque la variable
`AIKIT_CORS_ALLOW_CREDENTIALS` esté activa. Para usar cookies entre orígenes, declara el origen
concreto, por ejemplo `https://mi-web.example`.
