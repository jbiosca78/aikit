# Armarios Mario

Caso de uso de comercio electronico empleado como ejemplo completo de AiKit y como base del
estudio comparativo de esfuerzo de integracion descrito en la memoria.

El catalogo de la tienda se materializa en cuatro variantes que parten del mismo punto y se
diferencian unicamente en como incorporan el asistente conversacional. Al compartir el estado
inicial, el coste de cada integracion puede obtenerse comparando directorios:

```bash
diff -rq base/web aikit/web
diff -rq base/web bedrock/web
diff -rq base/web langchain/web
```

## Directorios

- `base/`: la tienda sin ninguna funcionalidad de IA. Representa la aplicacion existente a la
  que se quiere anadir un asistente, y es el punto de partida comun de las otras dos variantes.
  Contiene solo `web/`, con el catalogo estatico, una ficha por modelo y `catalogo.csv`.

- `aikit/`: la misma tienda con el asistente incorporado mediante el _framework_.
  - `web/`: la base mas el componente `chat-popup` de AiKit, declarado en `plantilla.html` y
    configurado desde `chat-ia.js` mediante atributos, sin modificar su codigo.
  - `backend/`: la configuracion `aikit.yaml` y el servicio de dominio `services/catalogo.py`,
    que expone el catalogo como herramientas invocables. El nucleo no se modifica.

- `bedrock/`: la misma tienda con el asistente implementado directamente sobre el SDK del
  proveedor, sin _framework_. Es uno de los terminos de comparacion del estudio.
  - `web/`: la base mas un widget de chat propio (`chat.js` y `chat.css`), declarado tambien
    en `plantilla.html`.
  - `backend/`: `app.py`, con el bucle de invocacion de herramientas, la gestion del historial
    y la firma de sesiones, y `catalogo.py` con la misma logica de dominio.

- `langchain/`: la misma tienda con el asistente implementado mediante LangChain, el marco de
  orquestacion mas extendido. Es el segundo termino de comparacion.
  - `web/`: identica a la de `bedrock`, ya que LangChain no aporta componentes de interfaz.
  - `backend/`: `app.py`, donde las herramientas se declaran con decoradores y el bucle lo
    resuelve un agente, pero la sesion, el historial y el servicio web siguen siendo propios.
    Requiere las dependencias de `requirements.txt`.

## Datos

`catalogo.csv` es la unica fuente de datos y es identico en las tres variantes. Incluye casos
pensados para probar el asistente: un modelo agotado, otro que no requiere anclaje a pared,
modelos con puertas abatibles y correderas, y un rango amplio de precios y medidas.

Las ilustraciones de `web/img/` se generan a partir de las especificaciones de cada modelo:
la proporcion del dibujo corresponde a sus dimensiones reales y el numero y tipo de puertas,
las baldas y el color se toman del propio catalogo.

Las fichas de producto no se editan a mano. Se generan con `web/build.py` a partir de
`catalogo.csv` y de la disposicion comun definida en `web/plantilla.html`:

```bash
cd base/web && python3 build.py
```

Anadir un modelo consiste en anadir una fila al CSV y regenerar.

## Ejecucion

Cada variante se levanta por separado y las tres pueden convivir, ya que usan puertos distintos.

| Variante | Frontend | Backend |
|---|---|---|
| `base` | `web/serve.sh` (8082) | no tiene |
| `aikit` | `web/serve.sh` (8080) | `backend/serve.sh` (8000) |
| `bedrock` | `web/serve.sh` (8081) | `backend/run.sh` (8001) |
| `langchain` | `web/serve.sh` (8083) | `backend/run.sh` (8002) |

Los tres backends requieren credenciales de AWS con acceso a Bedrock. El perfil se indica en
`aikit/backend/aikit.yaml` y mediante las variables `BASELINE_AWS_PROFILE` y `LC_AWS_PROFILE`
en las variantes de comparacion.
