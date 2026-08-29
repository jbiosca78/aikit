# Crear un conector de motor

Un motor conecta el núcleo con un proveedor de modelo. Añadir soporte para uno nuevo consiste en
escribir un módulo en `aikit/engine/` que exponga dos funciones.

El punto de partida más cómodo es copiar `aikit/engine/template.py`, o el conector existente más
parecido al proveedor de destino.

## El contrato

```python
def init(**params) -> None:
    """Recibe el contenido de engine.params del aikit.yaml."""


def chat(message, tools=None, tool_executor=None, **kwargs) -> str:
    """Envía el mensaje al modelo y devuelve la respuesta final en texto."""
```

El núcleo comprueba durante el arranque que ambas funciones existen y que `chat` acepta al menos
un argumento. Si no se cumple, el proceso no arranca.

## Responsabilidades del conector

`init()` prepara el cliente del proveedor con las credenciales y el modelo indicados en la
configuración, y guarda el prompt de sistema, que llega en el parámetro `prompt`.

`chat()` concentra la parte específica de cada proveedor:

- Traducir la lista `tools`, en formato neutro, al formato de herramientas del proveedor.
- Enviar el mensaje junto con el prompt de sistema.
- Si el modelo solicita una o varias herramientas, invocar `tool_executor(nombre, argumentos)`,
  que devuelve un diccionario con la clave `content`, y remitir el resultado al modelo.
- Repetir mientras el modelo siga solicitando herramientas, con un límite de pasos.
- Devolver la respuesta final como texto.

El conector nunca ejecuta las herramientas por su cuenta: siempre delega en `tool_executor`, que
proporciona el núcleo. De este modo la ejecución queda centralizada y es trazable.

## Formato de las herramientas

El núcleo entrega las herramientas en una estructura común, próxima a la convención de OpenAI:

```python
{
    "type": "function",
    "function": {
        "name": "horarios__get_schedule",
        "description": "[Servicio: horarios] Devuelve el horario de un día concreto.",
        "parameters": {
            "type": "object",
            "properties": {"day": {"type": "string", "description": "..."}},
            "required": ["day"],
        },
    },
}
```

Cada conector traduce esa estructura al formato de su proveedor. Los conectores existentes
incluyen una función auxiliar para esa conversión que puede servir de referencia.

## Registro

No hace falta registrar el conector en ningún sitio: basta con indicar el nombre del fichero en
la configuración.

```yaml
engine:
  module: mi_proveedor
  params:
    api_key_env: MI_PROVEEDOR_API_KEY
    model: nombre-del-modelo
```

## Recomendaciones

- Limitar el número de pasos del ciclo de herramientas para evitar bucles indefinidos.
- Registrar en el nivel `DEBUG` las herramientas solicitadas y sus argumentos: es la vía más
  rápida para diagnosticar por qué el modelo no invoca la operación esperada.
- No incorporar lógica de dominio al conector. Su única responsabilidad es la traducción entre
  el formato neutro del núcleo y el del proveedor.
