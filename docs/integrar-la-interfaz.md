# Integrar la interfaz conversacional

AiKit incluye dos componentes de interfaz listos para usar: un chat flotante para aplicaciones
web y un cliente de terminal. Ambos consumen la misma API del núcleo, lo que ilustra que este
no está acoplado a un tipo de cliente concreto.

## Chat web

El componente vive en `aikit/ui/chat-popup/` y consta de dos ficheros: `chat-popup.js` con la
lógica y `chat-popup.css` con los estilos. Es JavaScript sin dependencias, por lo que funciona
con cualquier _frontend_: páginas estáticas, plantillas de servidor o aplicaciones construidas
con otro marco.

### Integración mínima

Se copian ambos ficheros al directorio público de la aplicación y se enlazan en la página:

```html
<link rel="stylesheet" href="chat-popup.css" />
...
<script src="chat-popup.js" data-api-url="http://localhost:8000/chat"></script>
```

Con eso aparece el botón flotante y el asistente queda operativo. Si la aplicación usa plantillas
o una disposición común, basta con declararlo una vez.

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

Cuando hay varias opciones, resulta más cómodo declararlas en un guion propio que inserte el
componente. Este es el enfoque que sigue el ejemplo `armarios-mario`, en su fichero
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

El componente conserva la conversación en el almacenamiento local del navegador, de modo que
sobrevive a la recarga y al cambio de página. Al abrirse por primera vez solicita una sesión
al punto de acceso `POST /session` y envía el identificador obtenido en cada petición, lo que
permite al núcleo mantener historiales separados por visitante.

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
dependencias externas. Está pensado para asistentes orientados a tareas técnicas, donde la
persona ya trabaja en una terminal y una interfaz web resultaría un estorbo.

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
