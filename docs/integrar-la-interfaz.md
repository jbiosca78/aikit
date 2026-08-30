# Integrar la interfaz conversacional

AiKit trae dos formas de hablar con el núcleo: un chat flotante para webs y un cliente de
terminal. Los dos usan la misma API, así que el backend no queda atado a una interfaz concreta.

## Chat web

El componente está en `aikit/ui/chat-popup/` y se compone de dos ficheros: `chat-popup.js` para
la lógica y `chat-popup.css` para los estilos. No tiene dependencias, así que puede usarse en una
página estática, una plantilla de servidor o una aplicación montada con otro marco.

### Integración mínima

Se copian ambos ficheros al directorio público de la aplicación y se enlazan en la página:

```html
<link rel="stylesheet" href="chat-popup.css" />
...
<script src="chat-popup.js" data-api-url="http://localhost:8000/chat"></script>
```

Con eso aparece el botón flotante y el asistente queda listo. Si la aplicación usa una plantilla
común, normalmente basta con añadirlo una sola vez.

## Opciones

El componente se configura mediante atributos `data-` en la propia etiqueta `<script>`, sin
modificar su código:

| Atributo | Valor por defecto | Descripción |
|---|---|---|
| `data-api-url` | `http://localhost:8000/chat` | Dirección del punto de acceso de conversación |
| `data-title` | `Chat IA` | Título de la ventana del asistente |
| `data-placeholder` | `¿En qué puedo ayudarte?` | Texto de ayuda del campo de entrada |
| `data-initial-text` | Mensaje genérico de bienvenida | Primer mensaje que ve el visitante |
| `data-storage-key` | `aikit-chat-popup-v1` | Clave de almacenamiento local de la conversación |

Conviene personalizar `data-storage-key` con un valor propio de cada aplicación, para que dos
proyectos servidos desde el mismo dominio no compartan el historial del navegador.

## Configuración desde un fichero aparte

Cuando hay varias opciones, suele ser más cómodo meterlas en un guion propio que inserte el
componente. Ese es el enfoque que sigue el ejemplo `armarios-mario`, en su fichero
`chat-ia.js`:

```javascript
(function () {
    const CONFIG = {
        apiUrl:      'http://localhost:8000/chat',
        storageKey:  'mi-proyecto-v1',
        title:       'Asistente',
        placeholder: 'Pregunta por precios, plazos...',
        initialText: 'Te ayudo a encontrar lo que buscas.',
    };

    const s = document.createElement('script');
    s.src = 'chat-popup.js';
    s.dataset.apiUrl      = CONFIG.apiUrl;
    s.dataset.storageKey  = CONFIG.storageKey;
    s.dataset.title       = CONFIG.title;
    s.dataset.placeholder = CONFIG.placeholder;
    s.dataset.initialText = CONFIG.initialText;
    document.body.appendChild(s);
})();
```

De este modo la página solo enlaza `chat-ia.js` y toda la personalización queda en un único
lugar. Ese mismo guion puede añadir un enlace en la navegación del sitio para abrir el
asistente, como hace el ejemplo.

## Comportamiento

El componente guarda la conversación en el almacenamiento local del navegador, así que no se
pierde al recargar o cambiar de página. Al abrirse por primera vez pide una sesión a
`POST /session` y envía ese identificador en cada mensaje. Con eso el núcleo puede mantener un
historial separado por visitante.

Si el servidor no responde, el componente muestra el error en la conversación en lugar de
fallar en silencio.

## Sesiones y dominios

Cuando la web y el núcleo se sirven desde el mismo dominio, la sesión viaja en una cookie
`HttpOnly`, que no es accesible desde JavaScript. Si están en dominios u orígenes distintos, el
componente recurre a la cabecera `x-session-token`, ya que las cookies entre orígenes requieren
HTTPS y una configuración específica de CORS. Ambos mecanismos se controlan desde la sección
`auth` de la configuración, descrita en [Configuración](configuracion.md).

## Personalización visual

Los estilos residen en `chat-popup.css` y usan nombres de clase con el prefijo `chat-`. Al
tratarse de código copiado al proyecto, puede modificarse libremente para adaptarlo a la
identidad visual de la aplicación sin afectar a su funcionamiento.

## Cliente de terminal

`aikit/ui/shell/aikit-shell` es un cliente de línea de órdenes escrito en Python, sin
dependencias externas. Está pensado para casos técnicos, donde la persona ya está trabajando en
una terminal y abrir una interfaz web sería más molestia que ayuda.

```bash
export AIKIT_URL=http://localhost:8000
aikit-shell                                   # sesión interactiva
aikit-shell "cómo listo los puertos abiertos?"
journalctl -u nginx | aikit-shell "resume los errores"
```

Admite tres modos de entrada: interactivo, consulta puntual como argumento y análisis de la
salida recibida por la entrada estándar, lo que permite encadenarlo con cualquier orden
mediante una tubería. La conversación se conserva entre invocaciones.

Cuando la respuesta contiene órdenes delimitadas en bloques de código, el cliente las extrae,
las muestra resaltadas y las guarda en `~/.config/aikit/ultimo-comando`. Con la opción `-c` las
copia al portapapeles. **Nunca las ejecuta**: la decisión corresponde siempre al usuario. Para
que el modelo devuelva las órdenes en ese formato, conviene indicarlo en el prompt de sistema,
como hace el ejemplo `sysadmin`.

| Variable de entorno | Descripción |
|---|---|
| `AIKIT_URL` | Dirección del núcleo, por defecto `http://localhost:8000` |
| `AIKIT_SHELL_STATE` | Ruta del fichero de estado de la conversación |

## Otros clientes

Dado que el núcleo expone su funcionalidad mediante una API, cualquier cliente capaz de
realizar peticiones HTTP puede actuar como interfaz: una aplicación de escritorio, un proceso
en un dispositivo empotrado o un asistente de voz. La secuencia es siempre la misma: solicitar
una sesión a `POST /session`, si procede, y enviar los mensajes a `POST /chat` conservando el
mismo `conversation_id`.
