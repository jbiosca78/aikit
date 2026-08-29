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
    name = "horarios"
    description = "Horario de atención al público de la tienda."

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

HORARIOS = {
    "lunes": "09:00-14:00 y 17:00-20:00",
    "martes": "09:00-14:00 y 17:00-20:00",
    "miercoles": "09:00-14:00 y 17:00-20:00",
    "jueves": "09:00-14:00 y 17:00-20:00",
    "viernes": "09:00-14:00 y 17:00-20:00",
    "sabado": "10:00-14:00",
    "domingo": "cerrado",
}


class Service(ServiceContract):
    name = "horarios"
    description = "Horario de atención al público de la tienda."

    def list_methods(self) -> List[MethodSchema]:
        return [
            MethodSchema(
                name="get_schedule",
                description=(
                    "Devuelve el horario de apertura de un día concreto. "
                    "Úsalo cuando pregunten a qué hora abre o cierra la tienda."
                ),
                params_schema={
                    "day": {
                        "type": "string",
                        "description": "Día de la semana en minúsculas, por ejemplo 'sabado'.",
                    }
                },
                required_params=["day"],
                returns_schema={"type": "object", "additionalProperties": True},
            ),
            MethodSchema(
                name="get_week_schedule",
                description="Devuelve el horario completo de la semana.",
                params_schema={},
                required_params=[],
                returns_schema={"type": "object", "additionalProperties": True},
            ),
        ]

    def get_schedule(self, day: str) -> Dict[str, Any]:
        clave = day.strip().lower()
        if clave not in HORARIOS:
            return {"encontrado": False, "dia": day}
        return {"encontrado": True, "dia": clave, "horario": HORARIOS[clave]}

    def get_week_schedule(self) -> Dict[str, str]:
        return dict(HORARIOS)
```

## Registrar el servicio

En la sección `services` del `aikit.yaml` de la integración:

```yaml
services:
  - name: horarios
```

Por convención, `name: horarios` carga el módulo `services.horarios` y su clase `Service`. Si el
módulo o la clase tienen otro nombre, se indican de forma explícita:

```yaml
services:
  - name: horarios
    module: mi_paquete.horarios
    class: HorariosService
```

Al arrancar, el núcleo importa el módulo, comprueba que cumple el contrato, consulta
`list_methods()` y publica las herramientas resultantes. En los registros de arranque aparece una
línea por cada servicio cargado.

## Cómo se presentan al modelo

Cada operación se publica con el nombre `servicio__metodo`, por ejemplo `horarios__get_schedule`.
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
  -d '{"message": "a que hora abris los sabados?"}'
```

También puede consultarse `GET /readiness`, que enumera los servicios cargados y el número total
de herramientas publicadas.
