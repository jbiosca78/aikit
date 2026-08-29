# Configuración

Cada integración mantiene su propio `aikit.yaml` y lo indica mediante la variable de entorno
`AIKIT_CONFIG`. El fichero de la raíz del repositorio documenta todas las opciones y sirve como
referencia comentada.

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

Selecciona el proveedor de modelo y sus parámetros.

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

`params` se entrega tal cual a la función `init()` del conector, por lo que sus claves dependen
del proveedor. El bloque `prompt` admite una cadena o una lista de líneas, que se concatenan; al
residir en la configuración, el comportamiento del asistente puede ajustarse sin tocar código.

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

Determina cómo se identifica al usuario, lo que permite aislar los historiales. El parámetro
`method` selecciona un único mecanismo.

```yaml
auth:
  method: cookie       # proxy | jwt | cookie
  allow_anonymous: true
  anonymous_principal: "anon"
```

Con `allow_anonymous: false`, las peticiones sin identidad reciben un error 401.

**`method: proxy`**. Un intermediario externo autentica al usuario e inyecta su identidad en una
cabecera. AiKit se limita a leerla.

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
sesión anónima firmada, cuyo identificador el cliente no puede falsificar.

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

`context_messages` determina cuántos mensajes recientes se envían como contexto en cada petición.
Aumentarlo mejora la continuidad de la conversación y encarece cada llamada al modelo.

### rewrites

Reescrituras opcionales del mensaje de entrada mediante expresiones regulares, útiles para
normalizar formas de expresión frecuentes antes de enviarlas al modelo.

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
