# Problemas frecuentes

Recopilación de los errores más habituales al poner en marcha o extender AiKit, con su causa y
su solución.

## El proceso no arranca

**`FileNotFoundError` al leer el fichero de configuración.** El núcleo busca el `aikit.yaml` de
la raíz del repositorio salvo que se indique otro mediante `AIKIT_CONFIG`. Al arrancar una
integración propia hay que exportar esa variable con la ruta absoluta de su fichero.

**`ModuleNotFoundError: No module named 'aikit'`.** El directorio raíz del repositorio no está en
la ruta de búsqueda de Python. Los guiones de arranque de los ejemplos lo añaden a `PYTHONPATH`;
si se lanza `uvicorn` a mano, hay que hacerlo también.

**`RuntimeError: No se encontró la clase Service`.** El módulo del servicio existe, pero no
define una clase con ese nombre, o tiene otro nombre y no se ha declarado `class` en la
configuración.

**`Engine contract violation`.** El conector de motor indicado no expone las funciones `init` y
`chat`. Véase [Crear un conector de motor](crear-un-motor.md).

## El servicio no se carga

Si un servicio no aparece en la respuesta de `GET /readiness`, conviene revisar en este orden:

1. Que esté declarado en la sección `services` de la configuración en uso, que puede no ser la
   que se está editando si `AIKIT_CONFIG` apunta a otra.
2. Que el módulo sea localizable: por convención, `name: pedidos` busca `services.pedidos`, y el
   directorio que contiene `services/` debe estar en `PYTHONPATH`.
3. Que la clase herede de `ServiceContract` e implemente `list_methods()`.

Los registros de arranque incluyen una línea por cada servicio cargado correctamente.

## El asistente no usa la herramienta

Es el problema más frecuente al añadir un servicio, y casi nunca se debe a un fallo técnico:
el modelo decide qué herramienta invocar a partir de las descripciones.

- Revisar el campo `description` del método. Debe indicar **cuándo** usarlo, no solo qué hace.
  Una descripción como "Devuelve el horario. Úsalo cuando pregunten a qué hora abre la tienda"
  funciona mejor que "Devuelve el horario".
- Revisar la descripción de los parámetros, sobre todo si tienen un formato concreto, como un
  día en minúsculas o una referencia con prefijo.
- Activar el nivel `DEBUG` en la sección `log`: los registros muestran qué herramientas se
  ofrecieron al modelo y cuál solicitó, con sus argumentos.
- Comprobar en `GET /readiness` que el número de herramientas publicadas es el esperado.
- Si conviven muchas herramientas con propósitos parecidos, el modelo puede confundirlas.
  Conviene que sus descripciones marquen claramente la diferencia.

## El asistente inventa datos

Suele ocurrir cuando el servicio devuelve una lista vacía sin contexto y el modelo rellena el
hueco. Devolver una respuesta explícita, del tipo `{"encontrado": false}`, permite al modelo
explicar la ausencia del dato. Añadir al prompt de sistema una instrucción de no inventar
información refuerza ese comportamiento.

## La conversación no mantiene el contexto

Si el asistente olvida lo anterior, revisar que `history.enabled` esté activado y que
`context_messages` no sea demasiado bajo. Conviene comprobar también que el cliente envía
siempre el mismo `conversation_id`: si genera uno nuevo en cada petición, cada mensaje se trata
como una conversación distinta.

## Todos los usuarios comparten la conversación

Con `auth.method: cookie` y `allow_anonymous: true`, un cliente que no solicite sesión se
resuelve como el principal anónimo, que es común a todos. El componente de interfaz pide la
sesión automáticamente; en integraciones propias hay que invocar `POST /session` y enviar el
identificador recibido.

## Las sesiones se pierden al reiniciar

Los guiones de arranque de los ejemplos generan una clave de firma aleatoria si no existe la
variable de entorno correspondiente, de modo que al reiniciar dejan de validar las sesiones
anteriores. En un despliegue real, la clave debe ser fija y provenir del entorno.

## Errores de credenciales del proveedor

Con Amazon Bedrock, los fallos de firma o de región suelen deberse al perfil de AWS indicado en
`engine.params` o a que el modelo no está habilitado en esa región. Con Ollama, conviene
comprobar que el servicio está en marcha y que el modelo se ha descargado previamente.
