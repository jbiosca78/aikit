# Crear un servicio de dominio

Un servicio expone la lógica de negocio de la aplicación al asistente. Cada uno de sus métodos
se traduce en una herramienta que el modelo puede invocar cuando lo considere necesario.

Añadir un servicio no requiere modificar el núcleo: basta con crear un fichero y declararlo en
la configuración.

## Resumen

1. Crear un fichero en el directorio `services/` de la integración.
2. Definir una clase `Service` que implemente `ServiceContract`.
3. Declarar en `list_methods()` las operaciones que el modelo podrá invocar.
4. Implementar esos métodos.
5. Registrar el servicio en `aikit.yaml`.

## El contrato

```python
from aikit.core.service_contract import ServiceContract, MethodSchema


class Service(ServiceContract):
    name = "pedidos"
    description = "Consulta del estado de los pedidos de un cliente."

    def list_methods(self) -> list[MethodSchema]:
        ...
```

La clase debe llamarse `Service`, salvo que se indique otro nombre en la configuración. Los
atributos `name` y `description` identifican el servicio y ayudan al modelo a situarlo.

## Declarar las operaciones

`list_methods()` devuelve la lista de operaciones invocables. Cada una se describe con un
`MethodSchema`:

| Campo | Descripción |
|---|---|
| `name` | Nombre del método. Debe coincidir con el de la función implementada |
| `description` | Cuándo debe usarse. El modelo decide a partir de este texto |
| `params_schema` | Parámetros, con el formato de propiedades de JSON Schema |
| `required_params` | Parámetros obligatorios. Si se omite, se consideran obligatorios todos |
| `returns_schema` | Estructura del valor devuelto |

La descripción es la parte más importante: es lo único que el modelo tiene para decidir si
invoca la operación. Conviene redactarla indicando en qué situación resulta útil, no solo qué
hace.

## Ejemplo completo

```python
from typing import Any, Dict, List

from aikit.core.service_contract import ServiceContract, MethodSchema

PEDIDOS = {
    "A-1024": {"estado": "en reparto", "entrega_estimada": "2026-03-04", "transportista": "SEUR"},
    "A-1025": {"estado": "en preparacion", "entrega_estimada": "2026-03-09", "transportista": None},
    "A-1026": {"estado": "entregado", "entrega_estimada": "2026-02-27", "transportista": "MRW"},
}


class Service(ServiceContract):
    name = "pedidos"
    description = "Consulta del estado de los pedidos de un cliente."

    def list_methods(self) -> List[MethodSchema]:
        return [
            MethodSchema(
                name="get_order",
                description=(
                    "Devuelve el estado de un pedido a partir de su referencia. "
                    "Úsalo cuando pregunten por un pedido concreto o por su fecha de entrega."
                ),
                params_schema={
                    "reference": {
                        "type": "string",
                        "description": "Referencia del pedido, por ejemplo 'A-1024'.",
                    }
                },
                required_params=["reference"],
                returns_schema={"type": "object", "additionalProperties": True},
            ),
            MethodSchema(
                name="list_pending_orders",
                description="Devuelve los pedidos que aún no se han entregado.",
                params_schema={},
                required_params=[],
                returns_schema={"type": "array", "items": {"type": "object"}},
            ),
        ]

    def get_order(self, reference: str) -> Dict[str, Any]:
        clave = reference.strip().upper()
        if clave not in PEDIDOS:
            return {"encontrado": False, "referencia": reference}
        return {"encontrado": True, "referencia": clave, **PEDIDOS[clave]}

    def list_pending_orders(self) -> List[Dict[str, Any]]:
        return [
            {"referencia": ref, **datos}
            for ref, datos in PEDIDOS.items()
            if datos["estado"] != "entregado"
        ]
```

## Registrar el servicio

En la sección `services` del `aikit.yaml` de la integración:

```yaml
services:
  - name: pedidos
```

Por convención, `name: pedidos` carga el módulo `services.pedidos` y su clase `Service`. Si el
módulo o la clase tienen otro nombre, se indican de forma explícita:

```yaml
services:
  - name: pedidos
    module: mi_paquete.pedidos
    class: PedidosService
```

Al arrancar, el núcleo importa el módulo, comprueba que cumple el contrato, consulta
`list_methods()` y publica las herramientas resultantes. En los registros de arranque aparece una
línea por cada servicio cargado.

## Cómo se presentan al modelo

Cada operación se publica con el nombre `servicio__metodo`, por ejemplo `pedidos__get_order`.
El prefijo evita colisiones entre servicios distintos y permite al núcleo enrutar la invocación.

Cuando el modelo solicita una herramienta, el núcleo localiza el servicio, ejecuta el método con
los argumentos recibidos y devuelve el resultado serializado en JSON. El modelo redacta entonces
la respuesta final apoyándose en esos datos.

## Recomendaciones

- Los métodos que empiezan por guion bajo se consideran internos y no son invocables.
- Devolver estructuras de datos, no texto redactado: de la redacción se encarga el modelo.
- Ante una consulta sin resultados, devolver una respuesta explícita, como
  `{"encontrado": false}`, en lugar de una lista vacía sin contexto. Ayuda al modelo a explicar
  la ausencia del dato en lugar de inventarlo.
- Si una operación debe producir una confirmación concreta para el usuario, puede incluirse en
  el resultado un campo `user_message`, que el núcleo utilizará como respuesta directa.
- Mantener los métodos con parámetros simples: cadenas, números y valores booleanos se
  interpretan mejor que estructuras anidadas.

## Comprobación

Con el servicio registrado y el proceso en marcha:

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "como va mi pedido A-1024?"}'
```

También puede consultarse `GET /readiness`, que enumera los servicios cargados y el número total
de herramientas publicadas.
