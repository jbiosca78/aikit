"""Servicio de ejemplo: consultas sobre el catálogo de armarios (CSV)."""

import csv
import os
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional

from aikit.core.service_contract import ServiceContract, MethodSchema

DEFAULT_CSV = Path(__file__).resolve().parents[2] / "web" / "catalogo.csv"

INT_FIELDS = {
    "precio_eur",
    "ancho_cm",
    "alto_cm",
    "fondo_cm",
    "baldas",
    "peso_max_por_balda_kg",
    "peso_total_max_kg",
    "puertas",
    "montaje_min",
    "stock",
}
LIST_FIELDS = {"colores"}


def _normalize(text: Any) -> str:
    t = unicodedata.normalize("NFD", str(text or ""))
    t = "".join(ch for ch in t if unicodedata.category(ch) != "Mn")
    return t.casefold().strip()


class Service(ServiceContract):
    name = "catalogo"
    description = "Catálogo de armarios a medida: modelos, medidas, precios, colores y disponibilidad."

    def __init__(self) -> None:
        self._csv_path = Path(os.getenv("AIKIT_CATALOGO_CSV") or DEFAULT_CSV)
        self._rows: List[Dict[str, Any]] = []
        self._loaded_mtime: Optional[float] = None

    def list_methods(self) -> List[MethodSchema]:
        model_schema = {
            "type": "object",
            "additionalProperties": True,
        }
        return [
            MethodSchema(
                name="list_models",
                description="Devuelve un resumen de todos los modelos del catálogo (id, nombre, precio y medidas).",
                params_schema={},
                required_params=[],
                returns_schema={"type": "array", "items": model_schema},
            ),
            MethodSchema(
                name="get_model",
                description="Devuelve todos los datos de un modelo concreto buscando por id (ej. 'modelo1') o por nombre.",
                params_schema={
                    "model": {
                        "type": "string",
                        "description": "Identificador o nombre del modelo (ej. 'modelo2' o 'FLEX 140').",
                    }
                },
                required_params=["model"],
                returns_schema=model_schema,
            ),
            MethodSchema(
                name="search_models",
                description=(
                    "Busca modelos filtrando por precio, medidas, color o texto libre. "
                    "Todos los parámetros son opcionales; sin filtros devuelve todo el catálogo."
                ),
                params_schema={
                    "text": {
                        "type": "string",
                        "description": "Texto libre a buscar en cualquier campo (material, observaciones, etc.).",
                    },
                    "color": {"type": "string", "description": "Color deseado (ej. 'roble claro')."},
                    "max_price": {"type": "number", "description": "Precio máximo en euros."},
                    "max_width_cm": {"type": "number", "description": "Ancho máximo disponible en cm."},
                    "max_height_cm": {"type": "number", "description": "Alto máximo disponible en cm."},
                    "max_depth_cm": {"type": "number", "description": "Fondo máximo disponible en cm."},
                    "only_available": {
                        "type": "boolean",
                        "description": "Si es true, devuelve solo modelos con stock mayor que cero.",
                    },
                },
                required_params=[],
                returns_schema={"type": "array", "items": model_schema},
            ),
            MethodSchema(
                name="compare_models",
                description="Compara dos modelos campo a campo para explicar diferencias.",
                params_schema={
                    "model_a": {"type": "string", "description": "Primer modelo (id o nombre)."},
                    "model_b": {"type": "string", "description": "Segundo modelo (id o nombre)."},
                },
                required_params=["model_a", "model_b"],
                returns_schema={"type": "object", "additionalProperties": True},
            ),
            MethodSchema(
                name="check_availability",
                description="Devuelve stock, disponibilidad y plazo de envío de un modelo.",
                params_schema={
                    "model": {"type": "string", "description": "Identificador o nombre del modelo."}
                },
                required_params=["model"],
                returns_schema={"type": "object", "additionalProperties": True},
            ),
        ]

    # --- carga de datos -------------------------------------------------

    def _load(self) -> List[Dict[str, Any]]:
        try:
            mtime = self._csv_path.stat().st_mtime
        except OSError as exc:
            raise RuntimeError(f"No se puede leer el catálogo en {self._csv_path}: {exc}") from exc

        if self._loaded_mtime == mtime:
            return self._rows

        rows: List[Dict[str, Any]] = []
        with self._csv_path.open(newline="", encoding="utf-8") as fh:
            for raw in csv.DictReader(fh):
                rows.append(self._parse_row(raw))

        self._rows = rows
        self._loaded_mtime = mtime
        return self._rows

    def _parse_row(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        row: Dict[str, Any] = {}
        for key, value in raw.items():
            if key is None:
                continue
            value = (value or "").strip()
            if key in INT_FIELDS:
                row[key] = int(value) if value.lstrip("-").isdigit() else None
            elif key in LIST_FIELDS:
                row[key] = [v.strip() for v in value.split("|") if v.strip()]
            else:
                row[key] = value
        return row

    def _find(self, model: str) -> Optional[Dict[str, Any]]:
        q = _normalize(model)
        if not q:
            return None
        rows = self._load()
        for row in rows:
            if _normalize(row.get("modelo")) == q or _normalize(row.get("nombre")) == q:
                return row
        for row in rows:
            if q in _normalize(row.get("nombre")) or q in _normalize(row.get("modelo")):
                return row
        return None

    # --- métodos expuestos ----------------------------------------------

    def list_models(self) -> List[Dict[str, Any]]:
        return [
            {
                "modelo": row.get("modelo"),
                "nombre": row.get("nombre"),
                "precio_eur": row.get("precio_eur"),
                "ancho_cm": row.get("ancho_cm"),
                "alto_cm": row.get("alto_cm"),
                "fondo_cm": row.get("fondo_cm"),
                "colores": row.get("colores"),
                "disponibilidad": row.get("disponibilidad"),
            }
            for row in self._load()
        ]

    def get_model(self, model: str) -> Dict[str, Any]:
        row = self._find(model)
        if row is None:
            return {"encontrado": False, "modelo": model}
        return {"encontrado": True, **row}

    def search_models(
        self,
        text: str = "",
        color: str = "",
        max_price: Optional[float] = None,
        max_width_cm: Optional[float] = None,
        max_height_cm: Optional[float] = None,
        max_depth_cm: Optional[float] = None,
        only_available: bool = False,
    ) -> List[Dict[str, Any]]:
        q_text = _normalize(text)
        q_color = _normalize(color)
        limits = [
            ("precio_eur", max_price),
            ("ancho_cm", max_width_cm),
            ("alto_cm", max_height_cm),
            ("fondo_cm", max_depth_cm),
        ]

        results: List[Dict[str, Any]] = []
        for row in self._load():
            if q_color and not any(q_color in _normalize(c) for c in row.get("colores", [])):
                continue
            if any(
                limit is not None and (row.get(field) is None or row[field] > limit)
                for field, limit in limits
            ):
                continue
            if only_available and not (row.get("stock") or 0) > 0:
                continue
            if q_text and q_text not in _normalize(" ".join(str(v) for v in row.values())):
                continue
            results.append(row)
        return results

    def compare_models(self, model_a: str, model_b: str) -> Dict[str, Any]:
        a = self._find(model_a)
        b = self._find(model_b)
        if a is None or b is None:
            return {
                "encontrado": False,
                "modelo_a": model_a if a is None else a.get("modelo"),
                "modelo_b": model_b if b is None else b.get("modelo"),
            }

        differences = {
            field: {"a": a.get(field), "b": b.get(field)}
            for field in a
            if a.get(field) != b.get(field)
        }
        return {
            "encontrado": True,
            "a": a,
            "b": b,
            "diferencias": differences,
        }

    def check_availability(self, model: str) -> Dict[str, Any]:
        row = self._find(model)
        if row is None:
            return {"encontrado": False, "modelo": model}
        return {
            "encontrado": True,
            "modelo": row.get("modelo"),
            "nombre": row.get("nombre"),
            "stock": row.get("stock"),
            "disponibilidad": row.get("disponibilidad"),
            "envio_dias": row.get("envio_dias"),
        }
