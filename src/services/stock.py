from typing import List, Dict, Any
from pydantic import BaseModel
from .base import BaseService, MethodSchema


class StockItem(BaseModel):
    cantidad: int
    nombre: str
    descripcion: str


class StockService(BaseService):
    name = "stock"
    description = "Gestión de inventario físico: sitios y artículos almacenados."

    # Datos de ejemplo en memoria
    _sitios_items: Dict[str, List[StockItem]] = {
        "armario cocina 1": [
            StockItem(cantidad=3, nombre="platos", descripcion="Platos de cerámica"),
        ],
        "trastero": [
            StockItem(cantidad=2, nombre="skis", descripcion="Skis snowblade rojos"),
            StockItem(cantidad=1, nombre="árbol de navidad", descripcion="Árbol artificial"),
        ],
        "despacho": [
            StockItem(cantidad=1, nombre="impresora", descripcion="Impresora láser"),
        ],
    }

    # Métodos disponibles para la IA (tool calling)
    def list_methods(self) -> List[MethodSchema]:
        return [
            MethodSchema(
                name="obtener_sitios",
                description="Devuelve una lista de lugares donde se almacenan objetos.",
                params_schema={},
                returns_schema={
                    "type": "array",
                    "items": {"type": "string"},
                },
            ),
            MethodSchema(
                name="obtener_items",
                description="Devuelve los objetos almacenados en un sitio concreto.",
                params_schema={
                    "sitio": {
                        "type": "string",
                        "description": "Nombre del sitio (ej. 'trastero')"
                    }
                },
                returns_schema={
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "cantidad": {"type": "integer"},
                            "nombre": {"type": "string"},
                            "descripcion": {"type": "string"},
                        }
                    }
                }
            ),
        ]

    # Métodos reales que ejecutará la API cuando la IA los invoque
    def obtener_sitios(self) -> List[str]:
        return list(self._sitios_items.keys())

    def obtener_items(self, sitio: str) -> List[Dict]:
        return [item.dict() for item in self._sitios_items.get(sitio, [])]
