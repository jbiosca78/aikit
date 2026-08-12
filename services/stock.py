from typing import List, Dict, Any
from pydantic import BaseModel
from .service_contract import ServiceContract, MethodSchema
import unicodedata


class StockItem(BaseModel):
    cantidad: int
    nombre: str
    descripcion: str


class Service(ServiceContract):
    name = "stock"
    description = "Gestión de inventario físico: sitios y artículos almacenados."

    # Datos de ejemplo en memoria
    _sitios_items: Dict[str, List[StockItem]] = {
        "armario cocina 1": [
            StockItem(cantidad=3, nombre="platos", descripcion="Platos de cerámica"),
        ],
        "trastero": [
            StockItem(cantidad=2, nombre="esquís", descripcion="Esquís snowblade rojos"),
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
            MethodSchema(
                name="buscar_item",
                description="Busca un objeto por nombre y devuelve en qué sitios aparece.",
                params_schema={
                    "nombre": {
                        "type": "string",
                        "description": "Nombre o parte del nombre del objeto (ej. 'esquis')"
                    }
                },
                returns_schema={
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "sitio": {"type": "string"},
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

    def _normalize_text(self, text: str) -> str:
        # Normaliza para comparar sin acentos ni mayusculas.
        t = unicodedata.normalize("NFD", text or "")
        t = "".join(ch for ch in t if unicodedata.category(ch) != "Mn")
        return t.casefold().strip()

    def buscar_item(self, nombre: str) -> List[Dict]:
        q = self._normalize_text(nombre)
        if not q:
            return []

        matches: List[Dict] = []
        for sitio, items in self._sitios_items.items():
            for item in items:
                norm_name = self._normalize_text(item.nombre)
                norm_desc = self._normalize_text(item.descripcion)
                if q in norm_name or q in norm_desc:
                    matches.append({
                        "sitio": sitio,
                        "cantidad": item.cantidad,
                        "nombre": item.nombre,
                        "descripcion": item.descripcion,
                    })
        return matches
